"""Scene reset sanity (requires SuperDex)."""

import os

import pytest

from lunarmbench.config import load_config
from lunarmbench.paths import DEFAULT_ASSETS
from lunarmbench.scene import build_scene, teardown
from lunarmbench.task import run_episode


pytestmark = pytest.mark.skipif(
    not DEFAULT_ASSETS.exists() and not os.environ.get("SUPERDEX_ASSETS_PATH"),
    reason="SuperDex assets not available",
)


def test_reset_no_initial_nan():
    os.environ.setdefault("SUPERDEX_ASSETS_PATH", str(DEFAULT_ASSETS))
    cfg = load_config("nominal_moon.yaml", seed=1)
    built = build_scene(cfg)
    try:
        t = built.plug.get_root_transform().translation
        assert all(abs(float(x)) < 10 for x in t)
        s = built.socket.get_root_transform().translation
        # Mouth is in front of the robot, not at the origin.
        assert abs(float(s[0])) + abs(float(s[2])) > 0.1
    finally:
        teardown(built)


def test_seed_consistency_and_nominal_success():
    os.environ.setdefault("SUPERDEX_ASSETS_PATH", str(DEFAULT_ASSETS))
    a = run_episode(load_config("nominal_moon.yaml", seed=3), oracle=True, config_name="t")
    b = run_episode(load_config("nominal_moon.yaml", seed=3), oracle=True, config_name="t")
    assert a.success and b.success
    assert abs(a.insertion_depth - b.insertion_depth) < 5e-3
