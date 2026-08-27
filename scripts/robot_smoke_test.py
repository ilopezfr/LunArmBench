"""Instantiate FR3+2F-85 and step a few headless control cycles."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "SUPERDEX_ASSETS_PATH", str(ROOT / "third_party" / "project_superdex" / "assets")
)


def main() -> int:
    import numpy as np
    import superdex.physics as physics
    import superdex.robotics as robotics
    from superdex.physics.paths import resolve_asset

    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("robot_smoke")
    scene.set_gravity([0.0, 0.0, -1.62])
    bot_prefab = robotics.load_bot_prefab_from_file(
        str(resolve_asset("bots/arm_hand_combos/fr3_v2_2f_85/fr3_v2_2f_85.superdex_bot"))
    )
    ctx = robotics.create_context()
    bot = robotics.create_bot(scene, bot_prefab, ctx)
    actor = bot.get_articulated_actor()
    plane = physics.create_plane_shape(normal=[0, 0, 1], distance=0)
    scene.create_rigid_actor(name="ground", shape=plane, is_static=True)

    osc = bot.create_controller("BASIC_OSC_PD")
    bot_name = bot.get_name()
    osc.initialize(f"{bot_name}/fr3_link0", f"{bot_name}/fr3_link8")
    params = osc.get_params()
    params.kp_p = 900.0
    params.kd_p = 75.0
    params.kp_r = 30.0
    params.kd_r = 3.0
    params.max_translation_error = 0.05
    params.max_rotation_error = 0.4
    osc.set_params(params)

    obsv = osc.get_current_observations_from_mochi()
    world_from_root = obsv.world_from_root
    current = world_from_root.inverse() * obsv.world_from_ee_link
    num_dofs = actor.get_num_dofs()
    all_dof_indices = np.arange(num_dofs, dtype=np.int32)
    for _ in range(10):
        obsv = osc.get_current_observations_from_mochi()
        tau = np.asarray(
            osc.compute_output(
                obsv,
                robotics.ControllerBasicOscPdTarget(root_from_target_ee=current),
            ),
            dtype=np.float32,
        )
        actor.set_external_forces_on_dofs(dof_indices=all_dof_indices, force_values=tau)
        scene.step(1.0 / 200.0)

    report = {
        "bot": bot.get_name(),
        "dofs": num_dofs,
        "gravity": list(scene.get_gravity()),
        "held_pose_steps": 10,
        "world_from_root": list(world_from_root.translation),
        "headless": True,
        "debugger_attached": False,
    }
    robotics.destroy_bot(scene, bot)
    physics.destroy_scene(scene)
    physics.shutdown()
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
