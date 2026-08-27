"""Small SE(3) helpers around SuperDex TransformRT / Quaternion."""

from __future__ import annotations

import numpy as np
import superdex.physics as physics


def as_xyzw(q: physics.Quaternion) -> np.ndarray:
    return np.array([q[0], q[1], q[2], q[3]], dtype=float)


def quat_rotate(q: physics.Quaternion, v: np.ndarray) -> np.ndarray:
    """Rotate vector v by quaternion q stored as xyzw."""
    x, y, z, w = as_xyzw(q)
    qvec = np.array([x, y, z], dtype=float)
    uv = np.cross(qvec, v)
    uuv = np.cross(qvec, uv)
    return v + 2.0 * (w * uv + uuv)


def transform_point(tf: physics.TransformRT, p: np.ndarray) -> np.ndarray:
    return np.asarray(tf.translation, dtype=float) + quat_rotate(tf.rotation, np.asarray(p, dtype=float))


def axis_from_transform(tf: physics.TransformRT, local_axis: np.ndarray | None = None) -> np.ndarray:
    if local_axis is None:
        local_axis = np.array([0.0, 0.0, 1.0])
    return quat_rotate(tf.rotation, np.asarray(local_axis, dtype=float))


def translation_of(tf: physics.TransformRT) -> np.ndarray:
    return np.asarray(tf.translation, dtype=float)


def orientation_error_rad(a: physics.Quaternion, b: physics.Quaternion) -> float:
    """Geodesic angle between two orientations."""
    rel = a.inverse() * b if hasattr(a, "inverse") else _quat_conj(a) * b
    # SuperDex Quaternion has no inverse(); compute via conjugate for unit quats.
    return float(np.linalg.norm(rel.to_rotation_vector()))


def _quat_conj(q: physics.Quaternion) -> physics.Quaternion:
    return physics.Quaternion(-q[0], -q[1], -q[2], q[3])


def quat_inverse(q: physics.Quaternion) -> physics.Quaternion:
    return _quat_conj(q)


def orientation_error_between(ta: physics.TransformRT, tb: physics.TransformRT) -> float:
    rel = ta.inverse() * tb
    return float(np.linalg.norm(rel.rotation.to_rotation_vector()))


def make_transform(translation, rotation=None) -> physics.TransformRT:
    if rotation is None:
        return physics.TransformRT(translation=list(np.asarray(translation, dtype=float)))
    return physics.TransformRT(
        rotation=rotation,
        translation=list(np.asarray(translation, dtype=float)),
    )


def rpy_deg_to_quat(roll_deg: float, pitch_deg: float, yaw_deg: float) -> physics.Quaternion:
    """Intrinsic XYZ (roll, pitch, yaw) in degrees."""
    r = np.deg2rad(roll_deg)
    p = np.deg2rad(pitch_deg)
    y = np.deg2rad(yaw_deg)
    return physics.Quaternion.rotation_z(y) * physics.Quaternion.rotation_y(p) * physics.Quaternion.rotation_x(r)
