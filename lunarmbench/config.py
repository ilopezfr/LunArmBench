"""Task / experiment configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lunarmbench.geometry import ConnectorGeometry
from lunarmbench.paths import CONFIGS_DIR


@dataclass
class PoseNoise:
    """POC fixture-pose uncertainty. Not a mission requirement."""

    translation_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    translation_std_m: float = 0.0
    rotation_std_deg: float = 0.0


@dataclass
class ControllerConfig:
    name: str = "straight_insert"
    osc_kp_p: float = 1200.0
    osc_kd_p: float = 80.0
    osc_kp_r: float = 40.0
    osc_kd_r: float = 4.0
    max_translation_error: float = 0.04
    max_rotation_error: float = 0.4
    approach_speed_mps: float = 0.08
    insert_speed_mps: float = 0.025
    approach_standoff_m: float = 0.035
    near_contact_m: float = 0.004
    settle_s: float = 0.15
    timeout_s: float = 6.0
    force_limit_n: float = 80.0
    enable_recovery: bool = False
    recovery_lateral_m: float = 0.004
    recovery_retries: int = 2


@dataclass
class TaskConfig:
    name: str = "connector_v0"
    gravity: float = 1.62
    gravity_label: str = "moon"
    sim_dt: float = 1.0 / 200.0
    robot: str = "fr3_v2_2f_85"
    plug_parent_link: str = "2f_85_base_link"
    plug_offset_z: float = 0.155
    friction: float = 0.4
    seed: int = 0
    geometry: ConnectorGeometry = field(default_factory=ConnectorGeometry)
    pose_noise: PoseNoise = field(default_factory=PoseNoise)
    controller: ControllerConfig = field(default_factory=ControllerConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _geom_from(data: dict) -> ConnectorGeometry:
    if not data:
        return ConnectorGeometry()
    fields = {k: v for k, v in data.items() if k in ConnectorGeometry.__dataclass_fields__}
    return ConnectorGeometry(**fields)


def _tuple3(value, default=(0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if value is None:
        return default
    seq = list(value)
    return (float(seq[0]), float(seq[1]), float(seq[2]))


def load_config(path: str | Path | None = None, **overrides: Any) -> TaskConfig:
    raw: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if not p.is_absolute():
            candidate = CONFIGS_DIR / p
            p = candidate if candidate.exists() else p
        raw = yaml.safe_load(p.read_text()) or {}
    geom = _geom_from(raw.get("geometry") or {})
    noise_raw = dict(raw.get("pose_noise") or {})
    if "translation_m" in noise_raw:
        noise_raw["translation_m"] = _tuple3(noise_raw["translation_m"])
    if "rotation_deg" in noise_raw:
        noise_raw["rotation_deg"] = _tuple3(noise_raw["rotation_deg"])
    noise = PoseNoise(**noise_raw)
    ctrl = ControllerConfig(**(raw.get("controller") or {}))
    skip = {"geometry", "pose_noise", "controller"}
    kwargs = {k: v for k, v in raw.items() if k not in skip}
    kwargs.update(overrides)
    return TaskConfig(geometry=geom, pose_noise=noise, controller=ctrl, **kwargs)
