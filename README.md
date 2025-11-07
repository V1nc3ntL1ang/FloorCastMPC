English | [中文](#中文版)

# FloorCast-MPC

FloorCast-MPC is a scheduling and prediction framework for multi-elevator systems centered on the custom **FloorCast MPC** controller. Without relying on an external solver, the controller evaluates elevator assignments in a rolling horizon, balancing passenger wait times with energy usage while ingesting probabilistic destination forecasts. A greedy baseline is available for comparison, but this README focuses on FloorCast MPC itself and the optimizations that make it effective.

## Feature Overview

-   **Rolling-horizon MPC**: Uses the configurable window `MPC_LOOKAHEAD_WINDOW` to examine requests near the current time and choose the lowest incremental-cost assignment ([scheduler/mpc_scheduler/mpc_scheduler.py#L21-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L21-L149)).
-   **Joint time + energy objective**: Passenger time and energy consumption compose the incremental cost, including travel energy and idle power, preventing excessive empty trips ([scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237)).
-   **Probabilistic destination modeling**: The FloorCast destination model (multinomial logistic regression) estimates `P(dest | origin, time, weekday)`; MPC computes expected costs over the Top-K destinations to manage uncertainty ([scheduler/mpc_scheduler/mpc_scheduler.py#L151-L199](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L151-L199), [scheduler/mpc_scheduler/destination_prediction.py#L1-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/destination_prediction.py#L1-L200)).
-   **Lightweight online data capture**: Simulation runs can export passenger request logs for offline fine-tuning of the FloorCast model, enabling continual improvement ([main.py#L289-L337](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L289-L337), [train_destination_predictor.py#L136-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/train_destination_predictor.py#L136-L200)).
-   **Visualization and analysis utilities**: Generate trajectory plots, wait-time distributions, and detailed metric logs to assess strategy performance ([main.py#L339-L499](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L339-L499)).

## Project Layout

```
FloorCast-MPC/
├── main.py                         # Weekly simulation entry point for comparing baseline vs. FloorCast MPC
├── train_destination_predictor.py   # Training script for the FloorCast destination model
├── models/
│   ├── config.py                    # Global configuration, simulation toggles, learning settings
│   ├── floor_config.py              # Building layout constants shared across modules
│   ├── destination.py               # Destination sampling helpers for simulation
│   ├── request.py                   # Passenger request generators (weekday/weekend)
│   ├── energy.py, kinematics.py     # Energy and motion models used during cost estimation
│   ├── temporal.py                  # Door dwell / timing utilities
│   ├── objective.py                 # Objective composition and passenger metric aggregation
│   ├── utils.py, variables.py       # Shared helpers and elevator state containers
├── scheduler/
│   ├── baseline_scheduler.py        # Greedy baseline scheduler
│   └── mpc_scheduler/
│       ├── mpc_scheduler.py         # FloorCast MPC scheduling core
│       ├── destination_prediction.py# FloorCast destination prediction model
│       └── prediction_api.py        # Model loading and inference helpers
├── results/                         # Created at runtime for logs, plots, and learned models
└── README.md
```

## FloorCast MPC Design Highlights

### 1. Layered candidate screening

Requests are sorted by arrival time. Within each rolling window, MPC selects candidate requests; if the window is sparse, it backfills to a fixed batch size to keep computation bounded while looking slightly ahead ([scheduler/mpc_scheduler/mpc_scheduler.py#L67-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L67-L149)).

### 2. Destination probability modeling

FloorCast uses an `SGDClassifier` (multinomial logistic regression) with time Fourier features, weekday one-hot encodings, and floor one-hots to capture cyclic traffic patterns. Top-K pruning with probability renormalization lets MPC compute expected costs under limited hypotheses ([scheduler/mpc_scheduler/destination_prediction.py#L71-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/destination_prediction.py#L71-L200)).

### 3. Cost function and energy constraints

Incremental cost combines:

-   Total passenger journey time (request to destination arrival);
-   Travel energy, including dynamic and frictional components;
-   Idle energy to discourage unnecessary empty trips;
-   A tiny time bias to prefer assignments that finish earlier under ties.
    Weights are configurable in `models/config.py`, allowing operators to tune the service policy for their buildings ([scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237), [models/config.py#L101-L115](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L101-L115)).

### 4. Tie-breaking strategy

When multiple elevators produce similar costs, MPC cycles through a rotating tie-break pointer to prevent one elevator from remaining idle, balancing long-term usage ([scheduler/mpc_scheduler/mpc_scheduler.py#L120-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L120-L149)).

## Installation and Environment

-   Python 3.10+
-   Core dependencies: `numpy`, `scikit-learn`, `matplotlib` (optional for plots), plus the standard library.

## Quick Start

1. **Run the weekly simulation** (compare greedy baseline vs. FloorCast MPC):

    ```bash
    python main.py
    ```

    Each simulated day prints detailed wait/energy summaries followed by weekly totals in the console ([main.py#L410-L499](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L410-L499)).

2. **Configure logging and plots**:

    - Toggle `SIM_ENABLE_LOG` to export JSON summaries and `SIM_ENABLE_PLOTS*` to draw trajectory/wait plots ([models/config.py#L73-L85](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L73-L85)).
    - When enabled, plots and logs are written to `results/` by the driver ([main.py#L339-L387](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L339-L387)).

3. **Load or learn the destination predictor**:

    - Point `DEST_MODEL_PATH` to a saved model to use it at runtime ([main.py#L286-L305](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L286-L305)).
    - Flip `ONLINE_LEARNING_ENABLE` to `True` so the simulator records daily request logs and optionally launches offline fine-tuning after the weekly run ([models/config.py#L118-L131](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L118-L131), [main.py#L289-L501](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L289-L501)).

4. **Train FloorCast offline**:
    ```bash
    python train_destination_predictor.py --data-dir results/online_learning --epochs 3 --batch-size 4000 --learning-rate 0.01 --l2 1e-4 --save-model results/predict_model/dest_model_final.pkl
    ```
    The script loads JSON logs, performs mini-batch updates, and reports Top-1/Top-3 accuracy and other metrics ([train_destination_predictor.py#L81-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/train_destination_predictor.py#L81-L200)).

## Configuration

All parameters live in `models/config.py`:

-   Building and elevator properties: floor count, capacity, kinematic constraints;
-   Request generation controls: weekday/weekend intensity, load ranges, peak/off-peak schedules;
-   Objective weights: wait penalty, energy weight, idle penalty, etc.;
-   MPC parameters: prediction window `MPC_LOOKAHEAD_WINDOW`, batch limit `MPC_MAX_BATCH`;
-   Online learning: export directories, training script path, learning rate, regularization ([models/config.py#L1-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L1-L149)).

## Results and Visualization

Depending on configuration, simulations can emit:

-   **Trajectory plots** showing floor-time paths per elevator;
-   **Wait-time distributions** comparing strategies;
-   **Metric logs** capturing daily/weekly summaries for long-term tracking of FloorCast MPC performance ([main.py#L339-L387](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L339-L387)).

---

## 中文版

[English](#floorcast-mpc) | 中文

FloorCast-MPC 是一个针对多电梯系统的调度与预测框架，核心是自研的 **FloorCast MPC** 控制器。该控制器在没有外部求解器的前提下，以滚动时域（rolling horizon）的方式综合考虑乘客等待时间与能耗，结合目的楼层预测模型，实现对电梯运行策略的动态优化。本项目同样包含用于对比的贪婪基线调度，但 README 将聚焦于 FloorCast MPC 及其优化设计。

## 特性总览

-   **滚动时域 MPC**：基于可配置的窗口 `MPC_LOOKAHEAD_WINDOW`，在每轮调度中评估当前时间附近的候选请求，并生成增量成本最低的分配方案（[scheduler/mpc_scheduler/mpc_scheduler.py#L21-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L21-L149)）。
-   **乘客时间 + 能耗联合目标**：增量成本由乘客总时间与能耗加权构成，能耗项考虑行程段能耗与待机功耗，从而避免仅追求最短时间导致的空载运行（[scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237)）。
-   **概率化目的地预测**：通过 FloorCast 目的地模型（多项逻辑回归）预测 `P(dest | origin, time, weekday)`，MPC 在计算成本时对 Top-K 目的地进行期望化处理以减轻不确定性（[scheduler/mpc_scheduler/mpc_scheduler.py#L151-L199](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L151-L199)，[scheduler/mpc_scheduler/destination_prediction.py#L1-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/destination_prediction.py#L1-L200)）。
-   **轻量级在线数据采集**：模拟期间可导出真实乘客请求日志，用于离线微调 FloorCast 模型，支持持续改进预测能力（[main.py#L289-L337](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L289-L337)，[train_destination_predictor.py#L136-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/train_destination_predictor.py#L136-L200)）。
-   **可视化与分析工具**：支持导出调度轨迹、等待时间分布等图表，以及详细的指标日志，用于评估不同策略的效果（[main.py#L339-L499](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L339-L499)）。

## 项目结构

```
FloorCast-MPC/
├── main.py                         # 周模拟入口，比较贪婪基线与 FloorCast MPC
├── train_destination_predictor.py   # FloorCast 目的地模型的训练脚本
├── models/
│   ├── config.py                    # 全局配置、仿真开关与学习参数
│   ├── floor_config.py              # 楼宇结构常量
│   ├── destination.py               # 目的地采样工具
│   ├── request.py                   # 乘客请求生成（工作日/周末）
│   ├── energy.py, kinematics.py     # 能耗与运动学模型
│   ├── temporal.py                  # 开关门/时间相关工具
│   ├── objective.py                 # 目标函数与乘客指标汇总
│   ├── utils.py, variables.py       # 通用工具与电梯状态结构
├── scheduler/
│   ├── baseline_scheduler.py        # 贪婪基线调度器
│   └── mpc_scheduler/
│       ├── mpc_scheduler.py         # FloorCast MPC 调度核心
│       ├── destination_prediction.py# FloorCast 目的地预测模型
│       └── prediction_api.py        # 模型加载与推理接口
├── results/                         # 运行时生成的日志、图像与模型目录
└── README.md
```

## FloorCast MPC 设计亮点

### 1. 分层候选筛选

请求按照到达时间排序，MPC 在滚动窗口内挑选候选请求，若窗口内不足则补足固定批量，实现对未来短期需求的前瞻，同时控制计算量（[scheduler/mpc_scheduler/mpc_scheduler.py#L67-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L67-L149)）。

### 2. 目的地概率建模

FloorCast 目的地模型采用 `SGDClassifier`（多项逻辑回归）并引入时间傅里叶特征、星期独热编码与楼层独热编码，使模型能够捕捉周期性流量模式。Top-K 剪枝与概率归一化保证了 MPC 在有限假设下进行期望成本计算（[scheduler/mpc_scheduler/destination_prediction.py#L71-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/destination_prediction.py#L71-L200)）。

### 3. 成本函数与能耗约束

增量成本由以下部分组成：

-   乘客全程时间（从请求产生到抵达目的地）；
-   运行能耗，包括起点与目的地段的动能与摩擦损耗；
-   待机能耗，用于抑制过多空载调度；
-   极小的时间偏置，用于在成本相同时优先完成更早结束的方案。
    这些指标共享配置权重，可在 `models/config.py` 中调整，以契合不同楼宇的服务策略（[scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L220-L237)，[models/config.py#L101-L115](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L101-L115)）。

### 4. 并列解决策略

当多个电梯具有相近成本时，MPC 使用循环的 tie-break 指针在平局的候选中轮转选择，避免某台电梯长期闲置，有助于均衡设备负载（[scheduler/mpc_scheduler/mpc_scheduler.py#L120-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/scheduler/mpc_scheduler/mpc_scheduler.py#L120-L149)）。

## 安装与环境

-   Python 3.10+
-   主要依赖：`numpy`, `scikit-learn`, `matplotlib`（绘图可选）以及标准库。

## 快速开始

1. **运行周度模拟**（比较贪婪基线与 FloorCast MPC）：

    ```bash
    python main.py
    ```

    终端将打印每日的等待/能耗总结以及全周汇总结果（[main.py#L410-L499](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L410-L499)）。

2. **配置日志与绘图开关**：

    - 调整 `SIM_ENABLE_LOG` 导出 JSON，总开关 `SIM_ENABLE_PLOTS` 与 `SIM_ENABLE_PLOTS_*` 控制不同图像输出（[models/config.py#L73-L85](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L73-L85)）。
    - 开启后，主程序会在 `results/` 目录写入图表与日志（[main.py#L339-L387](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L339-L387)）。

3. **加载或启用目的地预测模型**：

    - 通过环境变量 `DEST_MODEL_PATH` 指向已保存的模型以供推断（[main.py#L286-L305](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L286-L305)）。
    - 将 `ONLINE_LEARNING_ENABLE` 设为 `True` 后，模拟会收集每日请求日志并在周仿真结束后可自动触发离线微调（[models/config.py#L118-L131](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L118-L131)，[main.py#L289-L501](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L289-L501)）。

4. **离线训练 FloorCast 模型**：
    ```bash
    python train_destination_predictor.py --data-dir results/online_learning --epochs 3 --batch-size 4000 --learning-rate 0.01 --l2 1e-4 --save-model results/predict_model/dest_model_final.pkl
    ```
    脚本支持从 JSON 日志加载数据、分批增量训练，并输出 Top-1/Top-3 精度等评估指标（[train_destination_predictor.py#L81-L200](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/train_destination_predictor.py#L81-L200)）。

## 配置

所有参数集中于 `models/config.py`：

-   建筑与电梯参数：楼层数、载重、运动学约束等；
-   请求生成控制：工作日/周末强度、负载区间、峰谷配置；
-   目标函数权重：等待惩罚、能耗权重、空载惩罚等；
-   MPC 参数：预测窗口 `MPC_LOOKAHEAD_WINDOW`、批处理上限 `MPC_MAX_BATCH`；
-   在线学习参数：数据导出目录、训练脚本、学习率与正则等（[models/config.py#L1-L149](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/models/config.py#L1-L149)）。

## 结果与可视化

根据配置可生成：

-   **调度轨迹图**：每台电梯的楼层-时间轨迹；
-   **等待时间分布**：展示不同策略的等待统计；
-   **日志文件**：记录每日/全周指标，用于长期跟踪 FloorCast MPC 的性能演进（[main.py#L339-L387](https://github.com/V1nc3ntL1ang/FloorCast-MPC/blob/main/main.py#L339-L387)）。

