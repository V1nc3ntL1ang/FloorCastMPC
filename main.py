from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from models import config as cfg
from scheduler.baseline_scheduler import assign_requests_greedy, simulate_dispatch
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
from scheduler.mpc_scheduler import assign_requests_mpc
from scheduler.mpc_scheduler.prediction_api import load_destination_model


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

    if name == "mpc":
        weekday_idx = DAY_NAME_TO_WEEKDAY.get(day_label, 0)
        assign_fn(requests_copy, elevators, weekday=weekday_idx)
    else:
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
        zero_wait_count=passenger_metrics.zero_wait_count,
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

DAY_NAME_TO_WEEKDAY = {label: idx for idx, (label, _) in enumerate(DAY_SCHEDULE)}


def _maybe_load_destination_model() -> None:
    path = os.environ.get("DEST_MODEL_PATH", "").strip()
    if not path:
        return
    try:
        load_destination_model(path)
        print(f"[DestPredictor] Loaded destination model from: {path}")
    except Exception as exc:
        print(f"[DestPredictor] Failed to load model '{path}': {exc}")


def _prepare_online_learning_run_dir() -> str | None:
    base = Path(cfg.ONLINE_LEARNING_DATA_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / f"run_{timestamp}"
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(
            f"[DestPredictor] Failed to create online-learning dir '{run_dir}': {exc}"
        )
        return None
    return str(run_dir)


def _persist_online_learning_data(
    base_dir: str,
    day_index: int,
    day_label: str,
    weekday_index: int,
    result: Dict[str, object],
) -> None:
    if not base_dir:
        return

    elevators = result.get("elevators", [])
    records: List[Dict[str, float | int]] = []
    for elev in elevators:
        for req in getattr(elev, "served_requests", []):
            origin = getattr(req, "origin", None)
            destination = getattr(req, "destination", None)
            arrival = getattr(req, "arrival_time", None)
            if origin is None or destination is None or arrival is None:
                continue
            load = float(getattr(req, "load", 0.0))
            records.append(
                {
                    "origin": int(origin),
                    "destination": int(destination),
                    "arrival_time": float(arrival),
                    "load": load,
                    "weekday": int(weekday_index),
                }
            )

    if not records:
        return

    payload = {
        "day_index": int(day_index),
        "day_label": day_label,
        "weekday": int(weekday_index),
        "timestamp": datetime.now().isoformat(),
        "request_count": len(records),
        "requests": records,
    }

    filename = f"{day_index:02d}_{day_label.lower()}.json"
    path = Path(base_dir) / filename
    try:
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[DestPredictor] Failed to write online-learning data '{path}': {exc}")


def _invoke_offline_training(data_dir: str | None) -> None:
    if not data_dir:
        return
    data_path = Path(data_dir)
    if not data_path.exists():
        return
    if not any(data_path.glob("*.json")):
        print(
            "[DestPredictor] No online-learning data collected; skip offline training."
        )
        return

    script = cfg.ONLINE_LEARNING_TRAIN_SCRIPT
    if not script:
        print("[DestPredictor] No training script configured; skip offline training.")
        return

    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = Path.cwd() / script_path
    if not script_path.exists():
        print(f"[DestPredictor] Training script not found: {script_path}")
        return

    cmd = [
        sys.executable,
        str(script_path),
        "--data-dir",
        str(data_path),
        "--epochs",
        str(max(1, int(cfg.ONLINE_LEARNING_EPOCHS))),
        "--batch-size",
        str(max(1, int(cfg.ONLINE_LEARNING_BATCH_SIZE))),
        "--learning-rate",
        str(float(cfg.ONLINE_LEARNING_LEARNING_RATE)),
        "--l2",
        str(float(cfg.ONLINE_LEARNING_L2)),
    ]

    if cfg.ONLINE_LEARNING_LOAD_MODEL_PATH:
        cmd.extend(["--load-model", cfg.ONLINE_LEARNING_LOAD_MODEL_PATH])
    if cfg.ONLINE_LEARNING_SAVE_MODEL_PATH:
        save_path = Path(cfg.ONLINE_LEARNING_SAVE_MODEL_PATH)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--save-model", str(save_path)])

    print("[DestPredictor] Starting offline training:")
    print("  $", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        print("[DestPredictor] Offline training completed.")
    except subprocess.CalledProcessError as exc:
        print(
            f"[DestPredictor] Offline training failed with exit code {exc.returncode}."
        )


def main() -> None:
    _maybe_load_destination_model()

    online_data_dir = None
    if cfg.ONLINE_LEARNING_ENABLE:
        online_data_dir = _prepare_online_learning_run_dir()

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

        weekday_index = DAY_NAME_TO_WEEKDAY.get(day_label, day_index % 7)

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

            if (
                cfg.ONLINE_LEARNING_ENABLE
                and strat_name == "mpc"
                and online_data_dir is not None
            ):
                _persist_online_learning_data(
                    online_data_dir,
                    day_index,
                    day_label,
                    weekday_index,
                    result,
                )

    enable_global_plot = cfg.SIM_ENABLE_PLOTS or cfg.SIM_ENABLE_PLOTS_GLOBAL
    enable_time_plot = cfg.SIM_ENABLE_PLOTS or cfg.SIM_ENABLE_PLOTS_TIME
    enable_dist_plot = cfg.SIM_ENABLE_PLOTS or cfg.SIM_ENABLE_PLOTS_DISTRIBUTION

    aggregated_waits: Dict[str, List[float]] | None = (
        {"baseline": [], "mpc": []} if enable_dist_plot else None
    )

    if enable_global_plot or enable_time_plot or enable_dist_plot:
        for result in results:
            strat_name = result["name"]
            day_label = result["day"]
            elevator_list = result["elevators"]

            if enable_dist_plot and aggregated_waits is not None:
                aggregated_waits.setdefault(strat_name, []).extend(result["wait_times"])

            if enable_global_plot:
                title_label = f"{day_label} — {strat_name.title()} Strategy"
                base_filename = f"{day_label.lower()}_{strat_name}"
                plot_elevator_movements(
                    elevator_list,
                    filename=os.path.join(
                        DEFAULT_PLOT_DIR,
                        f"elevator_schedule_global_{base_filename}.png",
                    ),
                    strategy_label=title_label,
                )

            if enable_time_plot:
                title_label = f"{day_label} — {strat_name.title()} Strategy"
                base_filename = f"{day_label.lower()}_{strat_name}"
                plot_elevator_movements_time(
                    elevator_list,
                    filename=os.path.join(
                        DEFAULT_PLOT_DIR,
                        f"elevator_schedule_time_global_{base_filename}.png",
                    ),
                    strategy_label=title_label,
                )

        if enable_dist_plot and aggregated_waits is not None:
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

    if cfg.ONLINE_LEARNING_ENABLE:
        _invoke_offline_training(online_data_dir)


if __name__ == "__main__":
    main()
