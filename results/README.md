# Results

Timestamped run directories are never overwritten.

## Compact matrix (this spike)

`2026-08-27_033951_connector_v0/`

- `manifest.json` — git SHAs, Python, spec count
- `episodes.csv` — 60 episodes
- `configs/` — YAML snapshots
- `plots/` — required robustness figures + `summary.json`

Headline: Earth/Moon oracle 1.00 (n=5 each); translation 2 mm 1.00, 5 mm 0.00, 10 mm 0.00; angular 1–5° 1.00 (geometry not stressed); combined random 0.45 (n=20). Overall 0.65.

## Demo traces

`demo/nominal_success.npz`, `demo/10_mm_misalignment.npz`, `demo/success_vs_misalignment.png`.

No MP4: headless CPU box, official debugger GUI unused, video extensions gitignored. The PNG/NPZ pair is the success vs failure artifact.
