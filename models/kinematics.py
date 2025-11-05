import math
from models import config as cfg


def vmax_up(load):
    """Load-dependent upward velocity / 载荷相关的上行极限速度."""
    return cfg.KIN_MAX_SPEED_UP_FULL + (
        cfg.KIN_MAX_SPEED_UP_EMPTY - cfg.KIN_MAX_SPEED_UP_FULL
    ) * math.exp(-cfg.KIN_SPEED_DECAY_RATE * load / cfg.ELEVATOR_CAPACITY)


def vmax_down(load):
    """Load-dependent downward velocity / 载荷相关的下行极限速度."""
    return cfg.KIN_MAX_SPEED_DOWN_FULL + (
        cfg.KIN_MAX_SPEED_DOWN_EMPTY - cfg.KIN_MAX_SPEED_DOWN_FULL
    ) * math.exp(-cfg.KIN_SPEED_DECAY_RATE * load / cfg.ELEVATOR_CAPACITY)


def acc(load):
    """Load-dependent acceleration / 载荷相关的加速度."""
    return cfg.KIN_ACC_UP_FULL + (
        cfg.KIN_ACC_UP_EMPTY - cfg.KIN_ACC_UP_FULL
    ) * math.exp(-cfg.KIN_ACC_DECAY_RATE * load / cfg.ELEVATOR_CAPACITY)


def dec(load):
    """Load-dependent deceleration / 载荷相关的减速度."""
    return cfg.KIN_DEC_DOWN_FULL + (
        cfg.KIN_DEC_DOWN_EMPTY - cfg.KIN_DEC_DOWN_FULL
    ) * math.exp(-cfg.KIN_ACC_DECAY_RATE * load / cfg.ELEVATOR_CAPACITY)


def travel_time(load, origin_floor, destination_floor):
    """Compute travel duration between floors (triangular/trapezoidal profile) / 计算楼层间行程时间（考虑三角或梯形速度曲线）。"""
    distance = abs(destination_floor - origin_floor) * cfg.BUILDING_FLOOR_HEIGHT
    direction = "up" if destination_floor > origin_floor else "down"

    vmax = vmax_up(load) if direction == "up" else vmax_down(load)
    a_acc = acc(load)
    a_dec = dec(load)

    v_peak = math.sqrt(2 * distance * a_acc * a_dec / (a_acc + a_dec))

    if v_peak <= vmax:  # triangular profile / 三角速度曲线
        return v_peak * (1 / a_acc + 1 / a_dec)
    else:  # trapezoidal profile / 梯形速度曲线
        d_acc = vmax**2 / (2 * a_acc)
        d_dec = vmax**2 / (2 * a_dec)
        d_const = max(distance - d_acc - d_dec, 0)
        return vmax / a_acc + vmax / a_dec + d_const / vmax
