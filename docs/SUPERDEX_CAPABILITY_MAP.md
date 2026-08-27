# SuperDex capability map (inspected APIs)

Source of truth for this document: SuperDex `stable` commit `1d7150946fa3f3d3fb09c2bff07eaa138cbfdee6`, wheels `superdex==1.0.0` on Python 3.12 Linux x86_64, plus `dir()` / enum members / official examples. Inference is labeled as such.

## Packages

| Import | Status on this machine |
|---|---|
| `superdex.physics` | Works headlessly. `physics.initialize(num_worker_threads=0)` then `create_scene` / `scene.step`. |
| `superdex.robotics` | Works. `load_bot_prefab_from_file`, `create_context`, `create_bot`, `Bot.create_controller`. |
| `superdex.lab.gym` | Import works. Shipped Gym ids live under `superdex_gym/`. |
| `superdex.studio` | Installed (`superdex-studio` entry point). **Not used.** Headless POC does not launch Studio. |

`physics.initialize()` / `shutdown()` is **not reliably re-entrant** in one process. Install smokes and the cable recon therefore spawn child interpreters.

Do not query actors after `robotics.destroy_bot` **or** `physics.destroy_scene` — observed segfault (the cable-guide sketch hit this on `Actor.get_name()` after teardown).

## Coordinate frames and gravity

- Robotics examples document **Z-up / FLU** and call `scene.set_gravity([0, 0, -g])`.
- `physics.DEFAULT_GRAVITY` on this wheel is `[0, -9.8, 0]` (Y-down). A scene created with no override is **not** lunar/Earth Z-up.
- Round-trip verified: `set_gravity([0,0,-9.81])` and `set_gravity([0,0,-1.62])` both report back correctly (`scripts/gravity_sanity.py`).
- `Actor` / `BotLinkPrefab` have `has_gravity`. Official OSC examples set `has_gravity=False` on every arm link because `BASIC_OSC_PD` has no gravity term.

## Robots and prefabs

Asset root is `SUPERDEX_ASSETS_PATH` (this POC: `third_party/project_superdex/assets`).

Inspected shipped arm/hand combos under `assets/bots/arm_hand_combos/`:

- `fr3_v2_2f_85` — used here. Instantiates as 13 DoF, 20 links, including `2f_85_base_link`.
- `fr3_v2_allegro_v5/right`
- `fr3_dg5f_short` left/right and `fr3_dg5f_short_seed/right`
- `openarm_v20` and `openarm_v20_wuji`

Insertion-fixture authoring references (not used as the V0 geometry):

- `assets/prefabs/nine_hole_peg_test`
- `assets/prefabs/functional_dexterity_test`

`physics.prefab.load_from_file` / `add_to_scene` exist. Robotics bots use `robotics.load_bot_prefab_from_file`.

