"""Headless cable/rod/tendon smoke for the SuperDex POC.

This is recon, not a routing benchmark. Official examples gate their loops on
``physics.debugger.attach()``; this script bypasses the debugger.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PHYSICS_ASSETS = ROOT / "third_party" / "project_superdex" / "superdex_physics" / "assets"
os.environ["SUPERDEX_ASSETS_PATH"] = str(PHYSICS_ASSETS)


def _rod_spring(gravity: float, steps: int = 90) -> dict:
    import superdex.physics as physics
    from superdex.physics.paths import resolve_asset

    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("lunarmbench_rod_spring")
    scene.set_gravity([0.0, 0.0, -float(gravity)])

    radius = 1e-2
    youngs = 1e9
    shear = 1e9
    density = 1e3
    cube_size = 0.2
    area = math.pi * radius**2
    polar = 0.5 * math.pi * radius**4
    second = 0.25 * math.pi * radius**4
    torsion = 0.5 * math.pi * radius**4
    axial = youngs * area
    torsional = shear * torsion
    flexural = youngs * second

    helix_path = str(resolve_asset("rods/helix_with_visual.mochi.h5"))
    shape = physics.load_shape_from_file(helix_path, bake_scale=[1.0, 1.0, 1.0])
    rod = physics.experimental.create_rod_actor(
        scene,
        physics.experimental.RodActorParams(
            name="Spring",
            shape=shape,
            world_from_local=physics.TransformRT(),
            material=physics.experimental.RodMaterialParams(
                linear_density=density * area,
                linear_rotational_inertia=density * polar,
                axial_stiffness=axial,
                torsional_stiffness=torsional,
                flexural_stiffness=[flexural, flexural],
            ),
        ),
    )
    coordinates = list(rod.get_mesh().coordinates)
    num_nodes = len(coordinates) // 3
    last_node = num_nodes - 1
    last_element = num_nodes - 2
    near = coordinates[0:3]
    far = coordinates[-3:]
    pos_k = axial / 1.0
    rot_k = torsional / 1.0
    scene.create_deformable_node_position_constraint(
        actor=rod.get_handle(),
        node_index=0,
        position=near,
        stiffness=pos_k,
    )
    cube_shape = physics.load_shape_from_file(
        str(resolve_asset("cube/cube_mesh.mochi.json")),
        bake_scale=[cube_size, cube_size, cube_size],
    )
    cube = scene.create_rigid_actor(
        name="Mass",
        layer="Object",
        shape=cube_shape,
        density=density,
        collider_type=physics.ColliderType.BOX,
        world_from_local=physics.TransformRT(
            [far[0], far[1] - 0.5 * cube_size, far[2] - 0.5 * cube_size]
        ),
    )
    scene.create_deformable_node_to_rigid_constraint(
        deformable_actor=rod.get_handle(),
        rigid_actor=cube.get_handle(),
        deformable_node_index=last_node,
        fix_to_deformable_pos=True,
        stiffness=pos_k,
    )
    scene.create_rod_element_rotation_to_rigid_constraint(
        rigid_actor=cube.get_handle(),
        rod_actor=rod.get_handle(),
        element_index=last_element,
        ref_frame_rot_vec=[0.0, 0.0, 0.0],
        stiffness=rot_k,
    )
    z0 = float(cube.get_root_transform().translation[2])
    dt = 1.0 / 60.0
    for _ in range(steps):
        scene.step(dt)
    z1 = float(cube.get_root_transform().translation[2])
    physics.destroy_scene(scene)
    physics.shutdown()
    return {
        "gravity": gravity,
        "cube_z0": z0,
        "cube_z1": z1,
        "delta_z": z1 - z0,
        "num_rod_nodes": num_nodes,
        "helix_path": helix_path,
    }


def _guides_and_rod(gravity: float = 1.62, steps: int = 80) -> dict:
    """Tiny programmatic rod spanning two meshed guides under lunar g."""
    import superdex.physics as physics
    from superdex.physics.paths import resolve_asset

    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("lunarmbench_cable_guides")
    scene.set_gravity([0.0, 0.0, -float(gravity)])

    # Dynamic rigid actors require a surface mesh; create_sphere_shape is not enough.
    guide_shape = physics.load_shape_from_file(
        str(resolve_asset("cube/cube_mesh.mochi.json")),
        bake_scale=[0.04, 0.04, 0.04],
    )
    g0 = scene.create_rigid_actor(
        name="guide0",
        shape=guide_shape,
        is_static=False,
        has_gravity=False,
        collider_type=physics.ColliderType.BOX,
        world_from_local=physics.TransformRT(translation=[0.0, 0.0, 0.25]),
    )
    g1 = scene.create_rigid_actor(
        name="guide1",
        shape=guide_shape,
        is_static=False,
        has_gravity=False,
        collider_type=physics.ColliderType.BOX,
        world_from_local=physics.TransformRT(translation=[0.12, 0.0, 0.18]),
    )
    for actor, pos in ((g0, [0.0, 0.0, 0.25]), (g1, [0.12, 0.0, 0.18])):
        scene.create_rigid_pivot_position_constraint(
            stiffness=5.0e5,
            damping=5.0e3,
            saturation=1.0e5,
            target_position=pos,
            local_position=[0.0, 0.0, 0.0],
            actor=actor.get_handle(),
        )
    start = np.array([0.0, 0.0, 0.25], dtype=np.float32)
    end = np.array([0.12, 0.0, 0.18], dtype=np.float32)
    n_elem = 24
    t = np.linspace(0.0, 1.0, n_elem + 1, dtype=np.float32)[:, None]
    nodes = start + t * (end - start)
    axes = np.tile([0.0, 1.0, 0.0], (n_elem, 1)).astype(np.float32)
    radius = 0.004
    model = physics.experimental.generate_tubular_rod_model_data(
        nodes=nodes,
        element_frame_axes=axes,
        radius=radius,
        num_cross_section_segments=6,
        is_closed_loop=False,
    )
    shape = physics.create_model_shape(model)
    area = math.pi * radius**2
    rod = physics.experimental.create_rod_actor(
        scene,
        physics.experimental.RodActorParams(
            name="CableSketch",
            shape=shape,
            world_from_local=physics.TransformRT(),
            material=physics.experimental.RodMaterialParams(
                linear_density=1.0e3 * area,
                linear_rotational_inertia=1.0e3 * 0.5 * math.pi * radius**4,
                axial_stiffness=1.0e7 * area,
                torsional_stiffness=1.0e7 * 0.5 * math.pi * radius**4,
                flexural_stiffness=[
                    1.0e7 * 0.25 * math.pi * radius**4,
                    1.0e7 * 0.25 * math.pi * radius**4,
                ],
            ),
        ),
    )
    coords0 = np.array(list(rod.get_mesh().coordinates), dtype=float)
    n_nodes = len(coords0) // 3
    scene.create_deformable_node_position_constraint(
        actor=rod.get_handle(),
        node_index=0,
        position=list(start),
        stiffness=1.0e4,
    )
    # Do not also weld node 0 to g0: double constraints on the same rod node segfaulted.
    scene.create_deformable_node_to_rigid_constraint(
        deformable_actor=rod.get_handle(),
        rigid_actor=g1.get_handle(),
        deformable_node_index=n_nodes - 1,
        rigid_local_pos=[0.0, 0.0, 0.0],
        fix_to_deformable_pos=False,
        stiffness=1.0e4,
    )
    for _ in range(steps):
        scene.step(1.0 / 60.0)
    coords1 = np.array(list(rod.get_mesh().coordinates), dtype=float)
    z_end0 = float(coords0[-1])
    z_end1 = float(coords1[-1])
    guide_names = [g0.get_name(), g1.get_name()]
    physics.destroy_scene(scene)
    physics.shutdown()
    return {
        "gravity": gravity,
        "n_nodes": n_nodes,
        "end_z0": z_end0,
        "end_z1": z_end1,
        "sag": z_end1 - z_end0,
        "guides": guide_names,
    }


def _tendon_prefab(steps: int = 40) -> dict:
    import superdex.physics as physics
    from superdex.physics.paths import resolve_asset, resolve_asset_root

    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("lunarmbench_tendon")
    scene.set_gravity([0.0, 0.0, -1.62])
    prefab_rel = "samples/tendon_comparison_articulation.mochi_scene"
    prefab = physics.prefab.load_from_file(
        prefab_path=str(resolve_asset(prefab_rel)),
        root_path=str(resolve_asset_root(prefab_rel)),
    )
    result = physics.prefab.add_to_scene(
        prefab=prefab,
        scene=scene,
        params=physics.prefab.PrefabParams(
            name="TendonArt",
            translation=[-0.5, 0.0, -1.0],
            apply_scene_settings=False,
        ),
    )
    arts = result.filter(physics.ActorType.ARTICULATED)
    actor = arts[0]
    info = actor.get_articulated_shape_info()
    link_indices = {name: i for i, name in enumerate(info.link_names)}
    elements = [
        physics.RoutingElement(
            type=physics.RoutingElementType.WAYPOINT,
            index=link_indices[name],
            local_position=[0.0, 0.0, 0.0],
        )
        for name in ("Slider", "Eyelet0", "Eyelet1", "Eyelet2", "Eyelet3")
        if name in link_indices
    ]
    tendon_index = physics.experimental.add_spatial_tendon(
        actor,
        physics.experimental.SpatialTendonParams(routing_elements=elements),
    )
    for _ in range(steps):
        scene.step(1.0 / 60.0)
    physics.destroy_scene(scene)
    physics.shutdown()
    return {
        "prefab": prefab_rel,
        "n_articulated": len(arts),
        "n_links": len(info.link_names),
        "tendon_index": int(tendon_index),
        "n_waypoints": len(elements),
        "steps": steps,
    }


def main() -> int:
    import subprocess

    report: dict = {
        "physics_assets": str(PHYSICS_ASSETS),
        "assets_exist": PHYSICS_ASSETS.exists(),
    }
    errors: list[str] = []
    jobs = (
        ("rod_spring_earth", "_rod_spring", {"gravity": 9.81}),
        ("rod_spring_moon", "_rod_spring", {"gravity": 1.62}),
        ("guides_rod_moon", "_guides_and_rod", {"gravity": 1.62}),
        ("spatial_tendon", "_tendon_prefab", {}),
    )
    # initialize/shutdown is not re-entrant; run each case in a child process.
    for name, fn, kwargs in jobs:
        payload = json.dumps(kwargs)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json, scripts.cable_feasibility as c; "
                    f"print(json.dumps(c.{fn}(**json.loads({payload!r})), default=str))"
                ),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT), "SUPERDEX_ASSETS_PATH": str(PHYSICS_ASSETS)},
        )
        if proc.returncode != 0:
            errors.append(name)
            report[name] = {"error": proc.stderr[-2500:], "stdout": proc.stdout[-1000:]}
        else:
            report[name] = json.loads(proc.stdout)
    report["errors"] = errors
    print(json.dumps(report, indent=2, default=str))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
