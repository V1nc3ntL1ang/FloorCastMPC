import config as cfg
from models.kinematics import travel_time
from models.temporal import hold_time
from models.energy import segment_energy, standby_energy


def assign_requests_greedy(requests, elevators):
    """
    Simple greedy dispatcher: keep queues balanced and prefer nearer cars.
    将请求按等待队列长度 + 距离的贪婪策略分配给电梯。

    基线假设：
      - 分配时只知道 origin（厅呼），不知道 destination（轿厢呼）。
      - 因此只用 origin 更新电梯的“预估位置”，不偷看目的楼层。
    """
    if not elevators:
        return

    for elev in elevators:
        elev.queue = []
        elev.served_requests = []
        elev._forecast_floor = elev.floor

    for req in sorted(requests, key=lambda r: r.arrival_time):
        best = min(
            elevators,
            key=lambda elev: (
                len(elev.queue),
                abs(elev._forecast_floor - req.origin),
                elev.id,
            ),
        )
        best.queue.append(req)

        # ★ 关键：只用 origin 更新，不用 destination
        best._forecast_floor = req.origin

    for elev in elevators:
        if hasattr(elev, "_forecast_floor"):
            delattr(elev, "_forecast_floor")


def simulate_dispatch(elevators):
    """
    Simulate greedy batches per elevator and return metrics /
    按电梯模拟贪婪批处理并返回统计量 (total_time, total_energy, served_requests, emptyload_energy)。

    经典策略特性：
      - 方向优先（collective control）：当前有乘客时，沿一个方向把车内和沿途同向请求都顺路服务完。
      - 同层多上多下：在同一停靠点，可以同时处理多个上客和下客，停靠时间按总上下客载重计算。
    """

    total_time = 0.0
    total_energy = 0.0
    emptyload_energy = 0.0

    for elev in elevators:
        current_floor = elev.floor
        current_time = 0.0
        elev.initial_floor = current_floor

        # 按到达时间排序的待服务请求 / requests sorted by arrival time
        pending = sorted(elev.queue, key=lambda r: r.arrival_time)
        for req in pending:
            req.pickup_time = None
            req.dropoff_time = None
            req.origin_arrival_time = None
            req.destination_arrival_time = None

        waiting = (
            []
        )  # 已到达但尚未上车 / arrived requests waiting on their origin floor
        onboard = []  # 当前电梯内的请求 / passengers currently inside the cab
        service_log = []

        def pull_ready_requests():
            """Move arrived pending requests into the waiting list / 将已到达请求移入等待队列。"""
            nonlocal pending, waiting
            while pending and pending[0].arrival_time <= current_time:
                waiting.append(pending.pop(0))

        def current_load():
            return sum(req.load for req in onboard)

        def travel_between(start_floor, end_floor):
            """Advance time and energy for a trip / 更新跨层行程的时间与能耗。"""
            nonlocal current_floor, current_time, total_time, total_energy, emptyload_energy

            if start_floor == end_floor:
                return

            load = current_load()
            travel_duration = travel_time(load, start_floor, end_floor)
            direction = "up" if end_floor > start_floor else "down"
            distance = abs(end_floor - start_floor) * cfg.BUILDING_FLOOR_HEIGHT
            energy_motion = segment_energy(load, distance, direction)
            energy_idle = standby_energy(travel_duration)

            current_time += travel_duration
            total_time += travel_duration
            total_energy += energy_motion + energy_idle
            current_floor = end_floor

            if load <= 1e-9:
                emptyload_energy += energy_motion + energy_idle

            pull_ready_requests()

        def request_direction(req, reference_floor):
            if req.destination > reference_floor:
                return "up"
            if req.destination < reference_floor:
                return "down"
            return "idle"

        def process_stop(boarders, leavers):
            """
            Handle dwell time, boarding, and alighting /
            处理同一停靠点的开门、上下客：
              - 支持多个乘客同时上车和下车；
              - 停靠时间由上下客总载重通过 hold_time 计算。
            """
            nonlocal current_time, total_time, total_energy

            if not boarders and not leavers:
                return

            # 计算下客总载重（只考虑车内已有乘客）
            leaving_weight = sum(req.load for req in leavers if req in onboard)

            # 下客后当前载重 / remaining capacity
            post_leave_load = max(0.0, current_load() - leaving_weight)
            remaining_capacity = max(0.0, cfg.ELEVATOR_CAPACITY - post_leave_load)

            # 容量约束：能上的先上，剩下的留在 waiting
            if boarders:
                admitted = []
                for req in boarders:
                    if req.load <= remaining_capacity + 1e-9:
                        admitted.append(req)
                        remaining_capacity -= req.load
                boarders = admitted

            arrive_time = current_time  # 电梯到达这一层的时间（开门前）
            boarding_weight = sum(r.load for r in boarders)

            # 关键改动：只要有上或下，就产生停靠时间
            if boarders or leavers:
                dwell = hold_time(boarding_weight, leaving_weight)
            else:
                dwell = 0.0

            current_time += dwell
            total_time += dwell
            total_energy += standby_energy(dwell)

            # 处理下客：他们的 destination_arrival_time = 电梯到达时刻
            for req in leavers:
                if req in onboard:
                    onboard.remove(req)
                req.destination_arrival_time = arrive_time
                req.dropoff_time = current_time

            # 处理上客：他们的 origin_arrival_time = 电梯到达时刻
            for req in boarders:
                if req in waiting:
                    waiting.remove(req)
                req.origin_arrival_time = arrive_time
                req.pickup_time = current_time
                if req not in service_log:
                    service_log.append(req)
                # 如果上车就到达目的楼层（origin == destination == current_floor）
                if req.destination == current_floor:
                    req.dropoff_time = current_time
                    req.destination_arrival_time = arrive_time
                else:
                    onboard.append(req)

            pull_ready_requests()

        # ===== 主循环：直到该电梯的所有请求都服务完 =====
        while pending or waiting or onboard:
            pull_ready_requests()

            if not waiting and not onboard:
                if not pending:
                    break
                # Fast-forward to the next arrival / 若无请求待服务，则跳转到下一到达时刻
                next_req = pending.pop(0)
                if next_req.arrival_time > current_time:
                    idle_duration = next_req.arrival_time - current_time
                    total_energy += standby_energy(idle_duration)
                    current_time = next_req.arrival_time
                waiting.append(next_req)
                pull_ready_requests()

            if not waiting and not onboard:
                continue

            # 如果电梯当前为空，从 waiting 中选一个最近 & 最早到达的 origin 过去接
            if not onboard:
                target_req = min(
                    waiting,
                    key=lambda r: (r.arrival_time, abs(r.origin - current_floor)),
                )

                travel_between(current_floor, target_req.origin)

                # 当前楼层所有已到达的请求
                ready_here = [
                    r
                    for r in waiting
                    if r.origin == current_floor and r.arrival_time <= current_time
                ]
                if not ready_here:
                    continue

                # 选择一个“主请求”，以它的 destination 决定方向
                primary = min(
                    ready_here,
                    key=lambda r: (r.arrival_time, abs(r.destination - current_floor)),
                )
                direction = request_direction(primary, current_floor)

                # 同一层、同向（或目的层即当前层）的请求一起上车 → 多上
                boarders = [
                    r
                    for r in ready_here
                    if request_direction(r, current_floor) in {direction, "idle"}
                ]

                process_stop(boarders, [])

                # 如果这波上客之后没有有效行进方向（全是 idle），则回到主循环重新决策
                if direction == "idle" or not onboard:
                    continue

            else:
                # 根据车内乘客的目的楼层决定行进方向
                dirs = {
                    request_direction(req, current_floor)
                    for req in onboard
                    if request_direction(req, current_floor) != "idle"
                }
                direction = dirs.pop() if dirs else "idle"
                if direction == "idle":
                    # 理论上不会太常见：所有车内乘客目的楼层都等于当前层
                    process_stop([], onboard[:])
                    continue

            # ===== 顺路接人：沿当前方向跑完一趟 =====
            while onboard:
                pull_ready_requests()

                # 根据当前方向，找“顺路”的下一层：
                #   - 车内乘客的目的楼层；
                #   - 同方向的、已到达的 waiting 乘客的 origin 楼层。
                if direction == "up":
                    candidate_floors = [
                        req.destination
                        for req in onboard
                        if req.destination > current_floor
                    ]
                    candidate_floors += [
                        req.origin
                        for req in waiting
                        if req.arrival_time <= current_time
                        and req.origin > current_floor
                        and request_direction(req, req.origin) == "up"
                    ]
                    next_floor = min(candidate_floors) if candidate_floors else None
                else:
                    candidate_floors = [
                        req.destination
                        for req in onboard
                        if req.destination < current_floor
                    ]
                    candidate_floors += [
                        req.origin
                        for req in waiting
                        if req.arrival_time <= current_time
                        and req.origin < current_floor
                        and request_direction(req, req.origin) == "down"
                    ]
                    next_floor = max(candidate_floors) if candidate_floors else None

                if next_floor is None:
                    break

                # 行驶到下一站（可能是有人下车的楼层，也可能是顺路去接人的 origin）
                travel_between(current_floor, next_floor)

                # 多下：所有目的楼层是当前层的车内乘客一起下车
                leavers = [req for req in onboard if req.destination == current_floor]

                # 多上：当前层所有同向（或目的即当前层）的 waiting 乘客一起上车
                ready_here = [
                    r
                    for r in waiting
                    if r.origin == current_floor and r.arrival_time <= current_time
                ]
                boarders = [
                    r
                    for r in ready_here
                    if request_direction(r, current_floor) in {direction, "idle"}
                ]

                process_stop(boarders, leavers)

            # 当前方向服务结束，回到主循环重新决定下一批。

        # 更新电梯最终状态
        elev.floor = current_floor
        elev.queue = []
        elev.served_requests = service_log

    all_served = []
    for elev in elevators:
        all_served.extend(elev.served_requests)

    return total_time, total_energy, all_served, emptyload_energy
