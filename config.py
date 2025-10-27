# ============================================================
# Load-Aware Elevator Scheduling — Configuration (配置文件)
# ============================================================

from models.utils import duration_seconds, h2s

# ------------------------
# Building Parameters / 建筑物参数
# ------------------------
BUILDING_FLOORS = 15  # 总楼层数 / total number of floors
BUILDING_FLOOR_HEIGHT = 3.5  # 单层高度 (m) / floor height in meters
ELEVATOR_COUNT = 4  # 电梯数量 / number of elevators
ELEVATOR_CAPACITY = 1200.0  # 额定载荷 (kg) / rated payload

# ------------------------
# Kinematic Parameters / 运动学参数
# ------------------------
KIN_MAX_SPEED_UP_EMPTY = 3.0  # 空载上行速度上限 (m/s) / max upward speed (empty)
KIN_MAX_SPEED_UP_FULL = 2.5  # 满载上行速度上限 (m/s) / max upward speed (full)
KIN_MAX_SPEED_DOWN_EMPTY = 3.0  # 空载下行速度上限 (m/s) / max downward speed (empty)
KIN_MAX_SPEED_DOWN_FULL = 2.6  # 满载下行速度上限 (m/s) / max downward speed (full)
KIN_SPEED_DECAY_RATE = 1.2  # 速度随负载衰减系数 / decay rate vs load

KIN_ACC_UP_EMPTY = 1.2  # 空载上行加速度 (m/s²) / upward acceleration (empty)
KIN_ACC_UP_FULL = 0.9  # 满载上行加速度 (m/s²) / upward acceleration (full)
KIN_DEC_DOWN_EMPTY = 1.2  # 空载下行减速度 (m/s²) / downward deceleration (empty)
KIN_DEC_DOWN_FULL = 1.0  # 满载下行减速度 (m/s²) / downward deceleration (full)
KIN_ACC_DECAY_RATE = 1.3  # 加速度随负载衰减系数 / acceleration decay factor

# ------------------------
# Temporal Parameters / 时间参数
# ------------------------
HOLD_BASE_TIME = 5.0  # 基础开关门时间 (s) / base door dwell duration
HOLD_EFF_NORMAL = 0.002  # 正常拥挤度增量 (s/kg) / dwell time gain under normal load
HOLD_EFF_CONGESTED = 0.005  # 拥挤状态增量 (s/kg) / dwell gain beyond threshold
HOLD_CONGESTION_THRESHOLD = 400  # 拥挤阈值 (kg) / congestion weight threshold

# ------------------------
# Energy Parameters / 能耗参数
# ------------------------
ENERGY_CAR_MASS = 600.0  # 轿厢质量 (kg) / car mass
ENERGY_COUNTERWEIGHT_MASS = 500.0  # 对重质量 (kg) / counterweight mass
ENERGY_FRICTION_PER_METER = 50.0  # 摩擦能耗 (J/m) / frictional loss per meter
ENERGY_MOTOR_EFFICIENCY = 0.85  # 电机效率 / motor efficiency
ENERGY_STANDBY_POWER = 500.0  # 待机功率 (W) / standby power draw

# ------------------------
# Simulation Parameters / 仿真控制
# ------------------------
SIM_TIME_HORIZON = 300  # 仿真总时长 (s) / simulation horizon
SIM_TIME_STEP = 1.0  # 时间步长 (s) / integration step
SIM_RANDOM_SEED = 42  # 随机种子 / random seed
SIM_TOTAL_REQUESTS = 1000  # 每日请求总量 / number of generated requests
SIM_ENABLE_PLOTS = False  # 是否输出图像 / enable plot export
SIM_ENABLE_LOG = True  # 是否写入日志 / enable log export

# ------------------------
# Request Generation (Overview) / 请求生成概览
# ------------------------
OFFPEAK_MAIN_FLOW_RATIO = 0.8  # 涉及一楼的比例 / share of trips touching floor 1
OFFPEAK_LOAD_MIN = 50  # 平峰负载下界 (kg) / off-peak payload min
OFFPEAK_LOAD_MAX = 110  # 平峰负载上界 (kg) / off-peak payload max

PEAK_LOAD_MIN = 60  # 高峰负载下界 (kg) / peak payload min
PEAK_LOAD_MAX = 150  # 高峰负载上界 (kg) / peak payload max
PEAK_SIGMA_RATIO = 0.1  # 高峰标准差比 / std ratio relative to horizon
PEAK_MORNING_MU_RATIO = 0.2  # 早高峰中心 (占比) / morning peak position
PEAK_EVENING_MU_RATIO = 0.7  # 晚高峰中心 (占比) / evening peak position

# ------------------------
# Objective Weights / 目标函数权重
# ------------------------
WEIGHT_TIME = 1.0  # 时间权重 / weight on total time
WEIGHT_ENERGY = 0.001  # 能耗权重 / weight on total energy

