"""Run the compact LunArmBench × SuperDex experiment matrix."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    "SUPERDEX_ASSETS_PATH", str(ROOT / "third_party" / "project_superdex" / "assets")
)

from lunarmbench.paths import ensure_assets_path
from lunarmbench.plotting import analyze
from lunarmbench.runner import TrialSpec, new_run_dir, run_trials


def build_matrix(reps: int) -> list[TrialSpec]:
    specs: list[TrialSpec] = []
    # Experiment A: nominal mechanics
    for cfg in ("nominal_earth.yaml", "nominal_moon.yaml"):
        for seed in range(reps):
            specs.append(TrialSpec(f"A_{cfg}_{seed}", cfg, True, seed, {}))
    # Experiment B: translation uncertainty (Y offset)
    for mm, cfg in (
        (0, "nominal_moon.yaml"),
        (2, "pose_uncertainty_small.yaml"),
        (5, "pose_uncertainty_medium.yaml"),
        (10, "pose_uncertainty_large.yaml"),
    ):
        for seed in range(reps):
            specs.append(
                TrialSpec(f"B_{mm}mm_{seed}", cfg, False if mm else True, seed, {})
            )
    # Experiment C: angular uncertainty
    for deg, cfg in (
        (0, "nominal_moon.yaml"),
        (1, "angular_uncertainty_small.yaml"),
        (3, "angular_uncertainty_medium.yaml"),
        (5, "angular_uncertainty_large.yaml"),
    ):
        for seed in range(reps):
            oracle = deg == 0
            specs.append(TrialSpec(f"C_{deg}deg_{seed}", cfg, oracle, seed, {}))
    # Experiment D: combined random
    for seed in range(max(reps * 4, 20)):
        specs.append(TrialSpec(f"D_combined_{seed}", "combined_uncertainty.yaml", False, seed, {}))
    return specs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--name", default="connector_v0")
    args = parser.parse_args()
    ensure_assets_path()
    specs = build_matrix(args.reps)
    run_dir = new_run_dir(args.name)
    csv_path = run_trials(specs, run_dir, ROOT)
    summary = analyze(csv_path, run_dir / "plots")
    print(f"Wrote {csv_path}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
