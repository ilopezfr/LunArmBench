"""Procedural synthetic connector meshes.

Units are meters. Geometry is abstract and is not a NASA or commercial connector.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh


@dataclass(frozen=True)
class ConnectorGeometry:
    """Keyed rectangular plug / socket pair.

    Local frames:
    - Plug origin at geometric center, +Z along the insertion axis toward the tip.
    - Socket origin at the mouth center, +Z into the cavity.
    """

    plug_width: float = 0.024
    plug_height: float = 0.016
    plug_length: float = 0.040
    key_width: float = 0.008
    key_height: float = 0.004
    clearance_x: float = 0.0015
    clearance_y: float = 0.0015
    wall_thickness: float = 0.008
    socket_depth: float = 0.032
    success_depth: float = 0.018
    success_lateral_m: float = 0.004
    success_orient_rad: float = 0.087  # 5 deg, POC threshold
    plug_mass_kg: float = 0.08

    @property
    def cavity_width(self) -> float:
        return self.plug_width + 2.0 * self.clearance_y

    @property
    def cavity_height(self) -> float:
        return self.plug_height + 2.0 * self.clearance_x

    @property
    def cavity_key_width(self) -> float:
        return self.key_width + 2.0 * self.clearance_y

    @property
    def cavity_key_height(self) -> float:
        return self.key_height + self.clearance_x

    @property
    def outer_width(self) -> float:
        return self.cavity_width + 2.0 * self.wall_thickness

    @property
    def outer_height(self) -> float:
        return self.cavity_height + self.cavity_key_height + 2.0 * self.wall_thickness

    @property
    def outer_depth(self) -> float:
        return self.socket_depth + self.wall_thickness


def _box(extents, translation) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(translation)
    return mesh


def plug_mesh(geom: ConnectorGeometry) -> trimesh.Trimesh:
    body = _box(
        [geom.plug_height, geom.plug_width, geom.plug_length],
        [0.0, 0.0, 0.0],
    )
    key = _box(
        [geom.key_height, geom.key_width, geom.plug_length * 0.9],
        [geom.plug_height / 2.0 + geom.key_height / 2.0, 0.0, 0.0],
    )
    return trimesh.util.concatenate([body, key])


def socket_mesh(geom: ConnectorGeometry) -> trimesh.Trimesh:
    """Open-front keyed box assembled from wall panels (no CSG)."""
    t = geom.wall_thickness
    depth = geom.socket_depth
    cw, ch = geom.cavity_width, geom.cavity_height
    kh, kw = geom.cavity_key_height, geom.cavity_key_width
    # Mouth at z=0, cavity +Z. Walls sit outside the cavity.
    back = _box(
        [ch + kh + 2 * t, cw + 2 * t, t],
        [kh / 2.0, 0.0, depth + t / 2.0],
    )
    bottom = _box(
        [t, cw + 2 * t, depth],
        [-(ch / 2.0 + t / 2.0), 0.0, depth / 2.0],
    )
    top_left = _box(
        [t, (cw - kw) / 2.0 + t, depth],
        [ch / 2.0 + kh + t / 2.0, -(kw / 2.0 + ((cw - kw) / 2.0 + t) / 2.0), depth / 2.0],
    )
    top_right = _box(
        [t, (cw - kw) / 2.0 + t, depth],
        [ch / 2.0 + kh + t / 2.0, (kw / 2.0 + ((cw - kw) / 2.0 + t) / 2.0), depth / 2.0],
    )
    # Key slot is the gap in +X wall; add a recessed key-channel roof
    key_roof = _box(
        [t, kw, depth],
        [ch / 2.0 + kh + t / 2.0, 0.0, depth / 2.0],
    )
    left = _box(
        [ch + kh + 2 * t, t, depth],
        [kh / 2.0, -(cw / 2.0 + t / 2.0), depth / 2.0],
    )
    right = _box(
        [ch + kh + 2 * t, t, depth],
        [kh / 2.0, cw / 2.0 + t / 2.0, depth / 2.0],
    )
    return trimesh.util.concatenate([back, bottom, top_left, top_right, key_roof, left, right])


def mesh_to_shape(physics, mesh: trimesh.Trimesh):
    coords = np.asarray(mesh.vertices, dtype=np.float32).flatten()
    conn = np.asarray(mesh.faces, dtype=np.int32).flatten()
    return physics.create_tri_mesh_shape(coordinates=coords, connectivity=conn)
