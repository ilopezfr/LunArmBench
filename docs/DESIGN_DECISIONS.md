# Design decisions (locked for this spike)

Revisit only if a SuperDex API forces it. These are POC choices, not mission requirements.

## Install

- PyPI wheels `superdex==1.0.0` via `uv pip install`. Clone `facebookresearch/project_superdex` branch `stable` to `third_party/project_superdex` for assets and examples. **Do not vendor SuperDex.**
- `SUPERDEX_ASSETS_PATH` points at `third_party/project_superdex/assets` for robotics; cable recon temporarily points at `superdex_physics/assets`.
- No source build. No Studio. No GPU. Precision left at single.

## Robot

Fixed-base shipped combo `bots/arm_hand_combos/fr3_v2_2f_85`. No mobile base, humanoid, or bimanual work.

## Held connector

The plug is a `HARD`-welded `BotLinkPrefab` child of `2f_85_base_link` at `z = 0.155` m. Contact against gripper links is disabled. This isolates alignment / contact / insertion. There is no perception and no pick.

## Geometry

Synthetic keyed rectangle (D-shaped key), meters, generated as a triangle mesh from `ConnectorGeometry`. Clearance 1.5 mm per side so debugging is possible. Success thresholds (POC, not flight):

- insertion depth ≥ 18 mm
- lateral error ≤ 4 mm
- orientation error ≤ 5°

Not NASA CAD. Not a commercial connector. Not the shipped nine-hole peg prefab.

## Gravity vs OSC

Scene gravity stays **on** (`[0,0,-9.81]` or `[0,0,-1.62]`). Earth vs Moon is otherwise meaningless.

`BASIC_OSC_PD` has no gravity term. Official examples disable gravity on every link. This POC disables gravity only on `fr3_*` links so the Cartesian baseline can track; the gripper and welded plug still see scene gravity. Residual Earth vs Moon differences are therefore small and must not be over-interpreted.

If OSC had sagged unusably with this compromise, the fallback was IK + `MOCHI_ARTICULATED_POSE`. It was not needed.

## Socket actor

A truly static receptacle does **not** expose `TOTAL_CONTACT_FORCE` / `CONTACT_POINTS`. The socket is a dynamic rigid SDF actor with `has_gravity=False`, welded to the world with stiff pivot position + rotation constraints, so contact queries can be registered. This is an instrumentation choice, not a claim that flight hardware floats.

## Controller baselines

- **B0 Oracle:** waypoint planner uses the true socket pose. Required to produce at least one geometric success.
- **B1 Uncertainty:** planner uses the unperturbed estimate (configured translation/rotation undone).
- **B2 Recovery:** implemented behind `controller.enable_recovery` (retract + small lateral search). Not enabled in the compact matrix.

Waypoints: approach → near-contact → insert. Speeds and standoff live in YAML.

## Benchmark vs controller vs reward

Scoring lives in `lunarmbench/metrics.py` and is independent of OSC internals. The Gymnasium reward in `LunarConnectorInsertionEnv` is a training signal only and is not the success definition.

## Gym

`MochiEnv` is Lab-centric (SceneManager, Polyscope, shared scenes). The spike wraps the Physics/Robotics task as a standalone Gymnasium env `LunArmBench/LunarConnectorInsertion-v0`: privileged 25-D observation, 6-D Cartesian delta action, OSC as the low-level tracker.

## Runner

Each invocation of `scripts/run_sweep.py` creates `results/<UTC>_<name>/` with `manifest.json`, `episodes.csv`, copied YAML, and `plots/`. Previous runs are never overwritten. Resume skips CSV keys already present.

## Out of scope (still)

Humanoids, mobile bases, bimanual, real NASA CAD, dust/thermal/regolith, photoreal Moon, perception/VLA, HIL, teleop, full cable routing, RL as the main goal.
