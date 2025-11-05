import random

import config as cfg
from models.destination import sample_destination
from models.utils import rand_upper_floor, validate_ratios
from models.variables import Request

LOBBY_FLOOR = cfg.LOBBY_FLOOR


# ------------------------------
# Off-peak (Uniform Distribution) / 平峰期（均匀分布）
# ------------------------------
def generate_offpeak_uniform(
    num_requests: int,
    start_time: float,
    end_time: float,
    *,
    weekday: int = 0,
    intensity: float = 1.0,
    ratio_origin1: float = 0.5,
    ratio_dest1: float = 0.5,
    ratio_other: float = 0.0,
    load_min: float = 50.0,
    load_max: float = 110.0,
    seed_offset: int = 0,
    seed_base: int | None = None,
):
    """
    Generate off-peak requests with uniform arrival times / 生成平峰期均匀分布的请求。
    参数说明 / Parameter notes:
      - ratio_origin1: origin=1, dest∈[2..F] 的比例（上行）
      - ratio_dest1 : origin∈[2..F], dest=1 的比例（下行）
      - ratio_other : origin,dest∈[2..F] 且 origin!=dest 的比例（楼层间）
      - intensity   : 强度缩放系数，实际请求数 = floor(num_requests * intensity)
    """
    base = cfg.SIM_RANDOM_SEED if seed_base is None else seed_base
    random.seed(base + seed_offset)
    n = max(0, int(num_requests * max(0.0, intensity)))
    c1, c2 = validate_ratios(ratio_origin1, ratio_dest1, ratio_other)

    reqs = []
    for i in range(n):
        u = random.random()
        arrival = random.uniform(start_time, end_time)
        if u < c1:
            origin = LOBBY_FLOOR
            destination = sample_destination(weekday, arrival, origin)
        elif u < c2:
            origin = rand_upper_floor(cfg.BUILDING_FLOORS)
            destination = LOBBY_FLOOR
        else:
            origin = rand_upper_floor(cfg.BUILDING_FLOORS)
            destination = sample_destination(
                weekday, arrival, origin, exclude={LOBBY_FLOOR}
            )

        load = random.uniform(load_min, load_max)
        reqs.append(Request(i + 1, origin, destination, load, arrival))

    return reqs


# ------------------------------
# Peak (Gaussian Distribution) / 高峰期（高斯分布）
# ------------------------------
def generate_peak_gaussian(
    num_requests: int,
    start_time: float,
    end_time: float,
    *,
    weekday: int = 0,
    mu_time: float,
    sigma_ratio: float = 0.05,
    intensity: float = 1.0,
    ratio_origin1: float = 0.5,
    ratio_dest1: float = 0.5,
    ratio_other: float = 0.0,
    load_min: float = 60.0,
    load_max: float = 150.0,
    seed_offset: int = 100,
    seed_base: int | None = None,
):
    """
    Generate peak-period requests using truncated Gaussian arrival / 生成截断高斯分布的高峰期请求。
    其它参数含义与平峰函数一致；sigma = (end-start) * sigma_ratio。
    """
    base = cfg.SIM_RANDOM_SEED if seed_base is None else seed_base
    random.seed(base + seed_offset)
    n = max(0, int(num_requests * max(0.0, intensity)))
    c1, c2 = validate_ratios(ratio_origin1, ratio_dest1, ratio_other)

    width = max(1e-6, (end_time - start_time))
    sigma = max(1e-9, width * max(0.0, sigma_ratio))

    reqs = []
    for i in range(n):
        u = random.random()
        t = random.gauss(mu_time, sigma)
        arrival = min(max(t, start_time), end_time)
        if u < c1:
            origin = LOBBY_FLOOR
            destination = sample_destination(weekday, arrival, origin)
        elif u < c2:
            origin = rand_upper_floor(cfg.BUILDING_FLOORS)
            destination = LOBBY_FLOOR
        else:
            origin = rand_upper_floor(cfg.BUILDING_FLOORS)
            destination = sample_destination(
                weekday, arrival, origin, exclude={LOBBY_FLOOR}
            )

        load = random.uniform(load_min, load_max)
        reqs.append(Request(i + 1, origin, destination, load, arrival))

    return reqs


