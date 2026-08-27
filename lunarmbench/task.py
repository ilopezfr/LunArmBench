"""Lunar Connector Insertion V0 episode loop."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import numpy as np
import superdex.physics as physics

from lunarmbench.config import TaskConfig
from lunarmbench.controllers import (
    desired_ee_for_plug,
    interpolate_transforms,
    make_waypoints,
    osc_step,
)
from lunarmbench.metrics import (
    EpisodeRecord,
    classify_failure,
    insertion_metrics,
    is_success,
    pose_xyzrpy,
)
from lunarmbench.scene import BuiltScene, build_scene, teardown
from lunarmbench.transforms import translation_of


def _contact_force(actor) -> float | None:
    try:
        if not actor.is_query_supported(physics.QueryType.TOTAL_CONTACT_FORCE):
            return None
        f = np.asarray(actor.get_contact_force_world(), dtype=float)
        return float(np.linalg.norm(f))
    except Exception:
        return None


def _contact_torque(actor) -> float | None:
    try:
        if not actor.is_query_supported(physics.QueryType.TOTAL_CONTACT_FORCE):
            return None
        t = np.asarray(actor.get_contact_torque_world(), dtype=float)
        return float(np.linalg.norm(t))
    except Exception:
        return None


def _n_contacts(actor) -> int:
    try:
        if not actor.is_query_supported(physics.QueryType.CONTACT_POINTS):
            return 0
        return int(len(actor.get_contact_points_world()))
    except Exception:
        return 0


def _diverged(actor) -> bool:
    try:
        status = actor.get_convergence_status()
        name = status.name if hasattr(status, "name") else str(status)
        return "DIVERG" in name.upper() or "FAIL" in name.upper()
    except Exception:
        return False


def _ee_transform(built: BuiltScene) -> physics.TransformRT:
    obsv = built.osc.get_current_observations_from_mochi()
    return obsv.world_from_ee_link


def run_episode(
    cfg: TaskConfig,
    *,
    oracle: bool = True,
    git_commit: str = "",
    superdex_commit: str = "",
    config_name: str = "",
    teardown_scene: bool = True,
) -> EpisodeRecord:
    rng = np.random.default_rng(cfg.seed)
    built = build_scene(cfg, rng=rng)
    ctrl = cfg.controller
    geom = cfg.geometry
    t0 = time.perf_counter()

    true_tf = built.socket.get_root_transform()
    # Estimated pose is the unperturbed mouth: recover by removing configured bias
    # for the oracle case they match. For biased configs the controller still
    # tracks the true socket when oracle=True; when oracle=False it tracks the
    # plug-relative nominal placement (pre-perturbation), which we reconstruct
    # by applying the inverse of the configured deterministic offset.
    estimated_tf = true_tf
    if not oracle:
        from lunarmbench.transforms import rpy_deg_to_quat

        dt = np.array(cfg.pose_noise.translation_m, dtype=float)
        rpy = np.array(cfg.pose_noise.rotation_deg, dtype=float)
        inv_rot = rpy_deg_to_quat(*(-np.array(rpy))).__mul__(true_tf.rotation) if False else true_tf.rotation
        # Undo deterministic translation in world frame (POC: small-angle).
        estimated_tf = physics.TransformRT(
            rotation=true_tf.rotation,
            translation=list(translation_of(true_tf) - dt),
        )
        if np.any(np.abs(rpy) > 1e-9):
            # Approximate: estimated rotation is true * inv(perturbation).
            pert = rpy_deg_to_quat(*rpy)
            conj = physics.Quaternion(-pert[0], -pert[1], -pert[2], pert[3])
            estimated_tf = physics.TransformRT(
                rotation=conj * true_tf.rotation,
                translation=list(translation_of(true_tf) - dt),
            )

    # Temporarily swap socket transform used by waypoint planner
    class _SocketView:
        def __init__(self, tf):
            self._tf = tf

        def get_root_transform(self):
            return self._tf

    planned = BuiltScene(**{**built.__dict__, "socket": _SocketView(estimated_tf) if not oracle else built.socket})
    waypoints = make_waypoints(planned, geom.plug_length, ctrl, use_true_socket=True)

    plug0 = built.plug.get_root_transform()
    init_trans = float(np.linalg.norm(translation_of(true_tf) - translation_of(estimated_tf)))
    init_rot = float(
        np.linalg.norm((true_tf.inverse() * estimated_tf).rotation.to_rotation_vector())
    )

    stages = [
        (waypoints.approach, ctrl.approach_speed_mps, "approach"),
        (waypoints.near, ctrl.approach_speed_mps, "near"),
        (waypoints.inserted, ctrl.insert_speed_mps, "insert"),
    ]

    sim_t = 0.0
    steps = 0
    peak_f = 0.0
    integ_f = 0.0
    peak_tau_c = 0.0
    peak_effort = 0.0
    had_contact = False
    force_exceeded = False
    diverged = False
    retries = 0
    success = False
    last_metrics = insertion_metrics(built.plug, built.socket, geom)

    # Settle
    settle_steps = int(ctrl.settle_s / cfg.sim_dt)
    hold = desired_ee_for_plug(_ee_transform(built), built.plug.get_root_transform(), built.plug.get_root_transform())
    for _ in range(settle_steps):
        tau = osc_step(built, hold)
        built.scene.step(cfg.sim_dt)
        sim_t += cfg.sim_dt
        steps += 1

    current_plug_target = built.plug.get_root_transform()
    for target_plug, speed, _stage in stages:
        start = current_plug_target
        dist = float(np.linalg.norm(translation_of(target_plug) - translation_of(start)))
        duration = max(dist / max(speed, 1e-6), cfg.sim_dt)
        elapsed = 0.0
        while elapsed < duration:
            alpha = elapsed / duration
            plug_goal = interpolate_transforms(start, target_plug, alpha)
            ee_goal = desired_ee_for_plug(
                _ee_transform(built), built.plug.get_root_transform(), plug_goal
            )
            tau = osc_step(built, ee_goal)
            peak_effort = max(peak_effort, float(np.linalg.norm(tau)))
            built.scene.step(cfg.sim_dt)
            sim_t += cfg.sim_dt
            elapsed += cfg.sim_dt
            steps += 1

            f = _contact_force(built.socket)
            if f is not None:
                peak_f = max(peak_f, f)
                integ_f += f * cfg.sim_dt
                if f > ctrl.force_limit_n:
                    force_exceeded = True
            tc = _contact_torque(built.socket)
            if tc is not None:
                peak_tau_c = max(peak_tau_c, tc)
            n_pts = _n_contacts(built.socket) + _n_contacts(built.plug)
            if n_pts > 0 or (f is not None and f > 1e-4):
                had_contact = True
            diverged = diverged or _diverged(built.bot_actor)
            last_metrics = insertion_metrics(built.plug, built.socket, geom)
            success = is_success(last_metrics, geom)
            if success or force_exceeded or diverged or sim_t >= ctrl.timeout_s:
                break
        current_plug_target = target_plug
        if success or force_exceeded or diverged or sim_t >= ctrl.timeout_s:
            break

        if ctrl.enable_recovery and not success and _stage == "insert":
            # Retract and try a small lateral search (Baseline 2).
            for k in range(ctrl.recovery_retries):
                retries += 1
                lateral = np.array(
                    [
                        ((k % 2) * 2 - 1) * ctrl.recovery_lateral_m if k < 2 else 0.0,
                        (0.0 if k < 2 else ((k % 2) * 2 - 1) * ctrl.recovery_lateral_m),
                        0.0,
                    ]
                )
                retracted = physics.TransformRT(
                    rotation=waypoints.near.rotation,
                    translation=list(translation_of(waypoints.near) + lateral),
                )
                # one short retract+retry
                for goal in (waypoints.near, retracted, waypoints.inserted):
                    ee_goal = desired_ee_for_plug(
                        _ee_transform(built), built.plug.get_root_transform(), goal
                    )
                    for _ in range(int(0.4 / cfg.sim_dt)):
                        tau = osc_step(built, ee_goal)
                        built.scene.step(cfg.sim_dt)
                        sim_t += cfg.sim_dt
                        steps += 1
                        last_metrics = insertion_metrics(built.plug, built.socket, geom)
                        success = is_success(last_metrics, geom)
                        if success or sim_t >= ctrl.timeout_s:
                            break
                    if success or sim_t >= ctrl.timeout_s:
                        break
                if success or sim_t >= ctrl.timeout_s:
                    break

    timed_out = (not success) and sim_t >= ctrl.timeout_s
    reason = classify_failure(
        success=success,
        timed_out=timed_out,
        force_exceeded=force_exceeded,
        metrics=last_metrics,
        geom=geom,
        had_contact=had_contact,
        sim_diverged=diverged,
    )
    wall = time.perf_counter() - t0
    record = EpisodeRecord(
        episode_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        git_commit=git_commit,
        superdex_commit=superdex_commit,
        config_name=config_name or cfg.name,
        random_seed=cfg.seed,
        gravity=cfg.gravity,
        robot=cfg.robot,
        controller=ctrl.name + ("_oracle" if oracle else "_uncertain"),
        fixture_true_pose=pose_xyzrpy(true_tf),
        fixture_estimated_pose=pose_xyzrpy(estimated_tf),
        initial_translation_error=init_trans,
        initial_rotation_error=init_rot,
        success=bool(success),
        completion_time=sim_t,
        final_alignment_error=last_metrics["orientation_error"],
        insertion_depth=last_metrics["insertion_depth"],
        final_lateral_error=last_metrics["lateral_error"],
        retry_count=retries,
        termination_reason=reason,
        peak_contact_force=peak_f if peak_f > 0 else _contact_force(built.socket),
        integrated_contact_force=integ_f if integ_f > 0 else None,
        peak_contact_torque=peak_tau_c if peak_tau_c > 0 else None,
        collision_count=_n_contacts(built.socket),
        simulation_steps=steps,
        wall_clock_runtime=wall,
        real_time_factor=(sim_t / wall) if wall > 0 else 0.0,
        peak_control_effort=peak_effort,
    )
    if teardown_scene:
        teardown(built)
    return record
