"""Gymnasium wrapper around Lunar Connector Insertion V0.

Benchmark scoring stays in lunarmbench.metrics; this reward is a training signal only.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from lunarmbench.config import TaskConfig, load_config
from lunarmbench.controllers import desired_ee_for_plug, osc_step
from lunarmbench.metrics import insertion_metrics, is_success
from lunarmbench.paths import ensure_assets_path
from lunarmbench.scene import BuiltScene, build_scene, teardown
from lunarmbench.transforms import translation_of


class LunarConnectorInsertionEnv(gym.Env):
    """Privileged-state Cartesian insertion environment.

    Observation: joints, EE xyz, plug xyz, estimated socket xyz, relative xyz, previous action.
    Action: delta end-effector position (m) and rotation vector (rad).
    """

    metadata = {"render_modes": []}

    def __init__(self, config: str | TaskConfig = "nominal_moon.yaml", max_steps: int = 400):
        super().__init__()
        ensure_assets_path()
        self.cfg = config if isinstance(config, TaskConfig) else load_config(config)
        self.max_steps = max_steps
        self.built: BuiltScene | None = None
        self._step_count = 0
        self._prev_action = np.zeros(6, dtype=np.float32)
        self.action_space = spaces.Box(low=-0.02, high=0.02, shape=(6,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(7 + 3 + 3 + 3 + 3 + 6,), dtype=np.float32)

    def _obs(self) -> np.ndarray:
        assert self.built is not None
        pose = np.zeros(self.built.bot_actor.get_num_dofs(), dtype=np.float32)
        self.built.bot_actor.get_articulated_pose(pose)
        arm = pose[:7]
        ee = np.asarray(self.built.osc.get_current_observations_from_mochi().world_from_ee_link.translation, dtype=np.float32)
        plug = np.asarray(self.built.plug.get_root_transform().translation, dtype=np.float32)
        sock = np.asarray(self.built.socket.get_root_transform().translation, dtype=np.float32)
        rel = plug - sock
        return np.concatenate([arm, ee, plug, sock, rel, self._prev_action]).astype(np.float32)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        if self.built is not None:
            teardown(self.built)
            self.built = None
        if seed is not None:
            self.cfg.seed = int(seed)
        self.built = build_scene(self.cfg, rng=np.random.default_rng(self.cfg.seed))
        self._step_count = 0
        self._prev_action[:] = 0
        return self._obs(), {}

    def step(self, action):
        assert self.built is not None
        action = np.asarray(action, dtype=np.float32).reshape(6)
        self._prev_action = action
        import superdex.physics as physics

        obsv = self.built.osc.get_current_observations_from_mochi()
        ee = obsv.world_from_ee_link
        new_t = translation_of(ee) + action[:3]
        rv = np.asarray(ee.rotation.to_rotation_vector(), dtype=float) + action[3:]
        target = physics.TransformRT(
            rotation=physics.Quaternion.from_rotation_vector(list(rv)),
            translation=list(new_t),
        )
        osc_step(self.built, target)
        self.built.scene.step(self.cfg.sim_dt)
        self._step_count += 1
        metrics = insertion_metrics(self.built.plug, self.built.socket, self.cfg.geometry)
        success = is_success(metrics, self.cfg.geometry)
        timed_out = self._step_count >= self.max_steps
        terminated = bool(success)
        truncated = bool(timed_out and not success)
        # Training reward only — not the benchmark definition.
        reward = (
            float(metrics["insertion_depth"])
            - 2.0 * float(metrics["lateral_error"])
            - 0.5 * float(metrics["orientation_error"])
            - 0.01 * float(np.linalg.norm(action))
            + (10.0 if success else 0.0)
        )
        info = {"metrics": metrics, "success": success, "benchmark_success": success}
        return self._obs(), reward, terminated, truncated, info

    def close(self):
        if self.built is not None:
            teardown(self.built)
            self.built = None


def register_env() -> None:
    env_id = "LunArmBench/LunarConnectorInsertion-v0"
    if env_id in gym.envs.registry:
        return
    gym.register(
        id=env_id,
        entry_point="lunarmbench.environments.lunar_connector_env:LunarConnectorInsertionEnv",
    )
