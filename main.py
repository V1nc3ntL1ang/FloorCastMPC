from models.baseline import assign_requests_baseline, simulate_baseline
from models.objective import compute_objective
from models.request import generate_requests_day
from models.utils import (
    log_results,
    plot_elevator_movements,
    plot_elevator_movements_time,
    print_elevator_queues,
)
from models.variables import ElevatorState
import config as cfg


def main():
    # 1. 生成请求
    requests = generate_requests_day(cfg.SIM_TOTAL_REQUESTS)

    # 2. 初始化电梯
    elevators = [ElevatorState(id=k + 1, floor=1) for k in range(cfg.ELEVATOR_COUNT)]

    # 3. 基线调度与模拟
    assign_requests_baseline(requests, elevators)
    system_time, total_energy, served_requests = simulate_baseline(elevators)
    (
        total_cost,
        passenger_total_time,
        passenger_wait_time,
        passenger_in_cab_time,
        served_count,
    ) = compute_objective(served_requests, total_energy)

    # 4. 输出与可视化
    print_elevator_queues(elevators)

    if cfg.SIM_ENABLE_LOG:
        log_results(
            elevators,
            system_time,
            total_energy,
            total_cost,
            passenger_total_time,
            passenger_wait_time,
            passenger_in_cab_time,
        )

    if cfg.SIM_ENABLE_PLOTS:
        plot_elevator_movements(elevators)
        plot_elevator_movements_time(elevators)

    print(
        f"Passenger Time: {passenger_total_time:.2f}s "
        f"(wait {passenger_wait_time:.2f}s | in-cab {passenger_in_cab_time:.2f}s) | "
        f"System Active Time: {system_time:.2f}s | "
        f"Total Energy: {total_energy:.2f}J | "
        f"Served Requests: {served_count} | "
        f"Cost: {total_cost:.2f}"
    )


if __name__ == "__main__":
    main()
