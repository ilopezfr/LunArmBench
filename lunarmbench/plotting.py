"""Plot LunArmBench SuperDex POC results."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def analyze(csv_path: Path, plot_dir: Path) -> dict:
    df = pd.read_csv(csv_path)
    plot_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "n": int(len(df)),
        "success_rate": float(df["success"].mean()) if len(df) else 0.0,
        "by_config": df.groupby("config_name")["success"].mean().to_dict() if len(df) else {},
    }

    def _save(fig, name):
        fig.tight_layout()
        fig.savefig(plot_dir / name, dpi=140)
        plt.close(fig)

    if "initial_translation_error" in df.columns:
        g = df.copy()
        g["trans_mm"] = (g["initial_translation_error"] * 1000).round(1)
        rates = g.groupby("trans_mm")["success"].agg(["mean", "count"])
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(rates.index, rates["mean"], marker="o")
        ax.set_xlabel("Translational pose error (mm)")
        ax.set_ylabel("Success rate")
        ax.set_title(f"Success vs translation error (n={len(g)})")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        _save(fig, "success_vs_translation.png")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(g["trans_mm"], g["completion_time"], alpha=0.6)
        ax.set_xlabel("Translational pose error (mm)")
        ax.set_ylabel("Completion time (s)")
        ax.set_title("Completion time vs translation error")
        ax.grid(True, alpha=0.3)
        _save(fig, "time_vs_translation.png")

    if "initial_rotation_error" in df.columns:
        g = df.copy()
        g["rot_deg"] = (g["initial_rotation_error"] * 180.0 / 3.14159265).round(1)
        rates = g.groupby("rot_deg")["success"].agg(["mean", "count"])
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(rates.index, rates["mean"], marker="o")
        ax.set_xlabel("Angular pose error (deg)")
        ax.set_ylabel("Success rate")
        ax.set_title(f"Success vs angular error (n={len(g)})")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        _save(fig, "success_vs_angular.png")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(g["rot_deg"], g["completion_time"], alpha=0.6)
        ax.set_xlabel("Angular pose error (deg)")
        ax.set_ylabel("Completion time (s)")
        ax.set_title("Completion time vs angular error")
        ax.grid(True, alpha=0.3)
        _save(fig, "time_vs_angular.png")

    fig, ax = plt.subplots(figsize=(7, 4))
    counts = df["termination_reason"].value_counts()
    ax.bar(counts.index.astype(str), counts.values)
    ax.set_ylabel("Count")
    ax.set_title(f"Failure mode counts (n={len(df)})")
    ax.tick_params(axis="x", rotation=30)
    _save(fig, "failure_modes.png")

    if "peak_contact_force" in df.columns and df["peak_contact_force"].notna().any():
        fig, ax = plt.subplots(figsize=(6, 4))
        ok = df[df["success"] == True]  # noqa: E712
        bad = df[df["success"] == False]  # noqa: E712
        ax.scatter(ok["initial_translation_error"] * 1000, ok["peak_contact_force"], label="success", alpha=0.7)
        ax.scatter(bad["initial_translation_error"] * 1000, bad["peak_contact_force"], label="failure", alpha=0.7)
        ax.set_xlabel("Translational pose error (mm)")
        ax.set_ylabel("Peak contact force (N)")
        ax.set_title("Peak contact force vs pose error")
        ax.legend()
        ax.grid(True, alpha=0.3)
        _save(fig, "force_vs_translation.png")

    if "gravity" in df.columns:
        fig, ax = plt.subplots(figsize=(5, 4))
        rates = df.groupby("gravity")["success"].mean()
        ax.bar([str(x) for x in rates.index], rates.values)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Success rate")
        ax.set_xlabel("Gravity (m/s^2)")
        ax.set_title("Earth vs Moon oracle (do not overinterpret)")
        _save(fig, "earth_vs_moon.png")

    (plot_dir / "summary.json").write_text(pd.Series(summary).to_json())
    return summary
