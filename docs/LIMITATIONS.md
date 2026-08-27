# Limitations

Honest constraints discovered while running SuperDex 1.0.0 headlessly for Lunar Connector Insertion V0.

## Control and gravity

- `BASIC_OSC_PD` and `BASIC_JSC_PD` have **no gravity compensation**. Cartesian tracking on a fully gravitated FR3 sags. This spike turns gravity off on `fr3_*` links only. Gripper/plug mass still couples to `scene` gravity, so Earth vs Moon is not a clean A/B on the same closed-loop plant.
- Default `physics.DEFAULT_GRAVITY` is Y-down `[0,-9.8,0]`. Robotics examples are Z-up. Every scene in this repo sets gravity explicitly.

## Contact queries

- Static actors and articulated links do **not** support `TOTAL_CONTACT_FORCE` / `CONTACT_POINTS` even when contact is happening.
- Peak socket force on many oracle successes was ~0 N. Do not treat the force column as a calibrated wrench log. Geometric metrics (depth, lateral, orientation) are the success definition.
- There is no public per-contact impulse API beyond `ContactPoint` on actors that support `CONTACT_POINTS`.

## Geometry and uncertainty

- Clearance is intentionally large (1.5 mm/side; success lateral 4 mm). The angular sweep (1–5°) therefore did **not** stress the key: 5° over ~18 mm of insertion is ~1.6 mm of lateral drift, inside the success band. That is a POC parameterization issue, not evidence that SuperDex is rotation-robust.
- Translation 5 mm timed out (rim contact without reaching depth); 10 mm terminated as misalignment. Taxonomy depends on whether the socket query reports contact; with near-zero forces, some rim events classify as `timeout`.

## Lab / RL

- Lab is early preview. Shipped Gym envs are CartPole / Ant / HalfCheetah.
- `MochiEnv` is not a drop-in for a custom Robotics insertion scene.
- `physics.initialize` / `shutdown` is not re-entrant. Vectorized PPO in one process against this task is a sink; it was skipped.
- HybridVectorEnv scene sharing assumes sequential stepping.

## Headless / rendering

- Official examples exit immediately if `physics.debugger.attach()` fails. Headless code must not copy that pattern.
- No GPU. No Studio. No photoreal Moon. Demo artifacts are CSV traces and matplotlib PNGs, not on-policy video.
- `rgb_array` rendering exists on `MochiEnv` via Polyscope; it was not wired into the connector env.

## Assets and authoring

- Tendon/rod example files live under `superdex_physics/assets`, not the main `assets/` tree. A single `SUPERDEX_ASSETS_PATH` does not cover both.
- URDF box/sphere/cylinder collision primitives are ignored; meshes bake SDFs. Procedural `create_tri_mesh_shape` is the reliable path for synthetic fixtures.
- Destroying a bot or scene and then querying its actors can segfault.

## Determinism

- Fixed-seed oracle Moon insertions matched to ~5 mm on insertion depth across two process-local runs, and Earth/Moon oracles were bitwise-identical across the five seeds in the matrix (home pose is deterministic). This is **not** a claim of bitwise reproducibility across machines or SuperDex versions.
- Combined-uncertainty trials use `numpy` RNGs from the YAML seed; SuperDex internals may add extra noise.

## What this spike is not

A NASA connector, a cable-routing benchmark, a trained insertion policy, or a recommendation to make SuperDex the only LunArmBench simulator.
