"""Batch experiment runner with resume-safe per-run directories."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lunarmbench.config import load_config
from lunarmbench.paths import CONFIGS_DIR, RESULTS_DIR
from lunarmbench.task import run_episode


def _git_sha(cwd: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
    except Exception:
        return ""


@dataclass
class TrialSpec:
    trial_id: str
    config_path: str
    oracle: bool
    seed: int
    extra_overrides: dict


def new_run_dir(name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    path = RESULTS_DIR / f"{stamp}_{name}"
    (path / "configs").mkdir(parents=True, exist_ok=True)
    (path / "logs").mkdir(exist_ok=True)
    (path / "plots").mkdir(exist_ok=True)
    return path


def _episode_key(spec: TrialSpec) -> str:
    return f"{spec.trial_id}|{spec.seed}|{int(spec.oracle)}"


def _load_done(csv_path: Path) -> set[str]:
    done: set[str] = set()
    if not csv_path.exists():
        return done
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            done.add(f"{row.get('config_name')}|{row.get('random_seed')}|{1 if 'oracle' in row.get('controller','') else 0}")
    return done


def run_trials(specs: list[TrialSpec], run_dir: Path, repo_root: Path) -> Path:
    csv_path = run_dir / "episodes.csv"
    git_commit = _git_sha(repo_root)
    superdex_commit = _git_sha(repo_root / "third_party" / "project_superdex")
    fieldnames = None
    done = _load_done(csv_path)
    manifest = {
        "created": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "superdex_commit": superdex_commit,
        "n_specs": len(specs),
        "python": sys.version,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    # Snapshot YAML conditions so the run directory is self-contained.
    for spec in specs:
        src = Path(spec.config_path)
        if not src.is_absolute():
            src = CONFIGS_DIR / src
        dst = run_dir / "configs" / src.name
        if src.exists() and not dst.exists():
            dst.write_text(src.read_text())

    for spec in specs:
        key = f"{Path(spec.config_path).stem}|{spec.seed}|{int(spec.oracle)}"
        # also try trial_id match
        if key in done or _episode_key(spec) in done:
            continue
        cfg = load_config(spec.config_path, seed=spec.seed, **spec.extra_overrides)
        rec = run_episode(
            cfg,
            oracle=spec.oracle,
            git_commit=git_commit,
            superdex_commit=superdex_commit,
            config_name=Path(spec.config_path).stem,
        )
        row = rec.to_dict()
        row["trial_id"] = spec.trial_id
        if fieldnames is None:
            fieldnames = list(row.keys())
            write_header = not csv_path.exists()
            with csv_path.open("a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    w.writeheader()
                w.writerow(row)
        else:
            with csv_path.open("a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writerow(row)
        done.add(key)
    return csv_path
