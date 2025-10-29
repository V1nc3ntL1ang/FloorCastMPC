"""
MILP-based scheduler that assigns requests to elevators and writes to each
elevator's `queue`. If gurobipy is unavailable, returns False so caller can
fallback to baseline scheduling.
"""

try:
    import gurobipy as gp
    from gurobipy import GRB
except Exception:
    gp = None
    GRB = None

import config as cfg
from typing import List


def assign_requests_milp(requests: List[object], elevators: List[object]) -> bool:
    """
    使用 MILP 为电梯分配请求，并将结果写入 elevators[i].queue。
    仅处理在仿真时间窗内的请求（arrival_time <= SIM_TIME_HORIZON）。
    返回是否成功求解。
    """
    if gp is None or GRB is None:
        print("[MILP] gurobipy not available; skipping MILP.")
        for e in elevators:
            e.queue = []
        return False

    if not requests:
        for e in elevators:
            e.queue = []
        return True

    # ===== 1. 参数提取（来自 config）=====
    floors = list(range(1, cfg.BUILDING_FLOORS + 1))  # 楼层 1~15
    elevator_ids = list(range(1, cfg.ELEVATOR_COUNT + 1))  # 电梯 1~4
    time_step_s = 5  # 时间步长（秒）
    horizon_steps = int(cfg.SIM_TIME_HORIZON / time_step_s)
    max_sim_time = horizon_steps * time_step_s

    # 只保留仿真时间窗内的请求
    in_horizon_requests = [r for r in requests if r.arrival_time <= max_sim_time]
    if not in_horizon_requests:
        for e in elevators:
            e.queue = []
        return True

    requests_meta = [
        {
            "id": i,
            "o": r.origin,
            "d": r.destination,
            "L": r.load,
            "arrival": r.arrival_time,
        }
        for i, r in enumerate(in_horizon_requests)
    ]
    request_ids = [c["id"] for c in requests_meta]
    steps = list(range(0, horizon_steps + 1))

    print(
        f"Debug: floors={len(floors)}, elevators={len(elevator_ids)}, steps={len(steps)}, Requests={len(in_horizon_requests)}"
    )

    capacity_limit_kg = cfg.ELEVATOR_CAPACITY
    weight_time = cfg.WEIGHT_TIME
    weight_energy = cfg.WEIGHT_ENERGY
    dwell_base_s = cfg.HOLD_BASE_TIME
    dwell_eff_normal_s_per_kg = cfg.HOLD_EFF_NORMAL
    dwell_eff_congested_s_per_kg = cfg.HOLD_EFF_CONGESTED
    congestion_threshold_kg = cfg.HOLD_CONGESTION_THRESHOLD
    standby_power_w = cfg.ENERGY_STANDBY_POWER

    # 能耗：上下行不同（简化）
    move_energy_cost = {}
    for f1 in floors:
        for f2 in floors:
            if f1 == f2:
                move_energy_cost[(f1, f2)] = 0
            elif f2 > f1:
                move_energy_cost[(f1, f2)] = 250  # 上行
            else:
                move_energy_cost[(f1, f2)] = 150  # 下行

    elevator_init_floors = [e.floor for e in elevators]

    # ===== 2. 创建模型 =====
    model = gp.Model("EGCS_MILP")
    model.Params.OutputFlag = 0
    model.Params.TimeLimit = 30
    model.Params.MIPGap = 0.05

    # ===== 3. 决策变量 =====
    assign = model.addVars(elevator_ids, request_ids, vtype=GRB.BINARY, name="x")
    at_floor = model.addVars(elevator_ids, floors, steps, vtype=GRB.BINARY, name="z")
    move = model.addVars(
        elevator_ids, floors, floors, steps, vtype=GRB.BINARY, name="y"
    )
    board_start = model.addVars(request_ids, steps, vtype=GRB.BINARY, name="b")
    board_finish = model.addVars(request_ids, steps, vtype=GRB.BINARY, name="p")
    car_load_kg = model.addVars(elevator_ids, steps, lb=0, name="u")

    # ===== 4. 约束 =====
    # (A) 分配唯一性
    for cid in request_ids:
        model.addConstr(gp.quicksum(assign[k, cid] for k in elevator_ids) == 1)

    # (B) 初始位置
    for k in elevator_ids:
        init_f = elevator_init_floors[k - 1]
        for f in floors:
            model.addConstr(at_floor[k, f, 0] == (1 if f == init_f else 0))

    # (C) 位置流 & 单层移动
    for k in elevator_ids:
        for t in steps[:-1]:
            for f in floors:
                incoming = gp.quicksum(
                    move[k, f_prev, f, t]
                    for f_prev in [f - 1, f, f + 1]
                    if f_prev in floors
                )
                model.addConstr(at_floor[k, f, t + 1] == incoming)
        for f1 in floors:
            for f2 in floors:
                if abs(f1 - f2) > 1:
                    for t in steps[:-1]:
                        model.addConstr(move[k, f1, f2, t] == 0)

    # (D) 起点一致性 & 到达时间窗口
    for c in requests_meta:
        cid, o = c["id"], c["o"]
        t_min = max(0, int(c["arrival"] // time_step_s))
        for t in range(t_min):
            model.addConstr(board_start[cid, t] == 0)
            model.addConstr(board_finish[cid, t] == 0)
        model.addConstr(gp.quicksum(board_start[cid, t] for t in steps) == 1)
        model.addConstr(gp.quicksum(board_finish[cid, t] for t in steps) == 1)
        for t in steps:
            model.addConstr(
                board_start[cid, t]
                <= gp.quicksum(at_floor[k, o, t] * assign[k, cid] for k in elevator_ids)
            )
            model.addConstr(
                board_finish[cid, t]
                <= gp.quicksum(at_floor[k, o, t] * assign[k, cid] for k in elevator_ids)
            )

    # (E) PWL 停靠时间
    for c in requests_meta:
        cid = c["id"]
        o = c["o"]
        W_oc = gp.quicksum(
            c2["L"] * board_start[c2["id"], t]
            for c2 in requests_meta
            if c2["o"] == o
            for t in steps
        )
        alpha_weight = model.addVar(
            lb=0, ub=congestion_threshold_kg, name=f"alpha_{cid}"
        )
        beta_weight = model.addVar(lb=0, name=f"beta_{cid}")
        model.addConstr(alpha_weight + beta_weight == W_oc)
        t_b = gp.quicksum(t * board_start[cid, t] for t in steps)
        t_p = gp.quicksum(t * board_finish[cid, t] for t in steps)
        model.addConstr(
            t_p
            >= t_b
            + (
                dwell_base_s
                + dwell_eff_normal_s_per_kg * alpha_weight
                + dwell_eff_congested_s_per_kg * beta_weight
            )
            / time_step_s
        )

    # (F) 容量约束
    for k in elevator_ids:
        for t in steps:
            boarded = gp.quicksum(
                c["L"]
                * gp.quicksum(board_start[c["id"], t_prime] for t_prime in range(t + 1))
                * assign[k, c["id"]]
                for c in requests_meta
            )
            model.addConstr(car_load_kg[k, t] == boarded)
            model.addConstr(car_load_kg[k, t] <= capacity_limit_kg)

    # (G) FCFS（同楼层）
    for c1 in requests_meta:
        for c2 in requests_meta:
            if c1["o"] == c2["o"] and c1["arrival"] < c2["arrival"]:
                t_p1 = gp.quicksum(t * board_finish[c1["id"], t] for t in steps)
                t_p2 = gp.quicksum(t * board_finish[c2["id"], t] for t in steps)
                model.addConstr(t_p1 <= t_p2)

    # ===== 5. 目标函数 =====
    waiting_time = gp.quicksum(
        (
            gp.quicksum(t * board_finish[c["id"], t] for t in steps)
            - c["arrival"] / time_step_s
        )
        * time_step_s
        for c in requests_meta
    )
    travel_time = gp.quicksum(time_step_s * abs(c["o"] - c["d"]) for c in requests_meta)
    base_energy = standby_power_w * (len(steps) * time_step_s)
    move_energy = gp.quicksum(
        move_energy_cost.get((f1, f2), 0) * move[k, f1, f2, t]
        for k in elevator_ids
        for f1 in floors
        for f2 in floors
        for t in steps[:-1]
    )

    model.setObjective(
        weight_time * (waiting_time + travel_time)
        + weight_energy * (base_energy + move_energy),
        GRB.MINIMIZE,
    )

    # ===== 6. 求解 =====
    model.optimize()

    if model.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
        print("MILP failed to solve.")
        for e in elevators:
            e.queue = []
        return False

    # ===== 7. 写入结果 =====
    for e in elevators:
        e.queue = []

    assignment = {}
    for c in requests_meta:
        cid = c["id"]
        for k in elevator_ids:
            if assign[k, cid].X > 0.5:
                assignment[cid] = k
                break

    for i, req in enumerate(in_horizon_requests):
        elev_id = assignment[i]
        elevators[elev_id - 1].queue.append(req)

    return True
