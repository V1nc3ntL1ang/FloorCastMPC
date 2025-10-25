import config as cfg


def segment_energy(load, distance, direction="up"):
    """Compute motion energy for one travel segment (no regeneration)."""
    delta_mass = (cfg.ENERGY_CAR_MASS + load) - cfg.ENERGY_COUNTERWEIGHT_MASS
    if direction == "up":
        sign = 1
    else:
        sign = -1
    g = 9.81
    energy_motion = (
        sign * g * delta_mass * distance + cfg.ENERGY_FRICTION_PER_METER * distance
    )
    return max(energy_motion, 0) / cfg.ENERGY_MOTOR_EFFICIENCY
