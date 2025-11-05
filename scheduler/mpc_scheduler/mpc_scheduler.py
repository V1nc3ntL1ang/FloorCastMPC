"""
Rolling-horizon (MPC-lite) scheduler without external solvers /
滚动时域（轻量 MPC）调度器，在不依赖外部求解器的情况下，为电梯分配请求。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from models import config as cfg
from models.energy import segment_energy, standby_energy
from models.kinematics import travel_time
from models.temporal import hold_time
from scheduler.mpc_scheduler.prediction_api import (
    is_ready as _predictor_ready,
    predict_dest_distribution as _predict_distribution,
)


MPC_LOOKAHEAD_WINDOW = cfg.MPC_LOOKAHEAD_WINDOW
MPC_MAX_BATCH = cfg.MPC_MAX_BATCH
SECONDS_PER_DAY = 24 * 3600.0
DEST_TOP_K = 3


@dataclass
class _PlanState:
    floor: int
    time: float


def assign_requests_mpc(
    requests: List[object],
    elevators: List[object],
    *,
    lookahead_window: float | None = None,
    max_batch: int | None = None,
    weekday: int | None = None,
) -> None:
    """
    Assign requests using a rolling-horizon heuristic /
    采用滚动时域启发式将请求分配给电梯。

    Parameters / 参数
    -----------------
    lookahead_window:
        Maximum seconds beyond earliest unassigned arrival / 视窗长度（秒）。
    max_batch:
        Maximum candidate requests per iteration / 每轮评估的候选请求数。
    """
    if not elevators:
        return

    horizon = MPC_LOOKAHEAD_WINDOW if lookahead_window is None else lookahead_window
    batch_limit = MPC_MAX_BATCH if max_batch is None else max_batch
    if batch_limit <= 0:
        batch_limit = max(len(elevators) * 3, 1)

    for elev in elevators:
        elev.queue = []
        elev.served_requests = []

    if not requests:
        return

    unassigned = list(sorted(requests, key=lambda r: r.arrival_time))
    plans = {elev.id: _PlanState(floor=elev.floor, time=0.0) for elev in elevators}
    elevator_lookup = {elev.id: elev for elev in elevators}
    eps = 1e-9
    num_elevators = len(elevators)
    tie_cursor = 0

    while unassigned:
        earliest_arrival = unassigned[0].arrival_time
        window_limit = earliest_arrival + horizon

        candidate_indices: List[int] = []
        for idx, req in enumerate(unassigned):
            if req.arrival_time <= window_limit:
                candidate_indices.append(idx)
            elif len(candidate_indices) < batch_limit:
                candidate_indices.append(idx)
            if len(candidate_indices) >= batch_limit:
                break

        if not candidate_indices:
            candidate_indices = list(range(min(batch_limit, len(unassigned))))

        candidate_options: List[Tuple[float, float, float, int, int, int]] = []
        for idx in candidate_indices:
            req = unassigned[idx]
            for elev_idx, elev in enumerate(elevators):
                estimate = _estimate_incremental_cost(
                    plans[elev.id], req, weekday=weekday
                )
                if estimate is None:
                    continue
                cost, finish_time, passenger_time = estimate
                candidate_options.append(
                    (cost, finish_time, passenger_time, idx, elev.id, elev_idx)
                )

        if not candidate_options:
            # Fallback to least-busy elevator / 回退到最空闲电梯以避免停滞。
            idx = candidate_indices[0]
            req = unassigned.pop(idx)
            target_id = min(plans, key=lambda eid: plans[eid].time)
            target_index = next(
                (i for i, e in enumerate(elevators) if e.id == target_id), 0
            )
            estimate = _estimate_incremental_cost(plans[target_id], req, weekday=weekday)
            finish_time = plans[target_id].time
            if estimate is not None:
                finish_time = estimate[1]
            _apply_assignment(elevator_lookup[target_id], req)
            plans[target_id].time = finish_time
            plans[target_id].floor = req.destination
            tie_cursor = (target_index + 1) % num_elevators
            continue

        min_cost = min(option[0] for option in candidate_options)
        best_cost_options = [
            opt for opt in candidate_options if opt[0] <= min_cost + eps
        ]
        min_finish = min(opt[1] for opt in best_cost_options)
        best_finish_options = [
            opt for opt in best_cost_options if opt[1] <= min_finish + eps
        ]
        min_passenger = min(opt[2] for opt in best_finish_options)
        tied_options = [
            opt for opt in best_finish_options if opt[2] <= min_passenger + eps
        ]

        selected_option = min(
            tied_options,
            key=lambda opt: ((opt[5] - tie_cursor) % num_elevators, opt[5]),
        )
        tie_used = len(tied_options) > 1

        idx, elevator_id = selected_option[3], selected_option[4]
        finish_time = selected_option[1]
        req = unassigned.pop(idx)
        _apply_assignment(elevator_lookup[elevator_id], req)
        plans[elevator_id].time = finish_time
        plans[elevator_id].floor = req.destination
        if tie_used:
            tie_cursor = (selected_option[5] + 1) % num_elevators


def _estimate_incremental_cost(
    plan: _PlanState, request: object, *, weekday: int | None = None
) -> Tuple[float, float, float] | None:
    """Return expected (cost, finish_time, passenger_time) under predicted destinations."""
    candidates = _destination_candidates(request, weekday)
    if not candidates:
        return None

    expected_cost = 0.0
    expected_finish = 0.0
    expected_passenger = 0.0

    for destination, prob in candidates:
        cost, finish_time, passenger_time = _cost_for_destination(plan, request, destination)
        expected_cost += prob * cost
        expected_finish += prob * finish_time
        expected_passenger += prob * passenger_time

    return expected_cost, expected_finish, expected_passenger


def _destination_candidates(request: object, weekday: int | None) -> List[Tuple[int, float]]:
    origin = request.origin
    if _predictor_ready():
        weekday_idx = 0 if weekday is None else int(weekday)
        time_s = float(request.arrival_time % SECONDS_PER_DAY)
        try:
            dist = _predict_distribution(
                origin,
                time_s,
                weekday_idx,
                exclude_origin=True,
            )
        except Exception:
            dist = {}

        if dist:
            items = sorted(dist.items(), key=lambda item: item[1], reverse=True)
            top_items = items[:DEST_TOP_K] if DEST_TOP_K > 0 else items
            total_prob = sum(prob for _, prob in top_items)
            if total_prob > 0:
                return [(int(dest), prob / total_prob) for dest, prob in top_items]

    # Fallback: use the actual request destination with certainty
    destination = int(getattr(request, "destination", origin))
    if destination == origin:
        # ensure we avoid zero-prob degenerate case by allowing same floor when necessary
        return [(destination, 1.0)]
    return [(destination, 1.0)]


def _cost_for_destination(
    plan: _PlanState, request: object, destination: int
) -> Tuple[float, float, float]:
    current_floor = plan.floor
    available_time = plan.time
    origin = request.origin

    travel_to_origin = travel_time(0.0, current_floor, origin)
    arrival_at_origin = available_time + travel_to_origin
    start_service = max(arrival_at_origin, request.arrival_time)
    dwell = hold_time(request.load, 0.0)
    depart_time = start_service + dwell
    travel_to_dest = travel_time(request.load, origin, destination)
    finish_time = depart_time + travel_to_dest

    passenger_time = finish_time - request.arrival_time

    energy = 0.0
    if current_floor != origin:
        distance = abs(current_floor - origin) * cfg.BUILDING_FLOOR_HEIGHT
        energy += segment_energy(0.0, distance, _direction(current_floor, origin))
        energy += standby_energy(travel_to_origin)

    energy += standby_energy(dwell)

    if origin != destination:
        distance = abs(destination - origin) * cfg.BUILDING_FLOOR_HEIGHT
        energy += segment_energy(
            request.load, distance, _direction(origin, destination)
        )
        energy += standby_energy(travel_to_dest)

    total_cost = cfg.WEIGHT_TIME * passenger_time + cfg.WEIGHT_ENERGY * energy
    total_cost += 1e-6 * finish_time

    return total_cost, finish_time, passenger_time


def _apply_assignment(elevator, request: object) -> None:
    elevator.queue.append(request)
    elevator.served_requests.append(request)


def _direction(start: int, end: int) -> str:
    if end > start:
        return "up"
    if end < start:
        return "down"
    return "up"
