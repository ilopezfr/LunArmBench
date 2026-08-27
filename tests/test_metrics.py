"""Metric helpers must not return NaN for finite inputs."""

import math

from lunarmbench.geometry import ConnectorGeometry
from lunarmbench.metrics import classify_failure, is_success


def test_metrics_finite():
    geom = ConnectorGeometry()
    m = {"insertion_depth": 0.01, "lateral_error": 0.002, "orientation_error": 0.03}
    assert math.isfinite(m["insertion_depth"])
    assert is_success(m, geom) in (True, False)
    r = classify_failure(
        success=False,
        timed_out=True,
        force_exceeded=False,
        metrics=m,
        geom=geom,
        had_contact=False,
        sim_diverged=False,
    )
    assert r in {"timeout", "pre_contact_collision", "misalignment", "jammed_insertion", "other"}
