import math
from models import config as cfg
from models.kinematics import vmax_up, vmax_down, acc as accel, dec as decel


def _positive(value: float) -> float:
    return value if value > 0.0 else 0.0


def segment_energy(load, distance, direction="up"):
    """Segment energy with kinematic decomposition (no regen) / 按加速-匀速-减速分段计算能耗（不含能量回收）。"""
    if distance <= 0:
        return 0.0

    eff = max(cfg.ENERGY_MOTOR_EFFICIENCY, 1e-9)
    g = 9.81

    vmax = vmax_up(load) if direction == "up" else vmax_down(load)
    a_acc = max(accel(load), 1e-9)
    a_dec = max(decel(load), 1e-9)

    v_peak_tri = math.sqrt(
        max(2.0 * distance * a_acc * a_dec / max(a_acc + a_dec, 1e-9), 0.0)
    )

    if v_peak_tri <= vmax + 1e-9:
        v_peak = v_peak_tri
        d_acc = v_peak**2 / (2.0 * a_acc)
        d_dec = v_peak**2 / (2.0 * a_dec)
        d_const = 0.0
    else:
        v_peak = vmax
        d_acc = v_peak**2 / (2.0 * a_acc)
        d_dec = v_peak**2 / (2.0 * a_dec)
        d_const = max(distance - d_acc - d_dec, 0.0)

    M_eq = (
        cfg.ENERGY_CAR_MASS + load
    )  # 等效运动质量 M0 + γL，此处取 γ=1 / equivalent moving mass.
    delta_mass = (cfg.ENERGY_CAR_MASS + load) - cfg.ENERGY_COUNTERWEIGHT_MASS
    sign = 1 if direction == "up" else -1
    friction = cfg.ENERGY_FRICTION_PER_METER

    e_acc = (
        _positive(
            0.5 * M_eq * v_peak**2 + sign * g * delta_mass * d_acc + friction * d_acc
        )
        / eff
    )
    e_const = _positive(sign * g * delta_mass * d_const + friction * d_const) / eff
    e_dec = (
        _positive(
            -0.5 * M_eq * v_peak**2 + sign * g * delta_mass * d_dec + friction * d_dec
        )
        / eff
    )

    return e_acc + e_const + e_dec


def standby_energy(duration):
    """Baseline auxiliary energy proportional to elapsed time / 按时间计算的基础附属能耗。"""
    return cfg.ENERGY_STANDBY_POWER * max(duration, 0.0)
