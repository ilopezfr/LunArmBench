"""Connector geometry unit tests (no SuperDex runtime required)."""

from lunarmbench.geometry import ConnectorGeometry, plug_mesh, socket_mesh
from lunarmbench.metrics import classify_failure, is_success


def test_plug_and_socket_watertight_enough():
    geom = ConnectorGeometry()
    plug = plug_mesh(geom)
    sock = socket_mesh(geom)
    assert len(plug.faces) > 0
    assert len(sock.faces) > 0
    assert plug.extents[2] > 0.03


def test_success_detector_thresholds():
    geom = ConnectorGeometry()
    ok = {"insertion_depth": geom.success_depth + 0.001, "lateral_error": 0.001, "orientation_error": 0.01}
    bad = {"insertion_depth": 0.002, "lateral_error": 0.02, "orientation_error": 0.2}
    assert is_success(ok, geom)
    assert not is_success(bad, geom)


def test_failure_taxonomy_misalignment():
    geom = ConnectorGeometry()
    reason = classify_failure(
        success=False,
        timed_out=False,
        force_exceeded=False,
        metrics={"insertion_depth": 0.02, "lateral_error": 0.01, "orientation_error": 0.01},
        geom=geom,
        had_contact=True,
        sim_diverged=False,
    )
    assert reason == "misalignment"
