# LunArmBench × SuperDex — final report

Engineering spike on SuperDex `stable` (`1d7150946fa3f3d3fb09c2bff07eaa138cbfdee6`, wheels `1.0.0`). Not a benchmark release.

## Executive summary

SuperDex can host **one** repeatable, parameterized, measurable Lunar Connector Insertion V0 task headlessly: fixed-base FR3 v2 + Robotiq 2F-85, synthetic keyed plug welded in the gripper, oracle OSC insertion that succeeds geometrically on Earth and Moon gravity, plus a pose-uncertainty sweep that fails at 5–10 mm of lateral fixture error.

It should **not** be LunArmBench’s primary stack. Lab is early-preview, Cartesian OSC has no gravity term, and contact-force queries are missing on static and articulated bodies.

**Recommendation: B — contact-rich specialized backend.**

## Environment

| Item | Value |
|---|---|
| Host | Ubuntu 24.04, Linux x86_64, 4 vCPU, 16 GB, no GPU |
| Python | 3.12.3 in `/workspace/.venv` |
| Wheels | `superdex==1.0.0` (physics, robotics, lab, studio) |
| Clone | `third_party/project_superdex` @ `1d7150946fa3f3d3fb09c2bff07eaa138cbfdee6` |
| Precision | single |
| Assets | `SUPERDEX_ASSETS_PATH=.../project_superdex/assets` |

Install commands: see the repository README. `python scripts/verify_install.py` smokes Physics (falling cube), Robotics (FR3+2F-85, 13 DoF / 20 links), and Lab CartPole. Each smoke is a subprocess because initialize/shutdown is not re-entrant.

Doc-vs-reality: official robotics examples gate `scene.step` on `physics.debugger.attach()`; headless must skip that. OSC examples disable link gravity. `DEFAULT_GRAVITY` is Y-down, not Z-up.

## Task

**Lunar Connector Insertion V0** (`lunarmbench/task.py`):

- Robot at the shipped home pose.
- Plug HARD-welded to `2f_85_base_link`, no start interpenetration.
- Socket in front of the robot; pose from YAML (deterministic offset or Gaussian).
- Control: approach → near-contact → insert via `BASIC_OSC_PD` until geometric success, timeout (6 s), force limit, or solver divergence.

Success (POC thresholds): depth ≥ 18 mm, lateral ≤ 4 mm, orientation ≤ 5°, still inside the receptacle. Implemented in `lunarmbench/metrics.py`, not in the controller and not in the Gym reward.

Oracle (B0) uses the true socket pose. Uncertainty (B1) plans from the unperturbed estimate.

## Experiments

Run directory: `results/2026-08-27_033951_connector_v0/` (60 episodes, ~31 s wall).

| Block | Condition | n | Success |
|---|---|---|---|
| A | Earth oracle g=9.81 | 5 | 1.00 |
| A | Moon oracle g=1.62 | 5 | 1.00 |
| B | Moon, 0 mm | 5 | 1.00 |
| B | Moon, 2 mm Y | 5 | 1.00 |
| B | Moon, 5 mm Y | 5 | 0.00 (timeout) |
| B | Moon, 10 mm Y | 5 | 0.00 (misalignment) |
| C | Moon, 1 / 3 / 5 deg | 5×3 | 1.00 |
| D | Moon, combined N(0, 4 mm) × N(0, 2°) | 20 | 0.45 |

Overall success 0.65. Mean successful completion time ~1.56 s sim, RTF ~4. Earth and Moon oracle traces are nearly identical (insertion depth 18.10 mm vs 18.07 mm). **Do not overinterpret gravity.** FR3 links have gravity disabled for OSC.

Angular 5° succeeded because the success lateral band (4 mm) swallows the geometric drift of a 5° error over 18 mm of insertion. The rotation sweep did not bite.

Plots (sample counts annotated in titles): `success_vs_translation.png`, `success_vs_angular.png`, `time_vs_*.png`, `failure_modes.png`, `force_vs_translation.png`, `earth_vs_moon.png`. Demo traces: `results/demo/success_vs_misalignment.png` plus `nominal_success.npz` / `10_mm_misalignment.npz`.

Contact-force values are **not** a calibrated wrench. Many successes log ~0 N on the welded socket query.

## Failure modes

Observed taxonomy in the matrix: `success`, `timeout` (5 mm translation), `misalignment` (10 mm and half of combined). No `simulation_instability`, no `force_threshold`. Recovery (B2) was not enabled.

## Gym

`LunArmBench/LunarConnectorInsertion-v0`: privileged obs (25,), 6-D Cartesian delta, OSC tracker, reward separate from `lunarmbench.metrics`. Reset / step / re-reset works. Not a `MochiEnv` subclass.

PPO was skipped (non-re-entrant physics runtime; would be a sink).

## Cable

Headless smokes (this machine): helix rod + hanging cube steps under Earth and Moon g (129 nodes); spatial tendon on the official comparison prefab (9 links, 5 waypoints, 40 steps); programmatic rod through two spherical guides under lunar g. Earth/Moon cube motion after 90 frames is still transient — not an equilibrium sag metric. See `docs/CABLE_FEASIBILITY.md`. Not a routing task.

## SuperDex scored 1–5

