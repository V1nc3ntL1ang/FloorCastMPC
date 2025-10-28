import random
import config as cfg
from models.utils import rand_other_pair, rand_upper_floor, validate_ratios
from models.variables import Request


# ------------------------------
# Off-peak (Uniform Distribution) / 平峰期（均匀分布）
# ------------------------------
def generate_offpeak_uniform(
    num_requests: int,
    start_time: float,
    end_time: float,
    *,
    intensity: float = 1.0,
    ratio_origin1: float = 0.5,
    ratio_dest1: float = 0.5,
    ratio_other: float = 0.0,
    load_min: float = 50.0,
    load_max: float = 110.0,
    seed_offset: int = 0,
):
    """
    Generate off-peak requests with uniform arrival times / 生成平峰期均匀分布的请求。
    参数说明 / Parameter notes:
      - ratio_origin1: origin=1, dest∈[2..F] 的比例（上行）
      - ratio_dest1 : origin∈[2..F], dest=1 的比例（下行）
      - ratio_other : origin,dest∈[2..F] 且 origin!=dest 的比例（楼层间）
      - intensity   : 强度缩放系数，实际请求数 = floor(num_requests * intensity)
    """
    random.seed(cfg.SIM_RANDOM_SEED + seed_offset)
    n = max(0, int(num_requests * max(0.0, intensity)))
    c1, c2 = validate_ratios(ratio_origin1, ratio_dest1, ratio_other)

    reqs = []
    for i in range(n):
        u = random.random()
        if u < c1:
            origin, destination = 1, rand_upper_floor(cfg.BUILDING_FLOORS)
        elif u < c2:
            origin, destination = rand_upper_floor(cfg.BUILDING_FLOORS), 1
        else:
            origin, destination = rand_other_pair(cfg.BUILDING_FLOORS)

        load = random.uniform(load_min, load_max)
        arrival = random.uniform(start_time, end_time)
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
    mu_time: float,
    sigma_ratio: float = 0.05,
    intensity: float = 1.0,
    ratio_origin1: float = 0.5,
    ratio_dest1: float = 0.5,
    ratio_other: float = 0.0,
    load_min: float = 60.0,
    load_max: float = 150.0,
    seed_offset: int = 100,
):
    """
    Generate peak-period requests using truncated Gaussian arrival / 生成截断高斯分布的高峰期请求。
    其它参数含义与平峰函数一致；sigma = (end-start) * sigma_ratio。
    """
    random.seed(cfg.SIM_RANDOM_SEED + seed_offset)
    n = max(0, int(num_requests * max(0.0, intensity)))
    c1, c2 = validate_ratios(ratio_origin1, ratio_dest1, ratio_other)

    width = max(1e-6, (end_time - start_time))
    sigma = max(1e-9, width * max(0.0, sigma_ratio))

    reqs = []
    for i in range(n):
        u = random.random()
        if u < c1:
            origin, destination = 1, rand_upper_floor(cfg.BUILDING_FLOORS)
        elif u < c2:
            origin, destination = rand_upper_floor(cfg.BUILDING_FLOORS), 1
        else:
            origin, destination = rand_other_pair(cfg.BUILDING_FLOORS)

        load = random.uniform(load_min, load_max)
        t = random.gauss(mu_time, sigma)
        t = min(max(t, start_time), end_time)
        reqs.append(Request(i + 1, origin, destination, load, t))

    return reqs


def generate_requests_day(total_requests: int):
    """Simulate a full-day demand profile / 生成完整一天的乘梯请求序列。"""
    total_morning = int(total_requests * cfg.PEAK_MORNING_RATIO)
    total_day = int(total_requests * cfg.OFFPEAK_DAY_RATIO)
    total_evening = int(total_requests * cfg.PEAK_EVENING_RATIO)
    total_night = int(total_requests * cfg.OFFPEAK_NIGHT_RATIO)

    morning = generate_peak_gaussian(
        num_requests=total_morning,
        start_time=cfg.h2s(*cfg.PEAK_MORNING_START),
        end_time=cfg.h2s(*cfg.PEAK_MORNING_END),
        mu_time=cfg.h2s(cfg.PEAK_MORNING_MU),
        sigma_ratio=cfg.MORNING_SIGMA_RATIO,
        intensity=cfg.MORNING_INTENSITY,
        ratio_origin1=cfg.MORNING_RATIO_ORIGIN1,
        ratio_dest1=cfg.MORNING_RATIO_DEST1,
        ratio_other=cfg.MORNING_RATIO_OTHER,
        load_min=cfg.MORNING_LOAD_MIN,
        load_max=cfg.MORNING_LOAD_MAX,
        seed_offset=100,
    )

    day = generate_offpeak_uniform(
        num_requests=total_day,
        start_time=cfg.h2s(*cfg.OFFPEAK_DAY_START),
        end_time=cfg.h2s(*cfg.OFFPEAK_DAY_END),
        intensity=cfg.DAY_INTENSITY,
        ratio_origin1=cfg.DAY_RATIO_ORIGIN1,
        ratio_dest1=cfg.DAY_RATIO_DEST1,
        ratio_other=cfg.DAY_RATIO_OTHER,
        load_min=cfg.DAY_LOAD_MIN,
        load_max=cfg.DAY_LOAD_MAX,
        seed_offset=200,
    )

    evening = generate_peak_gaussian(
        num_requests=total_evening,
        start_time=cfg.h2s(*cfg.PEAK_EVENING_START),
        end_time=cfg.h2s(*cfg.PEAK_EVENING_END),
        mu_time=cfg.h2s(cfg.PEAK_EVENING_MU),
        sigma_ratio=cfg.EVENING_SIGMA_RATIO,
        intensity=cfg.EVENING_INTENSITY,
        ratio_origin1=cfg.EVENING_RATIO_ORIGIN1,
        ratio_dest1=cfg.EVENING_RATIO_DEST1,
        ratio_other=cfg.EVENING_RATIO_OTHER,
        load_min=cfg.EVENING_LOAD_MIN,
        load_max=cfg.EVENING_LOAD_MAX,
        seed_offset=300,
    )

    night = generate_offpeak_uniform(
        num_requests=total_night,
        start_time=cfg.h2s(*cfg.OFFPEAK_NIGHT_START),
        end_time=cfg.h2s(*cfg.OFFPEAK_NIGHT_END),
        intensity=cfg.NIGHT_INTENSITY,
        ratio_origin1=cfg.NIGHT_RATIO_ORIGIN1,
        ratio_dest1=cfg.NIGHT_RATIO_DEST1,
        ratio_other=cfg.NIGHT_RATIO_OTHER,
        load_min=cfg.NIGHT_LOAD_MIN,
        load_max=cfg.NIGHT_LOAD_MAX,
        seed_offset=400,
    )

    # 统一按到达时间排序 / merge and sort by arrival time
    requests = sorted(morning + day + evening + night, key=lambda r: r.arrival_time)

    # 统一重新编号，确保请求 ID 唯一 / reindex IDs to guarantee uniqueness.
    for new_id, req in enumerate(requests, start=1):
        req.id = new_id

    return requests
