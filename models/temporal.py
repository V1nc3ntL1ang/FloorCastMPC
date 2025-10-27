import config as cfg


def hold_time(boarding_weight, alighting_weight):
    """Door dwell time vs. passenger mass / 基于乘客重量的开门停站时间。"""
    total_weight = boarding_weight + alighting_weight
    if total_weight <= cfg.HOLD_CONGESTION_THRESHOLD:
        return cfg.HOLD_BASE_TIME + cfg.HOLD_EFF_NORMAL * total_weight
    else:
        normal_part = cfg.HOLD_EFF_NORMAL * cfg.HOLD_CONGESTION_THRESHOLD
        # 超出阈值部分按拥挤系数计算 / congested segment beyond threshold
        congested_part = cfg.HOLD_EFF_CONGESTED * (
            total_weight - cfg.HOLD_CONGESTION_THRESHOLD
        )
        return cfg.HOLD_BASE_TIME + normal_part + congested_part
