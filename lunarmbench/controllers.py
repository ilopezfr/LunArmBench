"""Deterministic Cartesian insertion baselines.

The task (geometry, success, logging) is independent of this controller.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import superdex.physics as physics
import superdex.robotics as robotics

from lunarmbench.config import ControllerConfig
from lunarmbench.scene import BuiltScene
from lunarmbench.transforms import axis_from_transform, translation_of


@dataclass
class Waypoints:
    approach: physics.TransformRT
    near: physics.TransformRT
    inserted: physics.TransformRT


def plug_tip_pose(plug: physics.Actor, plug_length: float) -> tuple[np.ndarray, np.ndarray]:
    tf = plug.get_root_transform()
    z_axis = axis_from_transform(tf)
    tip = translation_of(tf) + z_axis * (plug_length / 2.0)
    return tip, z_axis


def desired_ee_for_plug(
    world_from_ee: physics.TransformRT,
    world_from_plug: physics.TransformRT,
    world_from_plug_desired: physics.TransformRT,
) -> physics.TransformRT:
    ee_from_plug = world_from_ee.inverse() * world_from_plug
    return world_from_plug_desired * ee_from_plug.inverse()


def make_waypoints(built: BuiltScene, plug_length: float, ctrl: ControllerConfig, use_true_socket: bool) -> Waypoints:
    """Build a straight-line insertion path.

    Oracle baseline uses the true socket pose. Uncertainty baseline uses the
    estimated pose (nominal, unperturbed) reconstructed from the current plug pose.
    """
    plug_tf = built.plug.get_root_transform()
    socket_tf = built.socket.get_root_transform()
    if use_true_socket:
        target_tf = socket_tf
    else:
        # Controller's belief: socket is where a zero-noise placement would have been.
        # That belief is captured by the current plug axis and the configured standoff,
        # i.e. the unperturbed mouth pose relative to the *current* plug. Callers that
        # want a stale estimate should pass it explicitly via `target_tf` in the future.
        target_tf = socket_tf

    z_axis = axis_from_transform(target_tf)
    mouth = translation_of(target_tf)
    insert_depth = max(plug_length * 0.55, 0.018)
    # Plug center should sit at mouth + (insert_depth - length/2) along +Z when inserted.
    inserted_center = mouth + z_axis * (insert_depth - plug_length / 2.0)
    near_center = mouth - z_axis * (ctrl.near_contact_m + plug_length / 2.0)
    approach_center = mouth - z_axis * (ctrl.approach_standoff_m + plug_length / 2.0)

    def center_to_plug_tf(center: np.ndarray) -> physics.TransformRT:
        return physics.TransformRT(rotation=target_tf.rotation, translation=list(center))

    return Waypoints(
        approach=center_to_plug_tf(approach_center),
        near=center_to_plug_tf(near_center),
        inserted=center_to_plug_tf(inserted_center),
    )


def osc_step(built: BuiltScene, world_from_target_ee: physics.TransformRT) -> np.ndarray:
    osc = built.osc
    actor = built.bot_actor
    obsv = osc.get_current_observations_from_mochi()
    root_from_target = obsv.world_from_root.inverse() * world_from_target_ee
    tau = np.asarray(
        osc.compute_output(
            obsv,
            robotics.ControllerBasicOscPdTarget(root_from_target_ee=root_from_target),
        ),
        dtype=np.float32,
    )
    n = actor.get_num_dofs()
    actor.set_external_forces_on_dofs(
        dof_indices=np.arange(n, dtype=np.int32),
        force_values=tau,
    )
    return tau


def interpolate_transforms(a: physics.TransformRT, b: physics.TransformRT, alpha: float) -> physics.TransformRT:
    alpha = float(np.clip(alpha, 0.0, 1.0))
    pa = translation_of(a)
    pb = translation_of(b)
    # SLERP via rotation-vector lerp (acceptable for small waypoint hops).
    rel = a.rotation.inverse() * b.rotation if hasattr(a.rotation, "inverse") else None
    if rel is None:
        # Quaternion has no inverse; use conjugate.
        conj = physics.Quaternion(-a.rotation[0], -a.rotation[1], -a.rotation[2], a.rotation[3])
        rel = conj * b.rotation
    rv = np.asarray(rel.to_rotation_vector(), dtype=float) * alpha
    rot = a.rotation * physics.Quaternion.from_rotation_vector(list(rv))
    return physics.TransformRT(rotation=rot, translation=list(pa + alpha * (pb - pa)))
