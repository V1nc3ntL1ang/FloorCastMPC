import os
import random
from datetime import datetime
from typing import Tuple


def h2s(hour, minute: int = 0) -> float:
    """
    Convert time-of-day to seconds / 将时刻转换为秒数.
    支持以下输入形式：
      - 两个整数：h2s(7, 30)
      - 单个整数：h2s(7)
      - 字符串：h2s("7:30") 或 h2s("18:45")
    """
    if isinstance(hour, str):
        parts = hour.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    return hour * 3600.0 + minute * 60.0


def duration_seconds(start, end) -> float:
    """Compute interval length in seconds (cross-day safe) / 计算时间段长度（秒），支持跨日。"""
    if isinstance(start, tuple):
        start_s = h2s(*start)
    else:
        start_s = h2s(start)
    if isinstance(end, tuple):
        end_s = h2s(*end)
    else:
        end_s = h2s(end)
    if end_s < start_s:
        end_s += 24 * 3600  # 跨日修正
    return end_s - start_s


def validate_ratios(
    r_origin1: float, r_dest1: float, r_other: float
) -> Tuple[float, float]:
    """Normalize ratios and return cumulative cut-offs / 归一化方向比例并返回累计边界。"""
    total = r_origin1 + r_dest1 + r_other
    if total <= 0:
        raise ValueError("All ratios are zero or negative.")

    r_origin1 /= total
    r_dest1 /= total
    r_other /= total

    c1 = r_origin1
    c2 = r_origin1 + r_dest1
    return c1, c2


def rand_upper_floor(max_floor: int) -> int:
    """Randomly select a floor in [2, max_floor] / 随机取 2..max_floor 的楼层。"""
    if max_floor < 2:
        raise ValueError("max_floor must be at least 2.")
    return random.randint(2, max_floor)


def rand_other_pair(max_floor: int) -> Tuple[int, int]:
    """Return two distinct non-1 floors / 返回两个不等且不为 1 的楼层（范围 2..max_floor）。"""
    a = rand_upper_floor(max_floor)
    b = rand_upper_floor(max_floor)
    while b == a:
        b = rand_upper_floor(max_floor)
    return a, b


# ============================================================
# Logging & Result Summaries
# ============================================================


def ensure_directory(path: str):
    """Create directory when missing / 若目录不存在则创建。"""
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def plot_elevator_movements(
    elevators,
    filename="/home/v1nc3nt/WinDesktop/SCUT/作业/优化方法/LoadAwareElevator/results/plots/elevator_schedule.png",
):
    """
    Plot elevator service schedule (floor vs. task index) / 绘制电梯服务序列（楼层-任务索引）。
    每部电梯的服务顺序依次展示。
    """
    try:
        # Limit BLAS/OpenMP threads to keep sandbox稳定
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
        os.environ.setdefault("KMP_AFFINITY", "disabled")

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"[Plot Skipped] {exc}")
        return

    ensure_directory(os.path.dirname(filename))
    plt.figure(figsize=(16, 10))
    colors = ["C0", "C1", "C2", "C3", "C4", "C5"]

    for i, elev in enumerate(elevators):
        floors = []
        tasks = []
        current_task = 0

        for req in elev.served_requests:
            floors += [req.origin, req.destination]
            tasks += [current_task, current_task + 1]
            current_task += 1

        if floors:
            plt.plot(
                tasks,
                floors,
                marker="o",
                color=colors[i % len(colors)],
                label=f"Elevator {elev.id}",
            )

    plt.xlabel("Task Index")
    plt.ylabel("Floor Level")
    plt.title("Elevator Service Schedule (Baseline Strategy)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"[Plot Saved] Elevator movement plot saved to: {filename}")


def plot_elevator_movements_time(
    elevators,
    filename="/home/v1nc3nt/WinDesktop/SCUT/作业/优化方法/LoadAwareElevator/results/plots/elevator_schedule_time.png",
):
    """Plot elevator services with time on the horizontal axis."""

    try:
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
        os.environ.setdefault("KMP_AFFINITY", "disabled")

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter
    except Exception as exc:
        print(f"[Plot Skipped] {exc}")
        return

    ensure_directory(os.path.dirname(filename))
    plt.figure(figsize=(12, 6))
    colors = ["C0", "C1", "C2", "C3", "C4", "C5"]

    for i, elev in enumerate(elevators):
        color = colors[i % len(colors)]
        requests = sorted(
            elev.served_requests,
            key=lambda r: (
                getattr(r, "origin_arrival_time", None)
                or getattr(r, "pickup_time", float("inf"))
            ),
        )

        if not requests:
            continue

        first_req = requests[0]
        start_time = (
            getattr(first_req, "origin_arrival_time", None)
            or getattr(first_req, "pickup_time", None)
            or 0.0
        )
        timeline = [(start_time, getattr(elev, "initial_floor", elev.floor))]

        def append_point(time_value, floor_value):
            if time_value is None or floor_value is None:
                return
            last_time, last_floor = timeline[-1]
            if time_value == last_time and floor_value == last_floor:
                return
            timeline.append((time_value, floor_value))

        for req in requests:
            arrival_origin = getattr(req, "origin_arrival_time", None)
            pickup_time = getattr(req, "pickup_time", None)
            dest_arrival = getattr(req, "destination_arrival_time", None)
            dropoff_time = getattr(req, "dropoff_time", None)

            if arrival_origin is None:
                arrival_origin = pickup_time
            if dest_arrival is None:
                dest_arrival = dropoff_time

            append_point(arrival_origin, req.origin)

            if pickup_time is not None:
                append_point(pickup_time, req.origin)

            append_point(dest_arrival, req.destination)

            if dropoff_time is not None:
                append_point(dropoff_time, req.destination)

        xs, ys = zip(*timeline)
        plt.plot(xs, ys, color=color, linewidth=1.6, alpha=0.9, label=f"Elevator {elev.id}")
        plt.scatter(xs, ys, color=color, s=12)

    plt.xlabel("Time of Day")
    plt.ylabel("Floor Level")
    plt.title("Elevator Service Timeline (Baseline Strategy)")
    ax = plt.gca()

    def _format_hhmm(x, pos):
        total = int(max(x, 0)) % (24 * 3600)
        hour = total // 3600
        minute = (total % 3600) // 60
        return f"{hour:02d}:{minute:02d}"

    ax.xaxis.set_major_formatter(FuncFormatter(_format_hhmm))
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"[Plot Saved] Elevator timeline plot saved to: {filename}")


