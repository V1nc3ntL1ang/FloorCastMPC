import config as cfg
from models.kinematics import travel_time
from models.temporal import hold_time
from models.energy import segment_energy


def assign_requests_baseline(requests, elevators):
    """Greedy nearest-floor assignment / 贪心分配至最近楼层的电梯。"""
    for e in elevators:
        e.queue = []
        e.served_requests = []

    for req in requests:
        best_elev = min(elevators, key=lambda e: abs(e.floor - req.origin))
        best_elev.queue.append(req)
        best_elev.served_requests.append(req)


def simulate_baseline(elevators):
    """
    Execute baseline simulation and return (total_time, total_energy) /
    顺序执行基线调度，返回总时间与总能耗。
    """
    total_time = 0.0
    total_energy = 0.0

    for elev in elevators:
        current_floor = elev.floor
        current_load = 0.0
        current_time = 0.0

        while elev.queue:
            req = elev.queue.pop(0)
            direction_to_origin = "up" if req.origin > current_floor else "down"

            # move to origin / 前往请求起点
            t_to_origin = travel_time(current_load, current_floor, req.origin)
            arrival_at_origin = current_time + t_to_origin
            e_to_origin = segment_energy(
                current_load,
                abs(req.origin - current_floor) * cfg.BUILDING_FLOOR_HEIGHT,
                direction_to_origin,
            )
            total_energy += e_to_origin

            # 若电梯提前到达则等待乘客 / wait if the cab arrives early
            wait_for_request = max(req.arrival_time - arrival_at_origin, 0.0)

            # boarding hold / 开门候客
            t_hold = hold_time(req.load, 0)
            departure_time = arrival_at_origin + wait_for_request + t_hold
            req.pickup_time = departure_time

            # move to destination / 载客前往目的楼层
            t_to_dest = travel_time(req.load, req.origin, req.destination)
            direction_to_dest = "up" if req.destination > req.origin else "down"
            e_to_dest = segment_energy(
                req.load,
                abs(req.destination - req.origin) * cfg.BUILDING_FLOOR_HEIGHT,
                direction_to_dest,
            )
            total_energy += e_to_dest
            dropoff_time = departure_time + t_to_dest
            req.dropoff_time = dropoff_time

            current_floor = req.destination
            current_load = 0.0
            current_time = dropoff_time
            # 汇总运行时间（忽略等待段以保持与旧目标一致） / accumulate travel time components
            total_time += t_to_origin + t_hold + t_to_dest

    return total_time, total_energy
