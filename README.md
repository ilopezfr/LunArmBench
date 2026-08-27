# LunArmBench × SuperDex Connector Insertion Spike

Engineering spike, not a full benchmark. The question this repo answers:

> Can SuperDex support one repeatable, parameterized, measurable Lunar Connector Insertion V0 task well enough to decide whether it belongs in the LunArmBench stack?

**Recommendation: B — contact-rich specialized backend.** SuperDex can host a held-in-gripper insertion task headlessly, with Earth/Moon gravity and a pose-uncertainty sweep. It is not yet a primary LunArmBench stack: Lab is early-preview, `BASIC_OSC_PD` has no gravity term, and contact queries are missing on static and articulated links. See [`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md).

## What this POC includes

- Headless SuperDex 1.0.0 install on Python 3.12 (no Studio, no GPU).
- Lunar Connector Insertion V0: fixed-base FR3 v2 + Robotiq 2F-85, synthetic keyed plug welded in the gripper, oracle OSC insertion.
- YAML conditions, geometric scoring independent of the controller, resumable sweep runner.
- Compact Earth/Moon + pose-uncertainty matrix and plots.
- Gymnasium env `LunArmBench/LunarConnectorInsertion-v0` (privileged obs; reward is **not** the benchmark).
- Cable/rod/tendon feasibility notes. No PPO training (documented sink).

Geometry is abstract. It is **not** a NASA or commercial connector.

## Environment fingerprint (this spike)

| Item | Value |
|---|---|
| OS | Ubuntu 24.04, Linux x86_64, 4 vCPU, 16 GB RAM, no GPU |
| Python | 3.12.3 |
| SuperDex wheels | `superdex==1.0.0` (physics / robotics / lab / studio) |
| SuperDex clone | `stable` @ `1d7150946fa3f3d3fb09c2bff07eaa138cbfdee6` |
| Precision | single (`SUPERDEX_PRECISION` unset) |
| Gravity API | `scene.set_gravity([0, 0, -g])`, Z-up FLU in robotics examples |

## Setup

Python 3.12 and `uv` are required. SuperDex is cloned **outside the committed tree**.

```bash
git clone https://github.com/ilopezfr/LunArmBench.git
cd LunArmBench

# Assets + examples (gitignored)
mkdir -p third_party
git clone --branch stable --depth 1 https://github.com/facebookresearch/project_superdex.git third_party/project_superdex

uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

export SUPERDEX_ASSETS_PATH="$PWD/third_party/project_superdex/assets"
export PYTHONPATH="$PWD"
```

Verify the install (Physics, Robotics FR3+2F-85, Lab CartPole; each smoke runs in a subprocess because `physics.initialize()` / `shutdown()` is not re-entrant):

```bash
python scripts/verify_install.py
python scripts/gravity_sanity.py
python scripts/robot_smoke_test.py
```

## Run the task

Single oracle episode (Moon gravity):

```bash
python scripts/run_connector.py --config nominal_moon.yaml --oracle
```

Uncertainty episode (controller does not see the true fixture pose):

```bash
python scripts/run_connector.py --config pose_uncertainty_medium.yaml --no-oracle
```

Compact matrix (Earth/Moon oracle, translation/angular sweeps, combined random ≥20 trials) plus plots:

```bash
python scripts/run_sweep.py --reps 5 --name connector_v0
python scripts/analyze_results.py results/<run_dir>
```

Gymnasium wrap:

```python
import gymnasium as gym
import lunarmbench  # registers LunArmBench/LunarConnectorInsertion-v0

env = gym.make("LunArmBench/LunarConnectorInsertion-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
env.close()
```

Cable/rod/tendon recon (uses `superdex_physics/assets`, not the main robotics asset tree):

```bash
python scripts/cable_feasibility.py
```

Tests:

```bash
python -m pytest tests -q
```

## Layout

```text
configs/          YAML task conditions (gravity, pose noise)
docs/             capability map, design, limitations, final report
lunarmbench/      task, scene, OSC baseline, metrics, runner, gym env
scripts/          install smokes, episode, sweep, cable recon
tests/
results/          timestamped run directories (never overwritten)
third_party/      gitignored SuperDex clone
```

## Docs

- [`docs/SUPERDEX_CAPABILITY_MAP.md`](docs/SUPERDEX_CAPABILITY_MAP.md) — inspected APIs
- [`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md)
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)
- [`docs/CABLE_FEASIBILITY.md`](docs/CABLE_FEASIBILITY.md)
- [`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md)

## Out of scope

Humanoids, mobile bases, bimanual, real NASA CAD, dust/thermal/regolith, photoreal Moon, perception/VLA, HIL, teleop, full cable routing, RL as the main goal.
