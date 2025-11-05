from dataclasses import dataclass
import heapq
import math

import config as cfg
from models.energy import segment_energy
from models.kinematics import travel_time


WAIT_PENALTY_SCALE = cfg.WAIT_PENALTY_SCALE
WAIT_PENALTY_EXPONENT = cfg.WAIT_PENALTY_EXPONENT
WAIT_PENALTY_THRESHOLD = cfg.WAIT_PENALTY_THRESHOLD
EMPTYLOAD_PENALTY_MULTIPLIER = cfg.EMPTYLOAD_PENALTY_MULTIPLIER


@dataclass
class PassengerMetrics:
    total_passenger_time: float
    total_wait_time: float
    total_in_cab_time: float
    wait_penalty_total: float
    served_count: int


@dataclass
class ObjectiveBreakdown:
    total_cost: float
    wait_cost: float
    ride_cost: float
    running_energy_cost: float
    emptyload_energy_cost: float


def wait_penalty(wait_time: float) -> float:
    """
    Piecewise (truncated) super-linear penalty for passenger waiting time.
    仅当等待时间超过阈值时施加额外非线性惩罚。

    参数:
        wait_time : 等待时间 (s)
    超参:
        WAIT_PENALTY_SCALE     - 时间归一化尺度 (s)
        WAIT_PENALTY_EXPONENT  - 非线性指数 (>1)
        WAIT_PENALTY_THRESHOLD - 开始施加非线性惩罚的阈值 (s)
    """
    if wait_time <= 0.0:
        return 0.0

    scale = max(WAIT_PENALTY_SCALE, 1e-6)
    exponent = max(WAIT_PENALTY_EXPONENT, 1.0)
    threshold = max(WAIT_PENALTY_THRESHOLD, 0.0)

    if wait_time <= threshold:
        # 阈值以下 → 线性惩罚（可直接等同于时间本身）
        return wait_time
    else:
        # 超过阈值部分施加非线性放大
        excess = wait_time - threshold
        normalized = excess / scale
        nonlinear_penalty = excess * (1.0 + normalized**exponent)
        return threshold + nonlinear_penalty


def summarize_passenger_metrics(served_requests) -> PassengerMetrics:
    """
    Aggregate passenger-centric statistics / 汇总乘客相关指标。
    返回乘客总时间、等待、轿厢内时间、惩罚值以及服务数量。
    """
    total_passenger_time = 0.0
    total_wait_time = 0.0
    total_in_cab_time = 0.0
    total_wait_penalty = 0.0
    served_count = 0

    for req in served_requests:
        arr = getattr(req, "arrival_time", None)
        origin_arrival = getattr(req, "origin_arrival_time", None)
        dest_arrival = getattr(req, "destination_arrival_time", None)

        if arr is None or dest_arrival is None:
            continue

        served_count += 1
        trip_total = max(dest_arrival - arr, 0.0)
        total_passenger_time += trip_total

        if origin_arrival is not None:
            wait = max(origin_arrival - arr, 0.0)
            total_wait_time += wait
            total_wait_penalty += wait_penalty(wait)
            total_in_cab_time += max(dest_arrival - origin_arrival, 0.0)
        else:
            total_in_cab_time += trip_total

    return PassengerMetrics(
        total_passenger_time=total_passenger_time,
        total_wait_time=total_wait_time,
        total_in_cab_time=total_in_cab_time,
        wait_penalty_total=total_wait_penalty,
        served_count=served_count,
    )


def compute_objective(
    wait_time: float,
    in_cab_time: float,
    emptyload_energy: float,
    running_energy: float,
    *,
    wait_penalty_value: float | None = None,
) -> ObjectiveBreakdown:
    """
    Compute weighted losses for waiting, riding, and energy usage /
    计算等待、乘坐与能耗的加权损失。

    Parameters / 参数
    -----------------
    wait_time: cumulative waiting time in seconds / 乘客等待总时间（秒）。
    in_cab_time: cumulative in-cab time in seconds / 乘客乘坐总时间（秒）。
    emptyload_energy: energy spent running empty (J) / 空载行驶能耗（焦耳）。
    running_energy: total traction + standby energy (J) / 总牵引加待机能耗（焦耳）。
    """
    wait_penalty_value = (
        wait_penalty(wait_time) if wait_penalty_value is None else wait_penalty_value
    )
    wait_cost = cfg.WEIGHT_TIME * wait_penalty_value
    ride_cost = cfg.WEIGHT_TIME * in_cab_time
    running_energy_cost = cfg.WEIGHT_ENERGY * running_energy
    extra_multiplier = max(EMPTYLOAD_PENALTY_MULTIPLIER - 1.0, 0.0)
    emptyload_energy_cost = cfg.WEIGHT_ENERGY * emptyload_energy * extra_multiplier

    total_cost = wait_cost + ride_cost + running_energy_cost + emptyload_energy_cost

    return ObjectiveBreakdown(
        total_cost=total_cost,
        wait_cost=wait_cost,
        ride_cost=ride_cost,
        running_energy_cost=running_energy_cost,
        emptyload_energy_cost=emptyload_energy_cost,
    )


