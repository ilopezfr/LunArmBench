"""Headless SuperDex install verification for the LunArmBench POC."""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "third_party" / "project_superdex" / "assets"
os.environ.setdefault("SUPERDEX_ASSETS_PATH", str(ASSETS))


def fingerprint() -> dict:
    import superdex.physics as physics
    import superdex.robotics as robotics  # noqa: F401
    import superdex.lab.gym  # noqa: F401

    try:
        import importlib.metadata as md

        versions = {
            name: md.version(name)
            for name in (
                "superdex",
                "superdex-physics",
                "superdex-robotics",
                "superdex-lab",
                "numpy",
                "gymnasium",
            )
        }
    except Exception as exc:  # pragma: no cover
        versions = {"error": str(exc)}

    sha_path = ROOT / "third_party" / "project_superdex"
    superdex_sha = ""
    if (sha_path / ".git").exists():
        import subprocess

        superdex_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=sha_path, text=True
        ).strip()

    return {
        "os": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": sys.version,
        "python_executable": sys.executable,
        "superdex_commit": superdex_sha,
        "superdex_assets_path": os.environ.get("SUPERDEX_ASSETS_PATH"),
        "precision": os.environ.get("SUPERDEX_PRECISION", "single (default)"),
        "gpu": "none (not required)",
        "package_versions": versions,
        "physics_uses_double": physics.uses_double_precision(),
    }


def physics_smoke() -> dict:
    import numpy as np
    import superdex.physics as physics

    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("lunarmbench_physics_smoke")
    scene.set_gravity([0.0, 0.0, -9.81])
    g = list(scene.get_gravity())
    half = 0.05
    coordinates = np.array(
        [
            [-half, -half, -half],
            [half, -half, -half],
            [half, half, -half],
            [-half, half, -half],
            [-half, -half, half],
            [half, -half, half],
            [half, half, half],
            [-half, half, half],
        ],
        dtype=np.float32,
    ).flatten()
    connectivity = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 4, 7],
            [0, 7, 3],
            [1, 2, 6],
            [1, 6, 5],
            [0, 1, 5],
            [0, 5, 4],
            [2, 3, 7],
            [2, 7, 6],
        ],
        dtype=np.int32,
    ).flatten()
    cube = physics.create_tri_mesh_shape(coordinates=coordinates, connectivity=connectivity)
    actor = scene.create_rigid_actor(
        name="cube",
        shape=cube,
        is_static=False,
        density=1000.0,
        world_from_local=physics.TransformRT(translation=[0.0, 0.0, 0.5]),
        collider_type=physics.ColliderType.BOX,
    )
    z0 = float(actor.get_root_transform().translation[2])
    for _ in range(30):
        scene.step(1.0 / 60.0)
    z1 = float(actor.get_root_transform().translation[2])
    physics.destroy_scene(scene)
    physics.shutdown()
    return {
        "gravity": g,
        "cube_z_start": z0,
        "cube_z_after": z1,
        "fell": z1 < z0 - 0.01,
    }


def robotics_smoke() -> dict:
    import superdex.physics as physics
    import superdex.robotics as robotics
    from superdex.physics.paths import resolve_asset

    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("lunarmbench_robotics_smoke")
    scene.set_gravity([0.0, 0.0, -1.62])
    bot_prefab = robotics.load_bot_prefab_from_file(
        str(resolve_asset("bots/arm_hand_combos/fr3_v2_2f_85/fr3_v2_2f_85.superdex_bot"))
    )
    ctx = robotics.create_context()
    bot = robotics.create_bot(scene, bot_prefab, ctx)
    actor = bot.get_articulated_actor()
    plane = physics.create_plane_shape(normal=[0, 0, 1], distance=0)
    scene.create_rigid_actor(name="ground", shape=plane, is_static=True)
    link_names = []
    for handle in actor.get_nested_link_actors():
        link = scene.get_actor(handle)
        if link is not None:
            link_names.append(link.get_name())
    t0 = time.perf_counter()
    for _ in range(20):
        scene.step(1.0 / 200.0)
    dt = time.perf_counter() - t0
    result = {
        "bot_name": bot_prefab.name,
        "num_dofs": int(actor.get_num_dofs()),
        "num_links": len(link_names),
        "link_names_sample": link_names[:8],
        "has_gripper_base": any(n.endswith("2f_85_base_link") for n in link_names),
        "headless_steps": 20,
        "wall_clock_s": dt,
    }
    robotics.destroy_bot(scene, bot)
    physics.destroy_scene(scene)
    physics.shutdown()
    return result


def lab_smoke() -> dict:
    from superdex.lab.gym.envs.benchmarks.cartpole_env import CartPoleEnv, CartPoleEnvCfg

    env = CartPoleEnv(CartPoleEnvCfg(render_mode=None))
    try:
        env.reset()
        env.step(env.action_space.sample())
    finally:
        env.close()
    return {"cartpole": "ok", "render_mode": None}


def main() -> int:
    import subprocess

    report = {"fingerprint": fingerprint()}
    errors: list[str] = []
    # SuperDex initialize/shutdown is not reliably re-entrant in one process.
    # Run each smoke in a child interpreter.
    for name in ("physics_smoke", "robotics_smoke", "lab_smoke"):
        proc = subprocess.run(
            [sys.executable, "-c", f"import json,scripts.verify_install as v; print(json.dumps(v.{name}(), default=str))"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        if proc.returncode != 0:
            errors.append(f"{name}: rc={proc.returncode} stderr={proc.stderr[-2000:]}")
            report[name] = {"error": proc.stderr[-2000:], "stdout": proc.stdout[-1000:]}
        else:
            report[name] = json.loads(proc.stdout)
    report["errors"] = errors
    print(json.dumps(report, indent=2, default=str))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