def generate_requests_weekday(
    total_requests: int, *, seed_shift: int = 0, weekday: int = 0
):
    """Simulate a full-day demand profile / 生成完整一天的乘梯请求序列。"""
    seed_base = cfg.SIM_RANDOM_SEED + seed_shift
    total_morning = int(total_requests * cfg.WEEKDAY_PEAK_MORNING_RATIO)
    total_day = int(total_requests * cfg.WEEKDAY_OFFPEAK_DAY_RATIO)
    total_evening = int(total_requests * cfg.WEEKDAY_PEAK_EVENING_RATIO)
    total_night = int(total_requests * cfg.WEEKDAY_OFFPEAK_NIGHT_RATIO)

    morning = generate_peak_gaussian(
        num_requests=total_morning,
        start_time=cfg.h2s(*cfg.WEEKDAY_PEAK_MORNING_START),
        end_time=cfg.h2s(*cfg.WEEKDAY_PEAK_MORNING_END),
        mu_time=cfg.h2s(cfg.WEEKDAY_PEAK_MORNING_MU),
        sigma_ratio=cfg.WEEKDAY_MORNING_SIGMA_RATIO,
        intensity=cfg.WEEKDAY_MORNING_INTENSITY,
        weekday=weekday,
        ratio_origin1=cfg.WEEKDAY_MORNING_RATIO_ORIGIN1,
        ratio_dest1=cfg.WEEKDAY_MORNING_RATIO_DEST1,
        ratio_other=cfg.WEEKDAY_MORNING_RATIO_OTHER,
        load_min=cfg.WEEKDAY_MORNING_LOAD_MIN,
        load_max=cfg.WEEKDAY_MORNING_LOAD_MAX,
        seed_offset=100,
        seed_base=seed_base,
    )

    day = generate_offpeak_uniform(
        num_requests=total_day,
        start_time=cfg.h2s(*cfg.WEEKDAY_OFFPEAK_DAY_START),
        end_time=cfg.h2s(*cfg.WEEKDAY_OFFPEAK_DAY_END),
        intensity=cfg.WEEKDAY_DAY_INTENSITY,
        weekday=weekday,
        ratio_origin1=cfg.WEEKDAY_DAY_RATIO_ORIGIN1,
        ratio_dest1=cfg.WEEKDAY_DAY_RATIO_DEST1,
        ratio_other=cfg.WEEKDAY_DAY_RATIO_OTHER,
        load_min=cfg.WEEKDAY_DAY_LOAD_MIN,
        load_max=cfg.WEEKDAY_DAY_LOAD_MAX,
        seed_offset=200,
        seed_base=seed_base,
    )

    evening = generate_peak_gaussian(
        num_requests=total_evening,
        start_time=cfg.h2s(*cfg.WEEKDAY_PEAK_EVENING_START),
        end_time=cfg.h2s(*cfg.WEEKDAY_PEAK_EVENING_END),
        mu_time=cfg.h2s(cfg.WEEKDAY_PEAK_EVENING_MU),
        sigma_ratio=cfg.WEEKDAY_EVENING_SIGMA_RATIO,
        intensity=cfg.WEEKDAY_EVENING_INTENSITY,
        weekday=weekday,
        ratio_origin1=cfg.WEEKDAY_EVENING_RATIO_ORIGIN1,
        ratio_dest1=cfg.WEEKDAY_EVENING_RATIO_DEST1,
        ratio_other=cfg.WEEKDAY_EVENING_RATIO_OTHER,
        load_min=cfg.WEEKDAY_EVENING_LOAD_MIN,
        load_max=cfg.WEEKDAY_EVENING_LOAD_MAX,
        seed_offset=300,
        seed_base=seed_base,
    )

    night = generate_offpeak_uniform(
        num_requests=total_night,
        start_time=cfg.h2s(*cfg.WEEKDAY_OFFPEAK_NIGHT_START),
        end_time=cfg.h2s(*cfg.WEEKDAY_OFFPEAK_NIGHT_END),
        intensity=cfg.WEEKDAY_NIGHT_INTENSITY,
        weekday=weekday,
        ratio_origin1=cfg.WEEKDAY_NIGHT_RATIO_ORIGIN1,
        ratio_dest1=cfg.WEEKDAY_NIGHT_RATIO_DEST1,
        ratio_other=cfg.WEEKDAY_NIGHT_RATIO_OTHER,
        load_min=cfg.WEEKDAY_NIGHT_LOAD_MIN,
        load_max=cfg.WEEKDAY_NIGHT_LOAD_MAX,
        seed_offset=400,
        seed_base=seed_base,
    )

    # 统一按到达时间排序 / merge and sort by arrival time
    requests = sorted(morning + day + evening + night, key=lambda r: r.arrival_time)

    # 统一重新编号，确保请求 ID 唯一 / reindex IDs to guarantee uniqueness.
    for new_id, req in enumerate(requests, start=1):
        req.id = new_id

    return requests


def generate_requests_weekend(
    total_requests: int, *, seed_shift: int = 0, weekday: int = 6
):
    """Simulate a weekend profile with day/night uniform segments / 生成周末日请求。"""
    seed_base = cfg.SIM_RANDOM_SEED + seed_shift
    total_day = int(total_requests * cfg.WEEKEND_DAY_RATIO)
    total_night = max(0, total_requests - total_day)

    day = generate_offpeak_uniform(
        num_requests=total_day,
        start_time=cfg.h2s(*cfg.WEEKEND_DAY_START),
        end_time=cfg.h2s(*cfg.WEEKEND_DAY_END),
        intensity=cfg.WEEKEND_DAY_INTENSITY,
        weekday=weekday,
        ratio_origin1=cfg.WEEKEND_DAY_RATIO_ORIGIN1,
        ratio_dest1=cfg.WEEKEND_DAY_RATIO_DEST1,
        ratio_other=cfg.WEEKEND_DAY_RATIO_OTHER,
        load_min=cfg.WEEKEND_DAY_LOAD_MIN,
        load_max=cfg.WEEKEND_DAY_LOAD_MAX,
        seed_offset=500,
        seed_base=seed_base,
    )

    night = generate_offpeak_uniform(
        num_requests=total_night,
        start_time=cfg.h2s(*cfg.WEEKEND_NIGHT_START),
        end_time=cfg.h2s(*cfg.WEEKEND_NIGHT_END),
        intensity=cfg.WEEKEND_NIGHT_INTENSITY,
        weekday=weekday,
        ratio_origin1=cfg.WEEKEND_NIGHT_RATIO_ORIGIN1,
        ratio_dest1=cfg.WEEKEND_NIGHT_RATIO_DEST1,
        ratio_other=cfg.WEEKEND_NIGHT_RATIO_OTHER,
        load_min=cfg.WEEKEND_NIGHT_LOAD_MIN,
        load_max=cfg.WEEKEND_NIGHT_LOAD_MAX,
        seed_offset=600,
        seed_base=seed_base,
    )

    requests = sorted(day + night, key=lambda r: r.arrival_time)

    for new_id, req in enumerate(requests, start=1):
        req.id = new_id

    return requests