| Dimension | Score | Note |
|---|---|---|
| Headless install / unattended stepping | 4 | Wheels + clone work; examples are GUI-gated; initialize not re-entrant |
| Gravity as a first-class scene parameter | 5 | `set_gravity`/`get_gravity` Z-up works; default vector is Y-down |
| Gravity × Cartesian control | 2 | OSC has no gravity term; must disable arm-link gravity |
| Robot assets (FR3 + 2F-85) | 5 | Shipped combo instantiates |
| Held-object weld / scene authoring | 4 | `HARD` joint + contact overrides; URDF primitives ignored |
| Contact-rich insertion (geometry) | 4 | Oracle insertions succeed; SDF meshes contact |
| Contact queries / force logs | 2 | Missing on static + articulated; socket weld is a workaround |
| Pose-uncertainty experiment tooling | 4 | YAML + runner + plots; angular grid was too gentle |
| Lab / Gym / RL substrate | 2 | CartPole only; MochiEnv is heavy; no vectorized custom Robotics env |
| Deformables / cables | 3 | Experimental rod/tendon APIs are real; asset path split; not task-ready |
| Docs vs runtime | 2 | Debugger-gated examples, gravity-off OSC, Y-down default |
| Headless video / photoreal | 1 | Not used; no GPU; PNG traces only |

## Recommendation

**B — contact-rich specialized backend.**

- **Not A (primary stack):** Lab is preview, OSC gravity is a research footgun, contact queries are incomplete, docs disagree with defaults.
- **Not C (experimental secondary only):** the insertion task, metrics, and sweep actually ran unattended with a clear robustness cliff at 5 mm.
- **Not D (drop):** SuperDex is a serious contact/deformable engine with the preferred robot already shipped.

Use SuperDex where LunArmBench needs SDF contact, rods/tendons, or this FR3 combo. Keep a second simulator for gravity-aware Cartesian control, vectorized RL, and static-fixture force sensing.

## Next experiment (if SuperDex stays in play)

1. Gravity-compensated Cartesian baseline (IK + `MOCHI_ARTICULATED_POSE`, or add a gravity term) with **all** `has_gravity=True`, then repeat Earth vs Moon.
2. Tighten clearance and rerun the angular sweep so 3–5° can fail.
3. Find or request contact queries on articulated links; drop the dynamic-socket weld.
4. Only then consider a cable-through-guides task on the physics asset tree.

## Answers to the 25 research questions

1. **Can SuperDex be installed headlessly from 1.0.0 wheels on Python 3.12 Linux?** Yes.
2. **Does `import superdex.physics / robotics / lab.gym` work without Studio?** Yes.
3. **Do assets resolve via `SUPERDEX_ASSETS_PATH`?** Yes for robotics assets. Tendon/rod examples need `superdex_physics/assets`.
4. **Can a Physics scene step without `debugger.attach()`?** Yes. Official examples will no-op if you copy them verbatim.
5. **Can Lab CartPole reset/step with `render_mode=None`?** Yes.
6. **Is gravity a first-class API?** Yes: `scene.set_gravity` / `get_gravity`. Set Z-up explicitly; do not trust `DEFAULT_GRAVITY`.
7. **Can gravity be set to Earth and Moon values?** Yes (9.81 and 1.62). Round-trip verified.
8. **Does the preferred FR3 v2 + 2F-85 combo instantiate?** Yes, 13 DoF, 20 links, `2f_85_base_link` present.
9. **Is Cartesian OSC available?** Yes, `BASIC_OSC_PD`. Target is `root_from_target_ee`; observations include `world_from_ee_link`.
10. **Does OSC include a gravity term?** No. Official examples disable link gravity.
11. **Can a plug be rigidly held in the gripper at reset?** Yes, `ArticulatedJointType.HARD` on a child link, with contact overrides.
12. **Can synthetic keyed plug/socket meshes be loaded as SDF colliders?** Yes, via `create_tri_mesh_shape` + `ColliderType.SDF`. URDF boxes are the wrong path.
13. **Can the oracle baseline insert successfully at least once?** Yes. Earth and Moon oracles are 5/5.
14. **Is success measurable geometrically without relying on controller internals?** Yes (`lunarmbench.metrics`).
15. **Are contact points/forces a public API?** Partially. `QueryType.TOTAL_CONTACT_FORCE` and `CONTACT_POINTS` exist but are unsupported on static actors and articulated links.
16. **Can we log a meaningful insertion wrench on the receptacle?** Only after welding a dynamic socket to the world, and even then oracle peaks were often ~0 N. Do not base conclusions on force.
17. **Does pose translation uncertainty produce a robustness curve?** Yes: 0–2 mm succeed, 5 mm timeout, 10 mm misalignment (n=5 each).
18. **Does pose angular uncertainty produce a robustness curve?** Not with these POC thresholds; 1–5° all succeeded. Geometry, not the solver, is why.
19. **Is there an Earth vs Moon performance gap on the oracle?** Not a meaningful one with arm gravity disabled.
20. **Can trials be batched with YAML, CSV, manifests, and plots without overwriting?** Yes (`scripts/run_sweep.py`).
21. **Is reset deterministic enough for a POC?** Fixed-seed oracle succeeds twice with insertion depth within 5 mm; matrix seeds 0–4 were identical for nominal Earth/Moon.
22. **Can the task be wrapped as a Gymnasium env with privileged obs and Cartesian actions?** Yes, standalone, not `MochiEnv`. Reward is not scoring.
23. **Are shipped Lab envs relevant to dexterous insertion?** No. CartPole / Ant / HalfCheetah only.
24. **Are rods/tendons real enough for a later cable task?** Experimental APIs exist and step headlessly; asset paths are split; not task-ready.
25. **Should SuperDex be LunArmBench’s primary simulator?** No. Use it as a **B** specialized contact/deformable backend.

## Pointers

- Capability map: `docs/SUPERDEX_CAPABILITY_MAP.md`
- Design: `docs/DESIGN_DECISIONS.md`
- Limitations: `docs/LIMITATIONS.md`
- Cable: `docs/CABLE_FEASIBILITY.md`
- Matrix: `results/2026-08-27_033951_connector_v0/`
