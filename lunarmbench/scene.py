"""Build the Lunar Connector Insertion V0 SuperDex scene."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import superdex.physics as physics
import superdex.robotics as robotics
from superdex.physics.paths import resolve_asset

from lunarmbench.config import TaskConfig
from lunarmbench.geometry import mesh_to_shape, plug_mesh, socket_mesh
from lunarmbench.transforms import (
    axis_from_transform,
    make_transform,
    rpy_deg_to_quat,
    translation_of,
)

COMBO_ASSET = "bots/arm_hand_combos/fr3_v2_2f_85/fr3_v2_2f_85.superdex_bot"
GRIPPER_LINKS = (
    "2f_85_base_link",
    "2f_85_left_inner_knuckle_link",
    "2f_85_left_knuckle_link",
    "2f_85_left_finger_link",
    "2f_85_left_finger_tip_link",
    "2f_85_right_inner_knuckle_link",
    "2f_85_right_knuckle_link",
    "2f_85_right_finger_link",
    "2f_85_right_finger_tip_link",
    "fr3_link8",
)


@dataclass
class BuiltScene:
    scene: physics.Scene
    robotics_context: robotics.RoboticsContext
    bot: robotics.Bot
    bot_actor: physics.Actor
    osc: robotics.Controller
    plug: physics.Actor
    socket: physics.Actor
    ee_name: str
    plug_name: str


def _find_link(scene: physics.Scene, actor: physics.Actor, suffix: str) -> physics.Actor:
    for handle in actor.get_nested_link_actors():
        link = scene.get_actor(handle)
        if link is not None and link.get_name().endswith(suffix):
            return link
    raise RuntimeError(f"Link ending with {suffix!r} not found")


def _apply_friction(contact: physics.ContactParams, mu: float) -> physics.ContactParams:
    contact.coulomb_friction_coefficient = float(mu)
    return contact


def attach_plug(prefab: robotics.BotPrefab, cfg: TaskConfig, plug_shape) -> None:
    parent_idx = next(i for i, link in enumerate(prefab.links) if link.name == cfg.plug_parent_link)
    joint = robotics.BotJointPrefab(
        name="gripper_to_plug",
        type=physics.ArticulatedJointType.HARD,
        parent_link_from_joint=physics.TransformRT(translation=[0.0, 0.0, cfg.plug_offset_z]),
    )
    link = robotics.BotLinkPrefab(
        name="connector_plug",
        parent_link=parent_idx,
        shape=plug_shape,
        collider_type=physics.ColliderType.SDF,
        mass=cfg.geometry.plug_mass_kg,
        contact=_apply_friction(physics.ContactParams(), cfg.friction),
    )
    prefab.joints.append(joint)
    prefab.links.append(link)
    overrides = prefab.contact_overrides
    for name in GRIPPER_LINKS:
        overrides.append(
            robotics.BotContactOverride(link_a="connector_plug", link_b=name, enable=False)
        )
    prefab.contact_overrides = overrides


def nominal_socket_transform(plug: physics.Actor, cfg: TaskConfig) -> physics.TransformRT:
    """Place the socket mouth a standoff distance along the plug +Z axis."""
    plug_tf = plug.get_root_transform()
    z_axis = axis_from_transform(plug_tf)
    tip = translation_of(plug_tf) + z_axis * (cfg.geometry.plug_length / 2.0)
    mouth = tip + z_axis * cfg.controller.approach_standoff_m
    return physics.TransformRT(rotation=plug_tf.rotation, translation=list(mouth))


def perturb_transform(
    nominal: physics.TransformRT,
    cfg: TaskConfig,
    rng: np.random.Generator,
) -> physics.TransformRT:
    noise = cfg.pose_noise
    dt = np.array(noise.translation_m, dtype=float)
    if noise.translation_std_m > 0:
        dt = dt + rng.normal(0.0, noise.translation_std_m, size=3)
    rpy = np.array(noise.rotation_deg, dtype=float)
    if noise.rotation_std_deg > 0:
        rpy = rpy + rng.normal(0.0, noise.rotation_std_deg, size=3)
    rot = rpy_deg_to_quat(*rpy) * nominal.rotation
    return physics.TransformRT(rotation=rot, translation=list(translation_of(nominal) + dt))


def build_scene(cfg: TaskConfig, rng: np.random.Generator | None = None) -> BuiltScene:
    rng = rng or np.random.default_rng(cfg.seed)
    physics.initialize(num_worker_threads=0)
    scene = physics.create_scene("lunarmbench_connector_v0")
    scene.set_gravity([0.0, 0.0, -float(cfg.gravity)])

    plug_shape = mesh_to_shape(physics, plug_mesh(cfg.geometry))
    socket_shape = mesh_to_shape(physics, socket_mesh(cfg.geometry))

    prefab = robotics.load_bot_prefab_from_file(str(resolve_asset(COMBO_ASSET)))
    # BASIC_OSC_PD has no gravity term. Disable gravity on the FR3 arm links so the
    # Cartesian baseline can track; gripper/plug weight still sees scene gravity.
    for i in range(len(prefab.links)):
        if prefab.links[i].name.startswith("fr3_"):
            prefab.links[i].has_gravity = False
    attach_plug(prefab, cfg, plug_shape)
    ctx = robotics.create_context()
    bot = robotics.create_bot(scene, prefab, ctx)
    bot_actor = bot.get_articulated_actor()

    plane = physics.create_plane_shape(normal=[0, 0, 1], distance=0)
    scene.create_rigid_actor(name="ground", shape=plane, is_static=True)

    plug = _find_link(scene, bot_actor, "/connector_plug")
    socket_tf = perturb_transform(nominal_socket_transform(plug, cfg), cfg, rng)
    # Static actors do not expose contact-force queries. Weld a dynamic socket
    # to the world so TOTAL_CONTACT_FORCE can be recorded.
    socket = scene.create_rigid_actor(
        name="connector_socket",
        shape=socket_shape,
        is_static=False,
        has_gravity=False,
        mass=25.0,
        collider_type=physics.ColliderType.SDF,
        contact=_apply_friction(physics.ContactParams(), cfg.friction),
        world_from_local=socket_tf,
    )
    if socket is None:
        raise RuntimeError("Failed to create socket actor")
    scene.create_rigid_pivot_position_constraint(
        stiffness=5.0e5,
        damping=5.0e3,
        saturation=1.0e5,
        target_position=list(translation_of(socket_tf)),
        local_position=[0.0, 0.0, 0.0],
        actor=socket.get_handle(),
    )
    scene.create_rigid_pivot_rotation_constraint(
        stiffness=5.0e5,
        damping=5.0e3,
        saturation=1.0e5,
        target_rotation=list(socket_tf.rotation.to_rotation_vector()),
        local_rotation=[0.0, 0.0, 0.0],
        actor=socket.get_handle(),
    )

    if socket.is_query_supported(physics.QueryType.TOTAL_CONTACT_FORCE):
        socket.register_query(physics.QueryType.TOTAL_CONTACT_FORCE)
    if socket.is_query_supported(physics.QueryType.CONTACT_POINTS):
        socket.register_query(physics.QueryType.CONTACT_POINTS)
    if plug.is_query_supported(physics.QueryType.CONTACT_POINTS):
        plug.register_query(physics.QueryType.CONTACT_POINTS)

    osc = bot.create_controller("BASIC_OSC_PD")
    bot_name = bot.get_name()
    osc.initialize(f"{bot_name}/fr3_link0", f"{bot_name}/fr3_link8")
    params = osc.get_params()
    params.kp_p = cfg.controller.osc_kp_p
    params.kd_p = cfg.controller.osc_kd_p
    params.kp_r = cfg.controller.osc_kp_r
    params.kd_r = cfg.controller.osc_kd_r
    params.max_translation_error = cfg.controller.max_translation_error
    params.max_rotation_error = cfg.controller.max_rotation_error
    params.b_apply_max_osc_torque_normalization = True
    osc.set_params(params)

    return BuiltScene(
        scene=scene,
        robotics_context=ctx,
        bot=bot,
        bot_actor=bot_actor,
        osc=osc,
        plug=plug,
        socket=socket,
        ee_name=f"{bot_name}/fr3_link8",
        plug_name=plug.get_name(),
    )


def teardown(built: BuiltScene) -> None:
    robotics.destroy_bot(built.scene, built.bot)
    physics.destroy_scene(built.scene)
    physics.shutdown()
