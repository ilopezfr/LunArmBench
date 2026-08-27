"""Fixed-seed initialization should not collide plug and socket."""

import os

import pytest

from lunarmbench.config import load_config
from lunarmbench.geometry import ConnectorGeometry
from lunarmbench.metrics import insertion_metrics
from lunarmbench.paths import DEFAULT_ASSETS
from lunarmbench.scene import build_scene, teardown


pytestmark = pytest.mark.skipif(
    not DEFAULT_ASSETS.exists() and not os.environ.get("SUPERDEX_ASSETS_PATH"),
    reason="SuperDex assets not available",
)


def test_no_start_collision_and_reachable():
    os.environ.setdefault("SUPERDEX_ASSETS_PATH", str(DEFAULT_ASSETS))
    cfg = load_config("nominal_moon.yaml", seed=0)
    built = build_scene(cfg)
    try:
        m = insertion_metrics(built.plug, built.socket, cfg.geometry)
        assert m["insertion_depth"] < 0.0  # tip still outside the mouth
        assert m["lateral_error"] < 0.002
    finally:
        teardown(built)
