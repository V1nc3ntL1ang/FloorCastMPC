from __future__ import annotations

import os
from copy import deepcopy
from typing import Callable, Dict, List, Sequence, Tuple

import config as cfg
from models.baseline_scheduler import assign_requests_greedy, simulate_dispatch
from models.objective import (
    compute_objective,
    compute_theoretical_limit,
    summarize_passenger_metrics,
)
from models.request import generate_requests_weekday, generate_requests_weekend
from models.utils import (
    DEFAULT_PLOT_DIR,
    log_results,
    plot_elevator_movements,
    plot_elevator_movements_time,
    plot_wait_distribution,
)
from models.variables import ElevatorState
from mpc_scheduler import assign_requests_mpc


def _extract_wait_times(served_requests) -> List[float]:
    """Collect wait durations per request / 提取每个请求的等待时间。"""
    waits: List[float] = []
    for req in served_requests:
        arrival = getattr(req, "arrival_time", None)
        origin_arrival = getattr(req, "origin_arrival_time", None)
        pickup = getattr(req, "pickup_time", None)
        if arrival is None:
            continue
        boarding_time = origin_arrival if origin_arrival is not None else pickup
        if boarding_time is None:
            continue
        waits.append(max(boarding_time - arrival, 0.0))
    return waits


def _run_strategy(
    day_label: str,
    day_type: str,
    name: str,
    assign_fn: Callable[[List[object], List[ElevatorState]], None],
    base_requests: List[object],
) -> Dict[str, object]:
    """
    Execute a scheduling strategy and gather metrics /
    执行给定调度策略并收集指标。
    """
    requests_copy = deepcopy(base_requests)
    elevators = [ElevatorState(id=k + 1, floor=1) for k in range(cfg.ELEVATOR_COUNT)]

    assign_fn(requests_copy, elevators)

    (
        system_time,
        total_energy,
        served_requests,
        emptyload_energy,
    ) = simulate_dispatch(elevators)

    passenger_metrics = summarize_passenger_metrics(served_requests)
    running_energy = total_energy

    objective_breakdown = compute_objective(
        passenger_metrics.total_wait_time,
        passenger_metrics.total_in_cab_time,
        emptyload_energy,
        running_energy,
        wait_penalty_value=passenger_metrics.wait_penalty_total,
    )
    (
        theoretical_breakdown,
        theoretical_in_cab_time,
        theoretical_running_energy,
        theoretical_wait_time,
        theoretical_wait_penalty,
    ) = compute_theoretical_limit(served_requests)

    wait_times = _extract_wait_times(served_requests)

    if cfg.SIM_ENABLE_LOG:
        log_results(
            elevators,
            system_time,
            running_energy,
            objective_breakdown,
            passenger_metrics.total_passenger_time,
            passenger_metrics.total_wait_time,
            passenger_metrics.total_in_cab_time,
            passenger_metrics.wait_penalty_total,
            emptyload_energy,
            theoretical_breakdown,
            theoretical_in_cab_time,
            theoretical_running_energy,
            theoretical_wait_time,
            theoretical_wait_penalty,
            strategy_label=f"{day_label}_{name}",
        )

    return {
        "day": day_label,
        "day_type": day_type,
        "name": name,
        "elevators": elevators,
        "system_time": system_time,
        "running_energy": running_energy,
        "emptyload_energy": emptyload_energy,
        "served_count": passenger_metrics.served_count,
        "passenger_total_time": passenger_metrics.total_passenger_time,
        "passenger_wait_time": passenger_metrics.total_wait_time,
        "passenger_in_cab_time": passenger_metrics.total_in_cab_time,
        "wait_penalty": passenger_metrics.wait_penalty_total,
        "objective": objective_breakdown,
        "theoretical": {
            "breakdown": theoretical_breakdown,
            "in_cab_time": theoretical_in_cab_time,
            "running_energy": theoretical_running_energy,
            "wait_time": theoretical_wait_time,
            "wait_penalty": theoretical_wait_penalty,
        },
        "wait_times": wait_times,
    }


DAY_SCHEDULE: Sequence[Tuple[str, str]] = (
    ("Mon", "weekday"),
    ("Tue", "weekday"),
    ("Wed", "weekday"),
    ("Thu", "weekday"),
    ("Fri", "weekday"),
    ("Sat", "weekend"),
    ("Sun", "weekend"),
)


