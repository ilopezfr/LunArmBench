"""Benchmark scoring, independent of the controller and of any RL reward."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from lunarmbench.config import TaskConfig
from lunarmbench.geometry import ConnectorGeometry
from lunarmbench.transforms import axis_from_transform, orientation_error_between, translation_of


FAILURE_MODES = (
    "success",
    "timeout",
    "force_threshold",
    "misalignment",
    "rim_collision",
    "jammed_insertion",
    "pre_contact_collision",
    "controller_instability",
    "simulation_instability",
    "other",
)


@dataclass
class EpisodeRecord:
    episode_id: str
    timestamp: str
    git_commit: str
    superdex_commit: str
    config_name: str
    random_seed: int
    gravity: float
    robot: str
    controller: str
    fixture_true_pose: list[float]
    fixture_estimated_pose: list[float]
    initial_translation_error: float
    initial_rotation_error: float
    success: bool
    completion_time: float
    final_alignment_error: float
    insertion_depth: float
    final_lateral_error: float
    retry_count: int
    termination_reason: str
    peak_contact_force: float | None = None
    integrated_contact_force: float | None = None
    peak_contact_torque: float | None = None
    collision_count: int | None = None
    simulation_steps: int = 0
    wall_clock_runtime: float = 0.0
    real_time_factor: float = 0.0
    peak_control_effort: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pose_xyzrpy(tf) -> list[float]:
    t = translation_of(tf)
    rv = np.asarray(tf.rotation.to_rotation_vector(), dtype=float)
    return [float(t[0]), float(t[1]), float(t[2]), float(rv[0]), float(rv[1]), float(rv[2])]


def insertion_metrics(plug, socket, geom: ConnectorGeometry) -> dict[str, float]:
    plug_tf = plug.get_root_transform()
    socket_tf = socket.get_root_transform()
    z_axis = axis_from_transform(socket_tf)
    tip = translation_of(plug_tf) + axis_from_transform(plug_tf) * (geom.plug_length / 2.0)
    mouth = translation_of(socket_tf)
    rel = tip - mouth
    depth = float(np.dot(rel, z_axis))
    lateral = rel - depth * z_axis
    lateral_err = float(np.linalg.norm(lateral))
    orient_err = orientation_error_between(socket_tf, plug_tf)
    return {
        "insertion_depth": depth,
        "lateral_error": lateral_err,
        "orientation_error": orient_err,
    }


def is_success(metrics: dict[str, float], geom: ConnectorGeometry) -> bool:
    return (
        metrics["insertion_depth"] >= geom.success_depth
        and metrics["lateral_error"] <= geom.success_lateral_m
        and metrics["orientation_error"] <= geom.success_orient_rad
    )


def classify_failure(
    *,
    success: bool,
    timed_out: bool,
    force_exceeded: bool,
    metrics: dict[str, float],
    geom: ConnectorGeometry,
    had_contact: bool,
    sim_diverged: bool,
) -> str:
    if success:
        return "success"
    if sim_diverged:
        return "simulation_instability"
    if force_exceeded:
        return "force_threshold"
    if not had_contact and timed_out:
        return "timeout"
    if not had_contact:
        return "pre_contact_collision" if metrics["lateral_error"] > geom.cavity_width else "timeout"
    if metrics["lateral_error"] > geom.success_lateral_m:
        return "misalignment"
    if 0.0 < metrics["insertion_depth"] < geom.success_depth:
        return "jammed_insertion"
    if timed_out:
        return "timeout"
    return "other"
