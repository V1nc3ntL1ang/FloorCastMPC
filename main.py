from models.baseline import assign_requests_baseline, simulate_baseline
from models.objective import compute_objective
from models.request import generate_requests_day
from models.utils import log_results, plot_elevator_movements, print_elevator_queues
from models.variables import ElevatorState
import config as cfg


def main():
    # 1. 生成请求
    requests = generate_requests_day(cfg.SIM_TOTAL_REQUESTS)

    # 2. 初始化电梯
    elevators = [ElevatorState(id=k + 1, floor=1) for k in range(cfg.ELEVATOR_COUNT)]

    # 3. 基线调度与模拟
    assign_requests_baseline(requests, elevators)
    total_time, total_energy = simulate_baseline(elevators)
    total_cost = compute_objective(total_time, total_energy)

    # 4. 输出与可视化
    print_elevator_queues(elevators)

    if cfg.SIM_ENABLE_LOG:
        log_results(elevators, total_time, total_energy, total_cost)

    if cfg.SIM_ENABLE_PLOTS:
        plot_elevator_movements(elevators)

    print(
        f"Total Time: {total_time:.2f}s | "
        f"Total Energy: {total_energy:.2f}J | "
        f"Cost: {total_cost:.2f}"
        plot_elevator_movements_time(elevators)
    )


if __name__ == "__main__":
    main()