# ============================================================
# Request Generation Parameters (Detailed) / 请求生成细节
# ============================================================

# ------------------------
# 通用控制项 / Generic Controls
# ------------------------
DEFAULT_LOAD_MIN = 50  # 默认负载下界 (kg)
DEFAULT_LOAD_MAX = 110  # 默认负载上界 (kg)
DEFAULT_SIGMA_RATIO = 0.05  # 默认高斯标准差比 / default sigma ratio
DEFAULT_INTENSITY = 1.0  # 默认强度系数 / intensity scaling

# ============================================================
# 1. 平峰参数 (Uniform Distribution) / Off-Peak Uniform Model
# ============================================================

OFFPEAK_INTENSITY = 0.4  # 平峰强度 (相对高峰) / relative intensity vs peak
OFFPEAK_LOAD_MIN = 50  # 平峰负载下界 (kg)
OFFPEAK_LOAD_MAX = 110  # 平峰负载上界 (kg)

# 三个比例之和应为 1.0 / ratios must sum to 1.0
OFFPEAK_RATIO_ORIGIN1 = 0.45  # 一楼出发 (上行) / departures from floor 1
OFFPEAK_RATIO_DEST1 = 0.45  # 抵达一楼 (下行) / arrivals to floor 1
OFFPEAK_RATIO_OTHER = 0.10  # 楼层间往返 / inter-floor traffic

# ============================================================
# 2. 高峰参数 (Gaussian Distribution) / Peak Gaussian Model
# ============================================================

PEAK_INTENSITY = 1.0  # 高峰强度系数 / peak intensity scale
PEAK_LOAD_MIN = 60  # 高峰负载下界 (kg)
PEAK_LOAD_MAX = 150  # 高峰负载上界 (kg)
PEAK_SIGMA_RATIO = 0.05  # 高峰标准差比 / time spread ratio

# 早高峰 / morning rush
PEAK_MORNING_RATIO_ORIGIN1 = 0.05  # 一楼出发比例 / upward trips from floor 1
PEAK_MORNING_RATIO_DEST1 = 0.90  # 抵达一楼比例 / down trips to floor 1
PEAK_MORNING_RATIO_OTHER = 0.05  # 楼层间流动 / inter-floor movement

# 晚高峰 / evening rush
PEAK_EVENING_RATIO_ORIGIN1 = 0.90  # 一楼出发比例 / upward trips from floor 1
PEAK_EVENING_RATIO_DEST1 = 0.05  # 抵达一楼比例 / down trips to floor 1
PEAK_EVENING_RATIO_OTHER = 0.05  # 楼层间流动 / inter-floor movement

# ============================================================
# 3. 时段定义 (小时:分钟) / Period Definitions (HH:MM)
# ============================================================

PEAK_MORNING_START = (8, 0)  # 早高峰开始 / morning start
PEAK_MORNING_END = (9, 0)  # 早高峰结束 / morning end

OFFPEAK_DAY_START = (9, 0)  # 白天平峰开始 / daytime off-peak start
OFFPEAK_DAY_END = (17, 0)  # 白天平峰结束 / daytime off-peak end

PEAK_EVENING_START = (17, 0)  # 晚高峰开始 / evening start
PEAK_EVENING_END = (21, 0)  # 晚高峰结束 / evening end

OFFPEAK_NIGHT_START = (21, 0)  # 夜间平峰开始 / night off-peak start
OFFPEAK_NIGHT_END = (7 + 24, 0)  # 夜间平峰结束 (跨日) / night off-peak end (next day)

PEAK_MORNING_MU = "8:30"  # 早高峰中心 / morning peak center
PEAK_EVENING_MU = "18:00"  # 晚高峰中心 / evening peak center

# ============================================================
# 自动计算时段权重 / Auto-computed period weights
# ============================================================

DAY_DURATION = 24 * 3600  # 一天总秒数 / seconds per day

_duration_morning = duration_seconds(PEAK_MORNING_START, PEAK_MORNING_END)
_duration_day = duration_seconds(OFFPEAK_DAY_START, OFFPEAK_DAY_END)
_duration_evening = duration_seconds(PEAK_EVENING_START, PEAK_EVENING_END)
_duration_night = duration_seconds(OFFPEAK_NIGHT_START, OFFPEAK_NIGHT_END)

_total = _duration_morning + _duration_day + _duration_evening + _duration_night

PEAK_MORNING_RATIO = _duration_morning / _total  # 早高峰权重 / morning share
OFFPEAK_DAY_RATIO = _duration_day / _total  # 白天平峰权重 / daytime share
PEAK_EVENING_RATIO = _duration_evening / _total  # 晚高峰权重 / evening share
OFFPEAK_NIGHT_RATIO = _duration_night / _total  # 夜间平峰权重 / night share
