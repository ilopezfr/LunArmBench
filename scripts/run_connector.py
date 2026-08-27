"""Run a single Lunar Connector Insertion V0 episode."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    "SUPERDEX_ASSETS_PATH", str(ROOT / "third_party" / "project_superdex" / "assets")
)

from lunarmbench.config import load_config
from lunarmbench.paths import ensure_assets_path
from lunarmbench.task import run_episode


def _git_sha(cwd: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
    except Exception:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="nominal_moon.yaml")
    parser.add_argument("--oracle", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    ensure_assets_path()
    overrides = {}
    if args.seed is not None:
        overrides["seed"] = args.seed
    cfg = load_config(args.config, **overrides)
    rec = run_episode(
        cfg,
        oracle=args.oracle,
        git_commit=_git_sha(ROOT),
        superdex_commit=_git_sha(ROOT / "third_party" / "project_superdex"),
        config_name=Path(args.config).stem,
    )
    print(json.dumps(rec.to_dict(), indent=2))
    return 0 if rec.success else 2


if __name__ == "__main__":
    raise SystemExit(main())
