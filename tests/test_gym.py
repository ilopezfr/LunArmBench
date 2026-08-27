"""Gymnasium wrapper smoke (requires SuperDex)."""

import os

import pytest

from lunarmbench.paths import DEFAULT_ASSETS


pytestmark = pytest.mark.skipif(
    not DEFAULT_ASSETS.exists() and not os.environ.get("SUPERDEX_ASSETS_PATH"),
    reason="SuperDex assets not available",
)


def test_gym_reset_step_rereset():
    os.environ.setdefault("SUPERDEX_ASSETS_PATH", str(DEFAULT_ASSETS))
    from lunarmbench.environments.lunar_connector_env import LunarConnectorInsertionEnv

    env = LunarConnectorInsertionEnv(config="nominal_moon.yaml", max_steps=5)
    try:
        obs, info = env.reset(seed=0)
        assert obs.shape == env.observation_space.shape
        action = env.action_space.sample()
        obs2, reward, terminated, truncated, info = env.step(action)
        assert obs2.shape == obs.shape
        assert "benchmark_success" in info
        assert "metrics" in info
        obs3, _ = env.reset(seed=1)
        assert obs3.shape == obs.shape
    finally:
        env.close()