def _srpt_flow_lb_speed_c(jobs, c: int) -> float:
    """
    jobs: list[(arrival_time, service_amount)] with time units aligned to travel_time
    c: total service rate (= number of elevators)
    returns: FLOW_LB = ∫ N(t) dt under SRPT on a speed-c preemptive single server
    """
    if not jobs:
        return 0.0
    jobs = sorted((float(a), float(s)) for a, s in jobs)
    i, n = 0, len(jobs)
    t = jobs[0][0]
    N = 0
    FLOW_LB = 0.0
    # heap of (remaining_service, arrival_time)
    heap = []
    service_rate = max(float(c), 1e-9)
    while i < n or heap:
        if not heap and i < n and t < jobs[i][0]:
            t = jobs[i][0]
        while i < n and jobs[i][0] <= t:
            a, s = jobs[i]
            heapq.heappush(heap, (s, a))
            N += 1
            i += 1
        if not heap:
            continue
        s_rem, a_top = heap[0]
        next_arrival = jobs[i][0] if i < n else math.inf
        complete_time = t + s_rem / service_rate
        if complete_time <= next_arrival:
            dt = complete_time - t
            FLOW_LB += N * dt
            t = complete_time
            heapq.heappop(heap)
            N -= 1
        else:
            dt = next_arrival - t
            FLOW_LB += N * dt
            t = next_arrival
            new_s = max(s_rem - service_rate * dt, 0.0)
            heapq.heapreplace(heap, (new_s, a_top))
    return max(FLOW_LB, 0.0)


def compute_theoretical_limit(
    requests,
) -> tuple[ObjectiveBreakdown, float, float, float, float]:
    """
    SRPT-based lower bound consistent with compute_objective / 与 compute_objective
    一致的 SRPT 理论下界，等待惩罚通过 Jensen 不等式估计总和下界。
    """

    jobs = []
    total_in_cab_time = 0.0
    min_running_energy = 0.0  # 牵引能耗下界

    for req in requests:
        origin = getattr(req, "origin", None)
        destination = getattr(req, "destination", None)
        if origin is None or destination is None or origin == destination:
            continue

        load = getattr(req, "load", 0.0)
        arrival_time = getattr(req, "arrival_time", getattr(req, "arrival", 0.0))
        ride_time = max(travel_time(load, origin, destination), 0.0)

        total_in_cab_time += ride_time
        jobs.append((arrival_time, ride_time))

        distance = abs(destination - origin) * cfg.BUILDING_FLOOR_HEIGHT
        direction = "up" if destination > origin else "down"
        min_running_energy += segment_energy(load, distance, direction)

    elevator_count = max(int(cfg.ELEVATOR_COUNT), 1)
    service_rate = max(float(elevator_count), 1e-9)
    flow_lb = _srpt_flow_lb_speed_c(jobs, elevator_count)
    total_service = sum(s for _, s in jobs)
    wait_lower_bound = max(flow_lb - total_service / service_rate, 0.0)
    job_count = len(jobs)
    if job_count == 0:
        wait_penalty_value = 0.0
    else:
        avg_wait = wait_lower_bound / job_count
        # Jensen lower bound: total penalty >= n * f(avg wait)
        wait_penalty_value = job_count * wait_penalty(avg_wait)

    breakdown = compute_objective(
        wait_time=wait_lower_bound,
        in_cab_time=total_in_cab_time,
        emptyload_energy=0.0,
        running_energy=min_running_energy,
        wait_penalty_value=wait_penalty_value,
    )

    return (
        breakdown,
        total_in_cab_time,
        min_running_energy,
        wait_lower_bound,
        wait_penalty_value,
    )
