import config as cfg
from models.kinematics import travel_time
from models.temporal import hold_time
from models.energy import segment_energy, standby_energy


def assign_requests_baseline(requests, elevators):
    """Assign requests greedily considering earliest availability for each elevator."""

    # Reset assignment containers on each elevator state.
    for e in elevators:
        e.queue = []
        e.served_requests = []

    # Tracks each elevator's projected state after scheduled jobs.
    projected_floor = {e.id: e.floor for e in elevators}
    projected_time = {e.id: 0.0 for e in elevators}
    num_elevators = len(elevators)
    tie_cursor = 0  # ring pointer used for tiebreaks / 环状指针用于平局处理
    eps = 1e-6

    for req in sorted(requests, key=lambda r: r.arrival_time):
        if not elevators:
            break

        candidates = []
        best_ready_time = None

        for idx, elev in enumerate(elevators):
            available_time = projected_time[elev.id]
            current_floor = projected_floor[elev.id]

            travel_duration = travel_time(0.0, current_floor, req.origin)
            arrival_at_origin = available_time + travel_duration
            ready_time = max(arrival_at_origin, req.arrival_time)

            candidates.append(
                {
                    "idx": idx,
                    "elevator": elev,
                    "ready_time": ready_time,
                    "arrival_at_origin": arrival_at_origin,
                    "available_time": available_time,
                }
            )

            if best_ready_time is None or ready_time < best_ready_time:
                best_ready_time = ready_time

        if best_ready_time is None:
            continue

        best_list = [
            c for c in candidates if abs(c["ready_time"] - best_ready_time) <= eps
        ]

        if not best_list:
            continue

        chosen = None

        if len(best_list) == 1:
            chosen = best_list[0]
        else:
            order = [
                ((tie_cursor + shift) % num_elevators) for shift in range(num_elevators)
            ]
            for idx_order in order:
                match = next((c for c in best_list if c["idx"] == idx_order), None)
                if match is not None:
                    chosen = match
                    tie_cursor = (idx_order + 1) % num_elevators
                    break
        if chosen is None:
            chosen = best_list[0]

        best_elevator = chosen["elevator"]
        best_elevator.queue.append(req)
        best_elevator.served_requests.append(req)

        available_time = projected_time[best_elevator.id]
        current_floor = projected_floor[best_elevator.id]
        travel_duration = travel_time(0.0, current_floor, req.origin)
        arrival_at_origin = available_time + travel_duration
        ready_time = max(arrival_at_origin, req.arrival_time)

        dwell = hold_time(req.load, 0.0)
        departure_time = ready_time + dwell
        finish_time = departure_time + travel_time(
            req.load, req.origin, req.destination
        )

        projected_time[best_elevator.id] = finish_time
        projected_floor[best_elevator.id] = req.destination


def simulate_baseline(elevators):
    """Simulate greedy single-elevator batches and return (total_time, total_energy)."""

    total_time = 0.0
    total_energy = 0.0

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
            """Move arrived pending requests into the waiting list."""

            nonlocal pending, waiting
            while pending and pending[0].arrival_time <= current_time:
                waiting.append(pending.pop(0))

        def current_load():
            return sum(req.load for req in onboard)

        def travel_between(start_floor, end_floor):
            """Advance simulation clock and energy for an inter-floor trip."""

            nonlocal current_floor, current_time, total_time, total_energy

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

            pull_ready_requests()

        def request_direction(req, reference_floor):
            if req.destination > reference_floor:
                return "up"
            if req.destination < reference_floor:
                return "down"
            return "idle"

        def process_stop(boarders, leavers):
            """Handle dwell time, boarding, and alighting at the current floor."""

            nonlocal current_time, total_time, total_energy

            if not boarders and not leavers:
                return

            leaving_weight = sum(
                req.load for req in leavers if req in onboard
            )  # weight exiting

            # Ensure capacity compliance before boarding new entities.
            post_leave_load = max(0.0, current_load() - leaving_weight)
            remaining_capacity = max(0.0, cfg.ELEVATOR_CAPACITY - post_leave_load)

            if boarders:
                admitted = []
                for req in boarders:
                    if req.load <= remaining_capacity + 1e-9:
                        admitted.append(req)
                        remaining_capacity -= req.load
                    # Requests beyond capacity remain in the waiting queue.
                boarders = admitted

            arrive_time = current_time
            boarding_weight = sum(r.load for r in boarders)
            dwell = hold_time(boarding_weight, leaving_weight)

            current_time += dwell
            total_time += dwell
            total_energy += standby_energy(dwell)

            for req in leavers:
                if req in onboard:
                    onboard.remove(req)
                req.destination_arrival_time = arrive_time
                req.dropoff_time = current_time

            for req in boarders:
                if req in waiting:
                    waiting.remove(req)
                req.origin_arrival_time = arrive_time
                req.pickup_time = current_time
                if req not in service_log:
                    service_log.append(req)
                if req.destination == current_floor:
                    req.dropoff_time = current_time
                    req.destination_arrival_time = arrive_time
                else:
                    onboard.append(req)

            pull_ready_requests()

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

            # If elevator is idle, travel to the next closest ready origin.
            if not onboard:
                target_req = min(
                    waiting,
                    key=lambda r: (r.arrival_time, abs(r.origin - current_floor)),
                )

                travel_between(current_floor, target_req.origin)

                # Determine who can board at this floor.
                ready_here = [
                    r
                    for r in waiting
                    if r.origin == current_floor and r.arrival_time <= current_time
                ]
                if not ready_here:
                    continue

                primary = min(
                    ready_here,
                    key=lambda r: (r.arrival_time, abs(r.destination - current_floor)),
                )
                direction = request_direction(primary, current_floor)
                boarders = [
                    r
                    for r in ready_here
                    if request_direction(r, current_floor) in {direction, "idle"}
                ]

                process_stop(boarders, [])

                if direction == "idle" or not onboard:
                    continue

            else:
                # Determine travel direction from onboard passengers.
                dirs = {
                    request_direction(req, current_floor)
                    for req in onboard
                    if request_direction(req, current_floor) != "idle"
                }
                direction = dirs.pop() if dirs else "idle"
                if direction == "idle":
                    # All passengers have reached their destinations (edge case)
                    process_stop([], onboard[:])
                    continue

            # Serve all requests in the chosen direction before considering others.
            while onboard:
                pull_ready_requests()

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

                travel_between(current_floor, next_floor)

                leavers = [req for req in onboard if req.destination == current_floor]
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

            # After serving this direction, the loop reiterates to pick the next batch.

        elev.floor = current_floor
        elev.queue = []
        elev.served_requests = service_log

    all_served = []
    for elev in elevators:
        all_served.extend(elev.served_requests)

    return total_time, total_energy, all_served