URDF primitive collision shapes are silently ignored (SuperDex docs / this spike's prior recon). Meshes (STL/OBJ/PLY) bake SDFs at load. This POC generates triangle meshes procedurally via `physics.create_tri_mesh_shape(coordinates, connectivity)`. There is **no** `create_box_shape`; boxes are `ColliderType.BOX` on a mesh or `create_sphere_shape` / `create_plane_shape` / `create_tet_mesh_shape` / `create_model_shape`.

## Controllers (Robotics)

`Bot.create_controller(type_name)` inspected via official examples:

| Type string | Role |
|---|---|
| `BASIC_OSC_PD` | Cartesian task-space PD. No gravity term. Target: `ControllerBasicOscPdTarget(root_from_target_ee=...)`. Observations: `world_from_root`, `world_from_ee_link` (not `root_from_ee`). |
| `BASIC_JSC_PD` | Joint-space PD. Also no gravity term (example comment). |
| `MOCHI_ARTICULATED_POSE` | Pose controller used with `physics.experimental.create_ik_solver`. |

This POC uses `BASIC_OSC_PD` on `fr3_link0` → `fr3_link8`. Torques are applied with `actor.set_external_forces_on_dofs`.

IK exists as `physics.experimental.create_ik_solver` / `destroy_ik_solver`. Not used for Baseline 0.

## Joints and held objects

`ArticulatedJointType`: `HARD`, `REVOLUTE`, `PRISMATIC`, `SPHERICAL`, `FREE`, `CYCLE`, `INVALID`.

A `HARD` joint on `BotJointPrefab` welds a child `BotLinkPrefab`. Used to hold the plug on `2f_85_base_link` at `plug_offset_z=0.155` m. `BotContactOverride(link_a, link_b, enable=False)` disables plug–finger collisions.

World welds for free rigid bodies: `scene.create_rigid_pivot_position_constraint` and `create_rigid_pivot_rotation_constraint`. `create_deformable_node_to_rigid_constraint` rejects static rigid actors (`Invalid rigid actor type`); the other body must be dynamic.

## Contact

`QueryType` members actually present:

- `TOTAL_CONTACT_FORCE`
- `CONTACT_POINTS`
- `NODE_CONTACT_FORCES`
- `CONSTRAINT_FORCE`
- `ARTICULATED_CONTROLLER_FORCE`
- `SDF_DISTANCES`
- plus deformable/visual queries (`NODE_POSITIONS`, `ELASTIC_ENERGY`, …)

Public `Actor` methods used:

- `is_query_supported(QueryType)`
- `register_query(QueryType)`
- `get_contact_force_world()`, `get_contact_torque_world()`, `get_contact_points_world()`
- `get_contact_force_from_actor_world`, `get_node_contact_forces_world`

**Support is actor-kind specific (measured, not assumed):**

| Actor | `TOTAL_CONTACT_FORCE` | `CONTACT_POINTS` |
|---|---|---|
| Dynamic rigid SDF (welded socket) | supported | supported |
| Static rigid SDF / plane | **not supported** (physics still collides; a cube still rests on a table) | **not supported** |
| Articulated plug link | **not supported** | **not supported** |

`physics.experimental.get_contact_force_world_batch` exists; not used.

`ContactParams` includes `coulomb_friction_coefficient` and `penalty_coefficient`. `ColliderType.SDF` is what this task uses for plug and socket meshes.

Contact-force plots in the matrix should be read with this gap in mind. Peak force on oracle successes was often ~0 N because the query is on the welded socket and many insertions barely load it, and because articulated-link forces are unavailable.

## Headless stepping and recording

Official Physics/Robotics examples gate the loop on `physics.debugger.attach()` (GUI). Headless must call `scene.step(dt)` directly and skip the debugger.

`Scene.start_recording` / `stop_recording` / `is_recording` and `RecordingParams` exist. This spike did **not** produce an MP4 (no GPU, debugger GUI unused; `.mp4` gitignored). Demo artifacts are 2-D traces/PNG.

`MochiEnv` render modes: `None`, `"human"` (Polyscope), `"rgb_array"`. Viewer default coordinate system is Polyscope Y-up, not robotics Z-up.

## Lab / Gym

Filesystem discovery in `superdex.lab.gym.utils.env_discovery` scans `superdex.lab.gym.envs.benchmarks` and `...envs.robots`. Shipped, registered envs on this wheel: **CartPole, Ant, HalfCheetah** (`superdex_gym/<Name>-v0`). No dexterous insertion env.

Custom env base: `superdex.lab.gym.envs.mochi_env.MochiEnv` + `MochiEnvCfg`. It assumes Lab `SceneManager`, optional scene sharing (`use_shared_scenes`), and `HybridVectorEnv` sequential stepping. Wrapping the connector task in `MochiEnv` was not necessary for the spike; the POC env is a standalone `gymnasium.Env` that reuses `lunarmbench.scene`.

CartPole headless (`render_mode=None`) reset/step/close succeeded.

## Vectorization

No first-class `num_envs` on `physics.Scene`. Lab documents `HybridVectorEnv` + shared scenes with the assumption that vectorized envs in one process are **stepped sequentially**. Combined with non-re-entrant `initialize`/`shutdown`, this is a poor PPO substrate for a custom Robotics task.

## Deformables, rods, tendons

`ActorType`: `RIGID`, `ARTICULATED`, `ROD`, `SHELL`, `SOFT`.

`physics.experimental` includes:

- `create_rod_actor`, `RodActorParams`, `RodMaterialParams`, `generate_tubular_rod_model_data`
- `add_spatial_tendon`, `SpatialTendonParams`, `RoutingElement` / `RoutingElementType.WAYPOINT`
- `add_linear_transmission`
- `create_shell_actor`, `create_soft_actor`
- McKibben / displacement / force actuators

Official examples:

- `superdex_physics/examples/example_mass_on_rod_spring.py`
- `superdex_physics/examples/example_tendon_comparison.py`

Those examples resolve assets under **`superdex_physics/assets`** (`rods/helix_with_visual.mochi.h5`, `samples/tendon_comparison_articulation.mochi_scene`), **not** the main robotics `assets/` tree. Pointing `SUPERDEX_ASSETS_PATH` at the robotics tree makes the tendon example fail with a missing scene file.

See [`CABLE_FEASIBILITY.md`](CABLE_FEASIBILITY.md).

## Precision and GPU

- Default precision: single (`physics.uses_double_precision() == False`, `PRECISION_NAME == "single"`).
- `SUPERDEX_PRECISION` unset in this spike. Contact was stable enough at 200 Hz that double was not required.
- No GPU on the spike machine. `scene.use_gpu` was not needed. Physics CPU stepping of the FR3 scene ran at ~4× real time for ~1.4 s insertions.
