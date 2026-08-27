# AGENTS.md

## Cursor Cloud specific instructions

This repo (`lunarmbench-superdex-poc`) is a **headless, CPU-only CLI/batch research tool** — there are
no long-running services, servers, ports, databases, or GUI. "Running the app" means executing a
script that simulates an episode and writes result files. Standard commands (install smokes, single
episode, sweep, gym usage, tests) are documented in `README.md`; use those rather than duplicating them.

Environment setup (uv install, `.venv` creation, `project_superdex` clone, `uv pip install -e ".[dev]"`)
is handled by the startup update script, so it is already done for you. Non-obvious notes:

- **Use the project venv.** `uv` auto-detects `.venv` in the repo root, so `uv pip ...` targets it
  without activation. Run code with `.venv/bin/python ...` (or `source .venv/bin/activate`).
  `uv` lives at `~/.local/bin/uv` (already on `PATH` via `~/.bashrc`).
- **`SUPERDEX_ASSETS_PATH` and `PYTHONPATH` do NOT need to be set manually.** `lunarmbench.paths`
  defaults the assets path to `third_party/project_superdex/assets`, and the package is installed
  editable, so scripts/tests/gym all resolve on their own. Only export `SUPERDEX_ASSETS_PATH` if you
  relocate the SuperDex clone away from `third_party/`.
- **`third_party/project_superdex` is gitignored and cloned separately** (branch `stable`). It is not
  part of the committed tree; the update script clones it if missing.
- **`physics.initialize()` / `physics.shutdown()` is not re-entrant.** Each install smoke
  (`scripts/verify_install.py`, `gravity_sanity.py`, `robot_smoke_test.py`) runs its physics session in
  its own subprocess. Do not start multiple physics sessions in one Python process.
- **Results are written to `results/<timestamp>_<name>/` and never overwritten**; each run creates a new
  timestamped directory.
