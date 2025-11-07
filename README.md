diff --git a/README.md b/README.md
index e69de29bb2d1d6434b8b29ae775ad8c2e48c5391..b8448f6afc61dcb4018d375cf53c7db39e7ca24a 100644
--- a/README.md
+++ b/README.md
@@ -0,0 +1,191 @@
+English | [中文](#中文版)
+
+# FloorCast-MPC
+
+FloorCast-MPC is a scheduling and prediction framework for multi-elevator systems centered on the custom **FloorCast MPC** controller. Without relying on an external solver, the controller evaluates elevator assignments in a rolling horizon, balancing passenger wait times with energy usage while ingesting probabilistic destination forecasts. A greedy baseline is available for comparison, but this README focuses on FloorCast MPC itself and the optimizations that make it effective.
+
+## Feature Overview
+- **Rolling-horizon MPC**: Uses the configurable window `MPC_LOOKAHEAD_WINDOW` to examine requests near the current time and choose the lowest incremental-cost assignment.【F:scheduler/mpc_scheduler/mpc_scheduler.py†L19-L135】
+- **Joint time + energy objective**: Passenger time and energy consumption compose the incremental cost, including travel energy and idle power, preventing excessive empty trips.【F:scheduler/mpc_scheduler/mpc_scheduler.py†L137-L180】
+- **Probabilistic destination modeling**: The FloorCast destination model (multinomial logistic regression) estimates `P(dest | origin, time, weekday)`; MPC computes expected costs over the Top-K destinations to manage uncertainty.【F:scheduler/mpc_scheduler/mpc_scheduler.py†L94-L136】【F:scheduler/mpc_scheduler/destination_prediction.py†L1-L191】
+- **Lightweight online data capture**: Simulation runs can export passenger request logs for offline fine-tuning of the FloorCast model, enabling continual improvement.【F:main.py†L118-L230】【F:train_destination_predictor.py†L1-L189】
+- **Visualization and analysis utilities**: Generate trajectory plots, wait-time distributions, and detailed metric logs to assess strategy performance.【F:main.py†L232-L388】
+
+## Project Layout
+```
+FloorCast-MPC/
+├── main.py                       # Weekly simulation entry point for comparing baseline vs. FloorCast MPC
+├── train_destination_predictor.py # Training script for the FloorCast destination model
+├── models/
+│   ├── config.py                 # Global configuration and MPC/model parameters
+│   ├── destination.py, request.py# Request/destination generation and data structures
+│   ├── energy.py, kinematics.py  # Energy and kinematics models
+│   ├── objective.py              # Objective composition and metric aggregation
+│   ├── utils.py, variables.py    # Shared utilities and state containers
+├── scheduler/
+│   ├── baseline_scheduler.py     # Greedy baseline scheduler
+│   └── mpc_scheduler/
+│       ├── mpc_scheduler.py      # FloorCast MPC scheduling core
+│       ├── destination_prediction.py # FloorCast destination prediction model
+│       └── prediction_api.py     # Model loading and inference helpers
+└── README.md
+```
+
+## FloorCast MPC Design Highlights
+### 1. Layered candidate screening
+Requests are sorted by arrival time. Within each rolling window, MPC selects candidate requests; if the window is sparse, it backfills to a fixed batch size to keep computation bounded while looking slightly ahead.【F:scheduler/mpc_scheduler/mpc_scheduler.py†L49-L90】
+
+### 2. Destination probability modeling
+FloorCast uses an `SGDClassifier` (multinomial logistic regression) with time Fourier features, weekday one-hot encodings, and floor one-hots to capture cyclic traffic patterns. Top-K pruning with probability renormalization lets MPC compute expected costs under limited hypotheses.【F:scheduler/mpc_scheduler/destination_prediction.py†L17-L168】
+
+### 3. Cost function and energy constraints
+Incremental cost combines:
+- Total passenger journey time (request to destination arrival);
+- Travel energy, including dynamic and frictional components;
+- Idle energy to discourage unnecessary empty trips;
+- A tiny time bias to prefer assignments that finish earlier under ties.
+Weights are configurable in `models/config.py`, allowing operators to tune the service policy for their buildings.【F:scheduler/mpc_scheduler/mpc_scheduler.py†L137-L180】【F:models/config.py†L1-L122】
+
+### 4. Tie-breaking strategy
+When multiple elevators produce similar costs, MPC cycles through a rotating tie-break pointer to prevent one elevator from remaining idle, balancing long-term usage.【F:scheduler/mpc_scheduler/mpc_scheduler.py†L70-L134】
+
+## Installation and Environment
+- Python 3.10+
+- Core dependencies: `numpy`, `scikit-learn`, `matplotlib` (optional for plots), plus the standard library.
+- Recommended virtual environment:
+  ```bash
+  python -m venv .venv
+  source .venv/bin/activate  # On Windows use .venv\Scripts\activate
+  pip install -U pip numpy scikit-learn matplotlib
+  ```
+
+## Quick Start
+1. **Run the weekly simulation** (compare greedy baseline vs. FloorCast MPC):
+   ```bash
+   python main.py
+   ```
+   Metrics print to the console. If logging or plotting is enabled in `models/config.py`, artifacts appear under `results/`.【F:main.py†L232-L388】
+
+2. **Enable the destination prediction model**:
+   - Provide a trained model path via the `DEST_MODEL_PATH` environment variable; or
+   - Enable online learning in `models/config.py` so that `train_destination_predictor.py` fine-tunes the model after simulation.【F:main.py†L96-L229】【F:models/config.py†L96-L122】
+
+3. **Train FloorCast offline**:
+   ```bash
+   python train_destination_predictor.py --data-dir results/online_learning --epochs 3 --batch-size 4000 --learning-rate 0.01 --l2 1e-4 --save-model results/predict_model/dest_model_final.pkl
+   ```
+   The script loads JSON logs, performs mini-batch updates, and reports Top-1/Top-3 accuracy and other metrics.【F:train_destination_predictor.py†L1-L189】
+
+## Configuration
+All parameters live in `models/config.py`:
+- Building and elevator properties: floor count, capacity, kinematic constraints;
+- Request generation controls: weekday/weekend intensity, load ranges, peak/off-peak schedules;
+- Objective weights: wait penalty, energy weight, idle penalty, etc.;
+- MPC parameters: prediction window `MPC_LOOKAHEAD_WINDOW`, batch limit `MPC_MAX_BATCH`;
+- Online learning: export directories, training script path, learning rate, regularization.【F:models/config.py†L1-L213】
+
+## Results and Visualization
+Depending on configuration, simulations can emit:
+- **Trajectory plots** showing floor-time paths per elevator;
+- **Wait-time distributions** comparing strategies;
+- **Metric logs** capturing daily/weekly summaries for long-term tracking of FloorCast MPC performance.【F:main.py†L232-L388】
+
+## Contribution
+Issues and Pull Requests are welcome—share your insights on tuning FloorCast MPC for different building scenarios.
+
+---
+
+## 中文版
+[English](#floorcast-mpc)
+
+FloorCast-MPC 是一个针对多电梯系统的调度与预测框架，核心是自研的 **FloorCast MPC** 控制器。该控制器在没有外部求解器的前提下，以滚动时域（rolling horizon）的方式综合考虑乘客等待时间与能耗，结合目的楼层预测模型，实现对电梯运行策略的动态优化。本项目同样包含用于对比的贪婪基线调度，但 README 将聚焦于 FloorCast MPC 及其优化设计。
+
+## 特性总览
+- **滚动时域 MPC**：基于可配置的窗口 `MPC_LOOKAHEAD_WINDOW`，在每轮调度中评估当前时间附近的候选请求，并生成增量成本最低的分配方案。【F:scheduler/mpc_scheduler/mpc_scheduler.py†L19-L135】
+- **乘客时间 + 能耗联合目标**：增量成本由乘客总时间与能耗加权构成，能耗项考虑行程段能耗与待机功耗，从而避免仅追求最短时间导致的空载运行。【F:scheduler/mpc_scheduler/mpc_scheduler.py†L137-L180】
+- **概率化目的地预测**：通过 FloorCast 目的地模型（多项逻辑回归）预测 `P(dest | origin, time, weekday)`，MPC 在计算成本时对 Top-K 目的地进行期望化处理以减轻不确定性。【F:scheduler/mpc_scheduler/mpc_scheduler.py†L94-L136】【F:scheduler/mpc_scheduler/destination_prediction.py†L1-L191】
+- **轻量级在线数据采集**：模拟期间可导出真实乘客请求日志，用于离线微调 FloorCast 模型，支持持续改进预测能力。【F:main.py†L118-L230】【F:train_destination_predictor.py†L1-L189】
+- **可视化与分析工具**：支持导出调度轨迹、等待时间分布等图表，以及详细的指标日志，用于评估不同策略的效果。【F:main.py†L232-L388】
+
+## 项目结构
+```
+FloorCast-MPC/
+├── main.py                       # 周模拟入口，比较基线与 FloorCast MPC
+├── train_destination_predictor.py # FloorCast 目的地模型的训练脚本
+├── models/
+│   ├── config.py                 # 全局配置与 MPC/模型参数
+│   ├── destination.py, request.py# 请求/目的地生成与表示
+│   ├── energy.py, kinematics.py  # 能耗、运动学模型
+│   ├── objective.py              # 目标函数与指标汇总
+│   ├── utils.py, variables.py    # 通用工具与状态结构
+├── scheduler/
+│   ├── baseline_scheduler.py     # 贪婪基线调度器
+│   └── mpc_scheduler/
+│       ├── mpc_scheduler.py      # FloorCast MPC 调度核心
+│       ├── destination_prediction.py # FloorCast 目的地预测模型
+│       └── prediction_api.py     # 预测模型的加载与运行接口
+└── README.md
+```
+
+## FloorCast MPC 设计亮点
+### 1. 分层候选筛选
+请求按照到达时间排序，MPC 在滚动窗口内挑选候选请求，若窗口内不足则补足固定批量，实现对未来短期需求的前瞻，同时控制计算量。【F:scheduler/mpc_scheduler/mpc_scheduler.py†L49-L90】
+
+### 2. 目的地概率建模
+FloorCast 目的地模型采用 `SGDClassifier`（多项逻辑回归）并引入时间傅里叶特征、星期独热编码与楼层独热编码，使模型能够捕捉周期性流量模式。Top-K 剪枝与概率归一化保证了 MPC 在有限假设下进行期望成本计算。【F:scheduler/mpc_scheduler/destination_prediction.py†L17-L168】
+
+### 3. 成本函数与能耗约束
+增量成本由以下部分组成：
+- 乘客全程时间（从请求产生到抵达目的地）；
+- 运行能耗，包括起点与目的地段的动能与摩擦损耗；
+- 待机能耗，用于抑制过多空载调度；
+- 极小的时间偏置，用于在成本相同时优先完成更早结束的方案。
+这些指标共享配置权重，可在 `models/config.py` 中调整，以契合不同楼宇的服务策略。【F:scheduler/mpc_scheduler/mpc_scheduler.py†L137-L180】【F:models/config.py†L1-L122】
+
+### 4. 并列解决策略
+当多个电梯具有相近成本时，MPC 使用循环的 tie-break 指针在平局的候选中轮转选择，避免某台电梯长期闲置，有助于均衡设备负载。【F:scheduler/mpc_scheduler/mpc_scheduler.py†L70-L134】
+
+## 安装与环境
+- Python 3.10+
+- 主要依赖：`numpy`, `scikit-learn`, `matplotlib`（绘图可选）以及标准库。
+- 建议使用虚拟环境：
+  ```bash
+  python -m venv .venv
+  source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
+  pip install -U pip numpy scikit-learn matplotlib
+  ```
+
+## 快速开始
+1. **运行周度模拟**（比较贪婪基线与 FloorCast MPC）：
+   ```bash
+   python main.py
+   ```
+   运行结果会在终端输出各日/全周指标，若 `models/config.py` 中开启了绘图或日志功能，将在 `results/` 目录生成对应文件。【F:main.py†L232-L388】
+
+2. **启用目的地预测模型**：
+   - 将已训练的模型路径写入环境变量 `DEST_MODEL_PATH`；或
+   - 在 `models/config.py` 中打开在线学习相关配置，模拟结束后自动调用 `train_destination_predictor.py` 进行微调。【F:main.py†L96-L229】【F:models/config.py†L96-L122】
+
+3. **离线训练 FloorCast 模型**：
+   ```bash
+   python train_destination_predictor.py --data-dir results/online_learning --epochs 3 --batch-size 4000 --learning-rate 0.01 --l2 1e-4 --save-model results/predict_model/dest_model_final.pkl
+   ```
+   脚本支持从 JSON 日志加载数据、分批增量训练，并输出 Top-1/Top-3 精度等评估指标。【F:train_destination_predictor.py†L1-L189】
+
+## 配置
+所有参数集中于 `models/config.py`：
+- 建筑与电梯参数：楼层数、载重、运动学约束等；
+- 请求生成控制：工作日/周末强度、负载区间、峰谷配置；
+- 目标函数权重：等待惩罚、能耗权重、空载惩罚等；
+- MPC 参数：预测窗口 `MPC_LOOKAHEAD_WINDOW`、批处理上限 `MPC_MAX_BATCH`；
+- 在线学习参数：数据导出目录、训练脚本、学习率与正则等。【F:models/config.py†L1-L213】
+
+## 结果与可视化
+根据配置可生成：
+- **调度轨迹图**：每台电梯的楼层-时间轨迹；
+- **等待时间分布**：展示不同策略的等待统计；
+- **日志文件**：记录每日/全周指标，用于长期跟踪 FloorCast MPC 的性能演进。【F:main.py†L232-L388】
+
+## 贡献与反馈
+欢迎提交 Issue 或 Pull Request，分享在不同楼宇场景中调整 FloorCast MPC 的经验与最佳实践。
+