def print_elevator_queues(elevators):
    """
    Print served requests for each elevator / 输出各电梯的服务队列。
    """
    print("\n=== Elevator Queues ===")
    for elev in elevators:
        print(f"Elevator {elev.id}:")
        if not elev.served_requests:
            print("  (No requests assigned)")
            continue
        for req in elev.served_requests:
            print(
                f"  Req#{req.id}: Floor {req.origin} → {req.destination} | Load={req.load:.1f}kg"
            )
    print("========================\n")


def _format_time(value):
    """Pretty-print time value / 时间值格式化。"""
    return f"{value:.1f}s" if value is not None else "N/A"


def _format_table(value, width):
    """Pad table cell / 表格列格式化。"""
    return f"{value:>{width}.1f}" if value is not None else "N/A".rjust(width)


def log_results(
    elevators,
    total_time,
    total_energy,
    total_cost,
    *,
    outdir="/home/v1nc3nt/WinDesktop/SCUT/作业/优化方法/LoadAwareElevator/results/summary",
):
    """
    Enhanced logging with per-elevator/per-request views / 输出增强日志（按电梯与按请求）。
    """
    ensure_directory(outdir)

    by_elevator_path = os.path.join(outdir, "summary_by_elevator.txt")
    with open(by_elevator_path, "w", encoding="utf-8") as f:
        f.write("=== Elevator Service Summary (by Elevator) ===\n")
        f.write(f"Generated at: {datetime.now()}\n")
        f.write(f"Total Time: {total_time:.2f} s\n")
        f.write(f"Total Energy: {total_energy:.2f} J\n")
        f.write(f"Total Objective Cost: {total_cost:.2f}\n\n")

        for elev in elevators:
            f.write(
                f"[Elevator {elev.id}] Served {len(elev.served_requests)} requests\n"
            )
            if not elev.served_requests:
                f.write("  (No requests)\n\n")
                continue

            for req in elev.served_requests:
                pickup = getattr(req, "pickup_time", None)
                dropoff = getattr(req, "dropoff_time", None)
                wait_time = pickup - req.arrival_time if pickup is not None else None
                ride_time = (
                    dropoff - pickup
                    if pickup is not None and dropoff is not None
                    else None
                )
                total_duration = (
                    dropoff - req.arrival_time if dropoff is not None else None
                )

                f.write(
                    "  Req#{rid:03d}: {origin:02d} → {dest:02d} | "
                    "Load={load:.1f}kg | Arr={arr:.1f}s | "
                    "Pick={pick} | Drop={drop} | Wait={wait} | "
                    "Ride={ride} | Total={total}\n".format(
                        rid=req.id,
                        origin=req.origin,
                        dest=req.destination,
                        load=req.load,
                        arr=req.arrival_time,
                        pick=_format_time(pickup),
                        drop=_format_time(dropoff),
                        wait=_format_time(wait_time),
                        ride=_format_time(ride_time),
                        total=_format_time(total_duration),
                    )
                )
            f.write("\n")

    print(f"[Log Saved] Elevator summary → {by_elevator_path}")

    all_requests = []
    for elev in elevators:
        for req in elev.served_requests:
            all_requests.append((elev.id, req))

    all_requests.sort(key=lambda x: x[1].arrival_time)

    by_request_path = os.path.join(outdir, "summary_by_request.txt")
    with open(by_request_path, "w", encoding="utf-8") as f:
        f.write("=== Request Timeline Summary (by Request) ===\n")
        f.write(f"Generated at: {datetime.now()}\n")
        f.write(f"Total Elevators: {len(elevators)}\n")
        f.write(f"Total Requests: {len(all_requests)}\n\n")

        header = (
            "ReqID | Elevator | Origin→Dest | Load(kg) | Arrive(s) | Pickup(s) | Dropoff(s) "
            "| Wait(s) | Ride(s) | Total(s)\n"
        )
        f.write(header)
        f.write("-" * len(header) + "\n")

        for eid, req in all_requests:
            pickup = getattr(req, "pickup_time", None)
            dropoff = getattr(req, "dropoff_time", None)
            wait_time = pickup - req.arrival_time if pickup is not None else None
            ride_time = (
                dropoff - pickup if pickup is not None and dropoff is not None else None
            )
            total_duration = dropoff - req.arrival_time if dropoff is not None else None

            f.write(
                f"{req.id:4d} | {eid:8d} | "
                f"{req.origin:2d}→{req.destination:2d} | "
                f"{req.load:8.1f} | "
                f"{req.arrival_time:9.1f} | {_format_table(pickup, 9)} | {_format_table(dropoff, 9)} | "
                f"{_format_table(wait_time, 7)} | {_format_table(ride_time, 7)} | {_format_table(total_duration, 8)}\n"
            )

    print(f"[Log Saved] Request summary → {by_request_path}")
