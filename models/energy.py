import config as cfg


def segment_energy(load, distance, direction="up"):
    """Energy consumed for one segment (no regen) / 计算单段行程能耗（不含能量回收）。"""
    delta_mass = (cfg.ENERGY_CAR_MASS + load) - cfg.ENERGY_COUNTERWEIGHT_MASS
    sign = 1 if direction == "up" else -1  # 上行正功，下行潜在回收 / upward positive work
    g = 9.81
    energy_motion = (
        sign * g * delta_mass * distance + cfg.ENERGY_FRICTION_PER_METER * distance
    )
    return max(energy_motion, 0) / cfg.ENERGY_MOTOR_EFFICIENCY
