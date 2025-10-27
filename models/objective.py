import config as cfg


def compute_objective(total_time, total_energy):
    """Weighted objective blending time and energy / 计算时间与能耗的加权目标值。"""
    return cfg.WEIGHT_TIME * total_time + cfg.WEIGHT_ENERGY * total_energy