def main() -> None:
    strategies: Sequence[
        Tuple[str, Callable[[List[object], List[ElevatorState]], None]]
    ] = (
        ("baseline", assign_requests_greedy),
        ("mpc", assign_requests_mpc),
    )

    results: List[Dict[str, object]] = []

    for day_index, (day_label, day_type) in enumerate(DAY_SCHEDULE):
        seed_shift = day_index * 114514
        if day_type == "weekday":
            requests = generate_requests_weekday(
                cfg.WEEKDAY_TOTAL_REQUESTS, seed_shift=seed_shift
            )
        else:
            requests = generate_requests_weekend(
                cfg.WEEKEND_TOTAL_REQUESTS, seed_shift=seed_shift
            )

        for strat_name, assign_fn in strategies:
            result = _run_strategy(
                day_label,
                day_type,
                strat_name,
                assign_fn,
                requests,
            )
            result["label"] = f"{day_label}-{strat_name}"
            results.append(result)

    aggregated_waits: Dict[str, List[float]] = {"baseline": [], "mpc": []}

    if cfg.SIM_ENABLE_PLOTS:
        for result in results:
            strat_name = result["name"]
            day_label = result["day"]
            aggregated_waits[strat_name].extend(result["wait_times"])
            title_label = f"{day_label} — {strat_name.title()} Strategy"
            base_filename = f"{day_label.lower()}_{strat_name}"
            elevator_list = result["elevators"]
            plot_elevator_movements(
                elevator_list,
                filename=os.path.join(
                    DEFAULT_PLOT_DIR,
                    f"elevator_schedule_global_{base_filename}.png",
                ),
                strategy_label=title_label,
            )
            plot_elevator_movements_time(
                elevator_list,
                filename=os.path.join(
                    DEFAULT_PLOT_DIR,
                    f"elevator_schedule_time_global_{base_filename}.png",
                ),
                strategy_label=title_label,
            )

        overall_wait_series = [
            (strat.upper(), waits) for strat, waits in aggregated_waits.items()
        ]
        plot_wait_distribution(
            overall_wait_series,
            filename=os.path.join(DEFAULT_PLOT_DIR, "wait_distribution_week.png"),
        )

    weekly_totals = {
        "baseline": {
            "served": 0,
            "wait_time": 0.0,
            "in_cab_time": 0.0,
            "wait_penalty": 0.0,
            "running_energy": 0.0,
            "emptyload_energy": 0.0,
            "objective": 0.0,
        },
        "mpc": {
            "served": 0,
            "wait_time": 0.0,
            "in_cab_time": 0.0,
            "wait_penalty": 0.0,
            "running_energy": 0.0,
            "emptyload_energy": 0.0,
            "objective": 0.0,
        },
    }

    last_day = None
    for result in results:
        obj = result["objective"]
        theo = result["theoretical"]
        name = result["name"]
        day_label = result["day"]
        day_type = result["day_type"]
        if day_label != last_day:
            descriptor = "Weekday" if day_type == "weekday" else "Weekend"
            print(f"\n===== {day_label} ({descriptor}) =====")
            last_day = day_label
        print(f"\nStrategy: {name}")
        print(
            "Served Requests: {served:,} | Active Time: {active:,.2f}s".format(
                served=result["served_count"],
                active=result["system_time"],
            )
        )
        print(
            "Passenger Metrics:"
            " total {total:,.2f}s"
            " (wait {wait:,.2f}s | in-cab {incab:,.2f}s)"
            " | wait penalty {penalty:,.2f}".format(
                total=result["passenger_total_time"],
                wait=result["passenger_wait_time"],
                incab=result["passenger_in_cab_time"],
                penalty=result["wait_penalty"],
            )
        )
        print(
            "Energy Metrics:"
            " running {run:,.2f}J"
            " | empty-load {empty:,.2f}J".format(
                run=result["running_energy"],
                empty=result["emptyload_energy"],
            )
        )
        print("Objective Cost Breakdown:")
        print(
            "  total {total:,.2f} | wait {wait:,.2f} | ride {ride:,.2f} | "
            "running energy {run:,.2f} | empty-load surcharge {empty:,.2f}".format(
                total=obj.total_cost,
                wait=obj.wait_cost,
                ride=obj.ride_cost,
                run=obj.running_energy_cost,
                empty=obj.emptyload_energy_cost,
            )
        )
        print("Theoretical Lower Bound:")
        print(
            "  wait ≥ {wait:,.2f}s (penalty ≥ {penalty:,.2f}) | "
            "ride ≥ {ride:,.2f}s | running energy ≥ {energy:,.2f}J | "
            "cost ≥ {cost:,.2f}".format(
                wait=theo["wait_time"],
                penalty=theo["wait_penalty"],
                ride=theo["in_cab_time"],
                energy=theo["running_energy"],
                cost=theo["breakdown"].total_cost,
            )
        )

        totals = weekly_totals[name]
        totals["served"] += result["served_count"]
        totals["wait_time"] += result["passenger_wait_time"]
        totals["in_cab_time"] += result["passenger_in_cab_time"]
        totals["wait_penalty"] += result["wait_penalty"]
        totals["running_energy"] += result["running_energy"]
        totals["emptyload_energy"] += result["emptyload_energy"]
        totals["objective"] += obj.total_cost

    print("\n===== Weekly Totals =====")
    for strat, totals in weekly_totals.items():
        print(f"\nStrategy: {strat}")
        print(
            "Served Requests: {served:,} | Wait {wait:,.2f}s | In-cab {incab:,.2f}s".format(
                served=totals["served"],
                wait=totals["wait_time"],
                incab=totals["in_cab_time"],
            )
        )
        print(
            "Wait Penalty Sum: {penalty:,.2f} | Running Energy: {energy:,.2f}J | "
            "Empty-load Energy: {empty:,.2f}J".format(
                penalty=totals["wait_penalty"],
                energy=totals["running_energy"],
                empty=totals["emptyload_energy"],
            )
        )
        print("Objective Cost (sum over week): {:.2f}".format(totals["objective"]))


if __name__ == "__main__":
    main()
