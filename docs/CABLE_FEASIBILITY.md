# Cable / tendon / rod feasibility

Phase 9 optional recon. This is **not** a routing benchmark.

## What SuperDex actually exposes

Inspected on `superdex==1.0.0`:

- `physics.experimental.create_rod_actor` + `RodActorParams` / `RodMaterialParams`
- `physics.experimental.generate_tubular_rod_model_data` (polyline → tubular visual mesh)
- `scene.create_deformable_node_position_constraint`
- Dynamic rigid actors require a **surface mesh**. `create_sphere_shape` is rejected (`The shape must have a surface mesh`). The guide sketch uses the official `cube/cube_mesh.mochi.json` asset.
- Combining a `deformable_node_position_constraint` and a `deformable_node_to_rigid_constraint` on the **same rod node** segfaulted in this spike. Pin one end, weld the other.
- `scene.create_rod_element_rotation_to_rigid_constraint`
- `physics.experimental.add_spatial_tendon` + `RoutingElementType.WAYPOINT`
- `physics.experimental.add_linear_transmission`
- `ActorType.ROD` / `SHELL` / `SOFT`

Official examples (GUI-gated on `debugger.attach()`):

- `superdex_physics/examples/example_mass_on_rod_spring.py`
- `superdex_physics/examples/example_tendon_comparison.py`

## Asset-path trap

Those examples call `superdex.physics.paths.resolve_asset`. The files they need are under **`third_party/project_superdex/superdex_physics/assets/`**:

- `rods/helix_with_visual.mochi.h5`
- `cube/cube_mesh.mochi.json`
- `samples/tendon_comparison_articulation.mochi_scene`

They are **not** in the main robotics `assets/` tree used by FR3. Pointing `SUPERDEX_ASSETS_PATH` at the robotics tree makes the tendon example fail with a missing `.mochi_scene`. Cable recon must switch the env var (see `scripts/cable_feasibility.py`).

## Headless smokes

`python scripts/cable_feasibility.py` runs four child processes (initialize/shutdown is not re-entrant). On this machine, all four returned 0:

1. Official helix rod + hanging cube, Earth g = 9.81. 129 nodes; cube Δz ≈ −1.18 m after 90 frames (transient, not equilibrium).
2. Same, Moon g = 1.62. Cube Δz ≈ −1.28 m after 90 frames. **Not** an equilibrium sag comparison — do not treat Earth vs Moon here as a cable metric.
3. Programmatic 24-element rod between two meshed, world-welded cube guides under lunar g (25 nodes; ends stay pinned).
4. Tendon-comparison prefab + `add_spatial_tendon` through Slider/Eyelet waypoints (9 links, 5 waypoints, 40 steps, lunar g).

JSON: `results/cable_feasibility.json`.

## What this does **not** prove

- Cable-through-guides as a LunArmBench task.
- Tendon friction over eyelets under lunar dust.
- Coupling a rod to the FR3+2F-85 insertion scene.
- Stability of visual-mesh contact (`use_visual_mesh_contact=True` in the official tendon rod) at insertion-scale radii.

## Recommendation for cables

Rods and spatial tendons are **real experimental APIs**, not vapor. They are viable for a later specialized backend study if LunArmBench wants a cable-through-guides task. They are the wrong next step until the rigid insertion task's contact-query and gravity-compensation gaps are understood.

Do not build a routing benchmark on SuperDex 1.0.0 Lab.

## PPO / RL

Skipped. Reasons:

- Custom env is standalone Gymnasium, not `MochiEnv`.
- `initialize`/`shutdown` is not re-entrant; reset tears the whole physics runtime down.
- No RLlib/PPO extra in `pyproject.toml`.
- The spike's success criterion is a measurable insertion experiment, not a trained policy.

A one-off PPO smoke would have been a sink.
