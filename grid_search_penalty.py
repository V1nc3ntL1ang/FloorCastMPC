"""
Single-stage parallel grid search for penalty & MPC parameters.
并行单阶段网格搜索，约500组样本，输出CSV。
"""

from __future__ import annotations
import itertools, multiprocessing as mp, csv, os
from datetime import datetime

from models import config as cfg
from models import objective as objective
import main as main_module
import scheduler.mpc_scheduler as mpc_module
from models.request import generate_requests_weekday, generate_requests_weekend


# ============================================================
# 工具函数
# ============================================================


def _set_penalty_params(scale, exponent, threshold, multiplier):
    cfg.WAIT_PENALTY_SCALE = scale
    cfg.WAIT_PENALTY_EXPONENT = exponent
    cfg.WAIT_PENALTY_THRESHOLD = threshold
    cfg.EMPTYLOAD_PENALTY_MULTIPLIER = multiplier
    objective.WAIT_PENALTY_SCALE = scale
    objective.WAIT_PENALTY_EXPONENT = exponent
    objective.WAIT_PENALTY_THRESHOLD = threshold
    objective.EMPTYLOAD_PENALTY_MULTIPLIER = multiplier


def _set_mpc_params(window, max_batch):
    cfg.MPC_LOOKAHEAD_WINDOW = window
    cfg.MPC_MAX_BATCH = max_batch
    mpc_module.MPC_LOOKAHEAD_WINDOW = window
    mpc_module.MPC_MAX_BATCH = max_batch


def _simulate_week_totals():
    original_plots = cfg.SIM_ENABLE_PLOTS
    original_logs = cfg.SIM_ENABLE_LOG
    cfg.SIM_ENABLE_PLOTS = False
    cfg.SIM_ENABLE_LOG = False

    # 与 main 保持一致：若设置了 DEST_MODEL_PATH，则加载目的地预测模型
    if hasattr(main_module, "_maybe_load_destination_model"):
        try:
            main_module._maybe_load_destination_model()
        except Exception:
            pass

    weekly_totals = {"baseline": 0.0, "mpc": 0.0}

    try:
        for day_index, (day_label, day_type) in enumerate(main_module.DAY_SCHEDULE):
            # 与 main.py 对齐的随机种子偏移
            seed_shift = day_index * 114514
            if day_type == "weekday":
                requests = generate_requests_weekday(
                    cfg.WEEKDAY_TOTAL_REQUESTS, seed_shift=seed_shift
                )
            else:
                requests = generate_requests_weekend(
                    cfg.WEEKEND_TOTAL_REQUESTS, seed_shift=seed_shift
                )

            for strat_name, assign_fn in (
                ("baseline", main_module.assign_requests_greedy),
                ("mpc", main_module.assign_requests_mpc),
            ):
                result = main_module._run_strategy(
                    day_label, day_type, strat_name, assign_fn, requests
                )
                weekly_totals[strat_name] += result["objective"].total_cost

        return weekly_totals
    finally:
        cfg.SIM_ENABLE_PLOTS = original_plots
        cfg.SIM_ENABLE_LOG = original_logs


def _worker(combo):
    (scale, exponent, threshold, multiplier, window, batch) = combo
    try:
        _set_penalty_params(scale, exponent, threshold, multiplier)
        _set_mpc_params(window, batch)
        totals = _simulate_week_totals()
        base = totals.get("baseline", float("inf"))
        mpc = totals.get("mpc", float("inf"))

        return dict(
            scale=scale,
            exponent=exponent,
            threshold=threshold,
            multiplier=multiplier,
            lookahead_window=window,
            max_batch=batch,
            baseline_cost=base,
            mpc_cost=mpc,
            delta=base - mpc,
            average_cost=0.5 * (base + mpc),
        )
    except Exception as e:
        return dict(
            scale=scale,
            exponent=exponent,
            threshold=threshold,
            multiplier=multiplier,
            lookahead_window=window,
            max_batch=batch,
            baseline_cost=float("inf"),
            mpc_cost=float("inf"),
            delta=float("-inf"),
            average_cost=float("inf"),
            error=str(e),
        )


# ============================================================
# 主流程
# ============================================================


def main():
    # ---- 参数空间 ----
    scales = [30, 60, 90, 120, 150]
    exponents = [1.25, 1.5, 1.75, 2, 2.25, 2.5]
    thresholds = [5, 10, 15, 25, 35, 45]
    multipliers = [2.0]
    lookahead_windows = [240]
    max_batches = [36]

    combos = list(
        itertools.product(
            scales, exponents, thresholds, multipliers, lookahead_windows, max_batches
        )
    )

    print(f"[INFO] Total {len(combos)} parameter combinations selected.")

    # ---- 并行执行 ----
    num_workers = max(1, mp.cpu_count() - 1)
    print(f"[INFO] Using {num_workers} CPU workers.")

    results = []
    with mp.Pool(processes=num_workers) as pool:
        for idx, res in enumerate(pool.imap_unordered(_worker, combos), start=1):
            results.append(res)
            print(
                f"[{idx}/{len(combos)}] progress={idx/len(combos)*100:6.2f}%", end="\r"
            )
    print()

    # ---- 排序与保存 ----
    results.sort(key=lambda r: r["delta"], reverse=True)
    save_dir = "/home/v1nc3nt/WinDesktop/SCUT/作业/优化方法/LoadAwareElevator/results/grid_search"
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"{save_dir}/grid_search_single_{timestamp}.csv"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Grid search completed. Results saved to:\n  {csv_path}")
    print("\nTop 5 results:")
    for r in results[:5]:
        print(f"Δ={r['delta']:.2f} | {r}")


if __name__ == "__main__":
    main()
