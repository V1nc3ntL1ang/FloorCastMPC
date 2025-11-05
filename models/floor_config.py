"""
Floor-specific configuration for the Load-Aware Elevator simulator.

Defines structural parameters (floor count, lobby index, height), residential
zones, time buckets, and destination hotspot multipliers used when generating
non-uniform OD patterns.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Sequence

from models.utils import h2s

# ============================================================
# 1. Building structure / 基本建筑结构
# ============================================================

BUILDING_FLOORS = 15  # 总楼层数
BUILDING_FLOOR_HEIGHT = 3.5  # 楼层高度 (m)
LOBBY_FLOOR = 1  # 大堂楼层

# ============================================================
# 2. Floor zoning / 楼层功能/分区
# ============================================================

# 住宅 / 办公主力区（这里你命名成 OFFICE_FLOOR_*，但描述是 residential，我保持一致）
OFFICE_FLOOR_MIN = 5
OFFICE_FLOOR_MAX = 12

# 分区列表（显式列出，便于一眼看懂）
RESIDENTIAL_FLOORS = [5, 6, 7, 8, 9, 10, 11, 12, 13]
FAMILY_RESIDENTIAL = [5, 6, 7]
PROFESSIONAL_RESIDENTIAL = [8, 9, 10]
PREMIUM_RESIDENTIAL = [11, 12]
SKY_RESIDENCE = [13]

# 配套设施楼层
AMENITY_FLOORS: Mapping[str, int] = {
    "cafe": 2,
    "fitness": 3,
    "community": 4,
    "sky_garden": 14,
    "sky_bar": 15,
}

# 其他功能标签
PANORAMIC_FLOORS = [14, 15]
NIGHTLIFE_FLOORS = [15]
DINING_FLOORS = [2, 14, 15]
FITNESS_FLOORS = [3]
COMMUNITY_FLOORS = [4]

# ============================================================
# 3. Floor tags / 每层楼的语义标签（完全显式枚举）
# ============================================================

# 说明：
#   - 每一层一个条目，便于肉眼审查 & 调整
#   - “residential”等标签用来驱动目的地权重模型

FLOOR_TAGS: Dict[int, set[str]] = {
    # 1F: 大堂 + 公共空间
    1: {"lobby", "public"},
    # 2F: 大堂咖啡 / 餐饮
    2: {"amenity", "dining", "public"},
    # 3F: 健身房
    3: {"amenity", "fitness", "public"},
    # 4F: 社区 / cowork
    4: {"amenity", "cowork", "community"},
    # 5F–7F: 家庭向住宅
    5: {"residential", "family"},
    6: {"residential", "family"},
    7: {"residential", "family"},
    # 8F–10F: 职业人士住宅
    8: {"residential", "professional"},
    9: {"residential", "professional"},
    10: {"residential", "professional"},
    # 11F–12F: 高端住宅
    11: {"residential", "premium"},
    12: {"residential", "premium"},
    # 13F: sky residence（高端+景观）
    13: {"residential", "premium", "panorama"},
    # 14F: sky garden + 景观 + 餐饮
    14: {"amenity", "panorama", "dining"},
    # 15F: sky bar + 夜生活
    15: {"amenity", "panorama", "dining", "nightlife"},
}

# 为了兼容：如果以后扩层，可按上面格式继续往字典里加新层即可。

# ============================================================
# 4. Time windows / 时间窗口（和 config.py 对齐）
# ============================================================

# ---- 工作日时间段 ----
WEEKDAY_PEAK_MORNING_START = (7, 0)
WEEKDAY_PEAK_MORNING_END = (10, 30)

WEEKDAY_OFFPEAK_DAY_START = (10, 30)
WEEKDAY_OFFPEAK_DAY_END = (17, 0)

LUNCH_START = (11, 30)
LUNCH_END = (13, 30)

WEEKDAY_PEAK_EVENING_START = (17, 0)
WEEKDAY_PEAK_EVENING_END = (21, 0)

WEEKDAY_OFFPEAK_NIGHT_START = (21, 0)
WEEKDAY_OFFPEAK_NIGHT_END = (7 + 24, 0)  # 跨午夜

WEEKDAY_TIME_WINDOWS: Dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "morning": (WEEKDAY_PEAK_MORNING_START, WEEKDAY_PEAK_MORNING_END),
    "lunch": (LUNCH_START, LUNCH_END),
    "day": (WEEKDAY_OFFPEAK_DAY_START, WEEKDAY_OFFPEAK_DAY_END),
    "evening": (WEEKDAY_PEAK_EVENING_START, WEEKDAY_PEAK_EVENING_END),
    "night": (WEEKDAY_OFFPEAK_NIGHT_START, WEEKDAY_OFFPEAK_NIGHT_END),
}

# ---- 周末时间段 ----
WEEKEND_DAY_START = (9, 0)
WEEKEND_DAY_END = (21, 0)
WEEKEND_NIGHT_START = (21, 0)
WEEKEND_NIGHT_END = (9 + 24, 0)

WEEKEND_TIME_WINDOWS: Dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "morning": ((8, 0), (10, 0)),
    "brunch": ((10, 0), (14, 0)),
    "day": ((14, 0), (18, 0)),
    "evening": ((18, 0), (23, 0)),
    "night": ((23, 0), (8 + 24, 0)),
}

TIME_BUCKET_PRIORITY: Dict[str, Sequence[str]] = {
    "weekday": ("morning", "lunch", "day", "evening", "night"),
    "weekend": ("morning", "brunch", "day", "evening", "night"),
}


def _seconds_window(
    window: tuple[tuple[int, int], tuple[int, int]],
) -> tuple[float, float]:
    start, end = window
    return h2s(*start), h2s(*end)


TIME_WINDOWS_SECONDS: Dict[str, Dict[str, tuple[float, float]]] = {
    "weekday": {
        bucket: _seconds_window(win) for bucket, win in WEEKDAY_TIME_WINDOWS.items()
    },
    "weekend": {
        bucket: _seconds_window(win) for bucket, win in WEEKEND_TIME_WINDOWS.items()
    },
}


def _in_window(start: float, end: float, t: float) -> bool:
    """Check if time t (seconds-of-day) lies in [start, end], supporting wrap-around."""
    day_seconds = 24 * 3600.0
    if end >= day_seconds:
        # e.g. 21:00–31:00 (次日 7:00)
        if t >= start:
            return True
        return t <= (end - day_seconds)
    if end < start:
        # 一般不会用到；保留防御式写法
        return t >= start or t <= end
    return start <= t <= end


def resolve_time_bucket(day_type: str, time_s: float) -> str:
    """
    根据 day_type ('weekday' / 'weekend') 和当天秒数返回所属时间段 bucket。
    """
    windows = TIME_WINDOWS_SECONDS[day_type]
    for bucket in TIME_BUCKET_PRIORITY[day_type]:
        start, end = windows[bucket]
        if _in_window(start, end, time_s):
            return bucket
    # Fallback：默认 day
    return "day"


# ============================================================
# 5. Day-of-week special events / 特定星期几的活动
# ============================================================

DAY_OF_WEEK_SPECIAL_EVENTS: Dict[str, Sequence[Dict[str, object]]] = {
    # Monday
    "Mon": (
        {
            "floor": AMENITY_FLOORS["fitness"],
            "demand_multiplier": 1.75,
            "time_span": (h2s(6, 30), h2s(8, 30)),
            "tags": {"fitness", "amenity"},
            "label": "corporate_bootcamp",
            "notes": "Residents join a corporate bootcamp—fitness floor spikes before work.",
        },
        {
            "floor": AMENITY_FLOORS["community"],
            "demand_multiplier": 1.4,
            "time_span": (h2s(19, 0), h2s(21, 0)),
            "tags": {"community", "cowork"},
            "label": "evening_meetup",
            "notes": "Shared workspace hosts a newcomers meetup each Monday evening.",
        },
    ),
    # Wednesday
    "Wed": (
        {
            "floor": AMENITY_FLOORS["community"],
            "demand_multiplier": 1.6,
            "time_span": (h2s(12, 0), h2s(14, 0)),
            "tags": {"community", "dining"},
            "label": "midweek_food_fair",
            "notes": "Pop-up vendors draw lunch traffic to the community hub midweek.",
        },
        {
            "floor": PREMIUM_RESIDENTIAL[0],
            "demand_multiplier": 1.3,
            "time_span": (h2s(20, 0), h2s(22, 0)),
            "tags": {"residential", "premium"},
            "label": "wine_tasting",
            "notes": "Premium residences host a private tasting night, increasing evening returns.",
        },
    ),
    # Friday
    "Fri": (
        {
            "floor": AMENITY_FLOORS["sky_bar"],
            "demand_multiplier": 2.1,
            "time_span": (h2s(18, 0), h2s(24, 0)),
            "tags": {"nightlife", "dining"},
            "label": "live_jazz",
            "notes": "Sky bar schedules live jazz every Friday, drawing post-work crowds.",
        },
        {
            "floor": AMENITY_FLOORS["cafe"],
            "demand_multiplier": 1.5,
            "time_span": (h2s(15, 0), h2s(17, 0)),
            "tags": {"amenity", "dining"},
            "label": "dessert_pop_up",
            "notes": "Lobby café partners with pastry chefs—afternoon tea traffic increases.",
        },
    ),
    # Saturday
    "Sat": (
        {
            "floor": AMENITY_FLOORS["sky_garden"],
            "demand_multiplier": 1.9,
            "time_span": (h2s(10, 0), h2s(14, 0)),
            "tags": {"panorama", "dining"},
            "label": "brunch_yoga",
            "notes": "Weekend skyline brunch & yoga at the sky garden.",
        },
        {
            "floor": FAMILY_RESIDENTIAL[0],
            "demand_multiplier": 1.4,
            "time_span": (h2s(14, 0), h2s(17, 0)),
            "tags": {"residential", "family"},
            "label": "kids_club",
            "notes": "Family levels organise kids club, raising intra-residential trips.",
        },
    ),
    # Sunday
    "Sun": (
        {
            "floor": FAMILY_RESIDENTIAL[1],
            "demand_multiplier": 1.35,
            "time_span": (h2s(9, 0), h2s(12, 0)),
            "tags": {"residential", "family"},
            "label": "family_brunch",
            "notes": "Extended families visit for Sunday brunch, boosting downward traffic.",
        },
        {
            "floor": AMENITY_FLOORS["community"],
            "demand_multiplier": 1.6,
            "time_span": (h2s(16, 0), h2s(19, 0)),
            "tags": {"community", "amenity"},
            "label": "makers_market",
            "notes": "Local artisans sell crafts; lobby-to-community flow intensifies late afternoon.",
        },
    ),
}


def events_for_day(day_label: str) -> Sequence[Dict[str, object]]:
    """Return configured special events for a given day label (e.g., 'Mon')."""
    return DAY_OF_WEEK_SPECIAL_EVENTS.get(day_label, ())


# ============================================================
# 6. Base offsets & multipliers / 基础偏置与热点系数
# ============================================================

# ---- 基础类别偏置：从大堂出发 ----
BASE_OFFSETS_FROM_LOBBY: Mapping[str, float] = {
    "base": 0.8,
    "residential": 1.8,
    "family": 0.4,
    "professional": 0.5,
    "premium": 0.8,
    "amenity": 0.7,
    "fitness": 0.5,
    "cowork": 0.6,
    "community": 0.4,
    "dining": 0.6,
    "panorama": 0.5,
    "nightlife": 0.5,
}

# ---- 基础类别偏置：从上层出发 ----
BASE_OFFSETS_FROM_UPPER: Mapping[str, float] = {
    "base": 0.7,
    "lobby": 2.4,
    "amenity": 0.9,
    "fitness": 0.8,
    "cowork": 0.7,
    "community": 0.6,
    "dining": 0.9,
    "panorama": 0.9,
    "nightlife": 1.0,
    "residential": 0.4,
    "premium": 0.5,
}

# ---- 时间相关热点 multiplier ----
HOTSPOT_MULTIPLIERS: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {
    "weekday": {
        "from_lobby": {
            "morning": {"residential": 3.6, "premium": 4.0, "professional": 3.1},
            "lunch": {"amenity": 3.4, "dining": 3.6, "fitness": 2.8, "cowork": 2.2},
            "day": {"amenity": 1.6, "cowork": 2.0, "residential": 1.5},
            "evening": {"residential": 3.8, "premium": 4.2, "panorama": 1.9},
            "night": {"nightlife": 3.2, "panorama": 2.6},
        },
        "from_upper": {
            "morning": {"lobby": 3.4, "amenity": 1.2},
            "lunch": {"amenity": 3.0, "dining": 2.8, "lobby": 1.4},
            "day": {"amenity": 1.6, "cowork": 1.9, "lobby": 1.3},
            "evening": {"lobby": 4.2, "dining": 1.6},
            "night": {"nightlife": 3.3, "panorama": 2.5, "lobby": 1.3},
        },
    },
    "weekend": {
        "from_lobby": {
            "morning": {"amenity": 2.6, "fitness": 3.4, "residential": 1.3},
            "brunch": {"dining": 3.8, "amenity": 3.2, "panorama": 2.4},
            "day": {"amenity": 3.0, "community": 2.3, "panorama": 2.6},
            "evening": {"dining": 3.5, "panorama": 3.2, "nightlife": 3.5},
            "night": {"nightlife": 4.0, "panorama": 3.3},
        },
        "from_upper": {
            "morning": {"amenity": 2.9, "fitness": 3.6, "lobby": 1.3},
            "brunch": {"dining": 3.5, "amenity": 3.0, "lobby": 1.4},
            "day": {"amenity": 3.2, "community": 2.6, "panorama": 2.4, "lobby": 1.3},
            "evening": {"panorama": 3.4, "nightlife": 3.6, "dining": 3.0, "lobby": 2.1},
            "night": {"nightlife": 4.1, "panorama": 3.5, "lobby": 1.6},
        },
    },
}

# ---- 特定楼层，额外加成 ----
FLOOR_SPECIFIC_BONUS: Dict[str, Dict[str, Dict[int, float]]] = {
    "weekday": {
        "lunch": {2: 1.4, 3: 1.3, 4: 1.2},
        "evening": {14: 1.4, 15: 1.6},
        "night": {14: 1.5, 15: 1.9},
    },
    "weekend": {
        "morning": {3: 1.6},
        "brunch": {2: 1.6, 4: 1.3},
        "day": {14: 1.6, 4: 1.2},
        "evening": {14: 1.8, 15: 2.2},
        "night": {15: 2.5},
    },
}

# ============================================================
# 7. Utility helpers
# ============================================================


def floor_tags(floor: int) -> set[str]:
    """Return the configured tags for a given floor."""
    return FLOOR_TAGS.get(floor, {"residential"})


def floors_with_tag(tag: str) -> Iterable[int]:
    """Yield floors that include the given category tag."""
    return (floor for floor, tags in FLOOR_TAGS.items() if tag in tags)


__all__ = [
    "BUILDING_FLOORS",
    "BUILDING_FLOOR_HEIGHT",
    "LOBBY_FLOOR",
    "OFFICE_FLOOR_MIN",
    "OFFICE_FLOOR_MAX",
    "RESIDENTIAL_FLOORS",
    "FAMILY_RESIDENTIAL",
    "PROFESSIONAL_RESIDENTIAL",
    "PREMIUM_RESIDENTIAL",
    "SKY_RESIDENCE",
    "AMENITY_FLOORS",
    "PANORAMIC_FLOORS",
    "NIGHTLIFE_FLOORS",
    "DINING_FLOORS",
    "FITNESS_FLOORS",
    "COMMUNITY_FLOORS",
    "FLOOR_TAGS",
    "floor_tags",
    "floors_with_tag",
    "WEEKDAY_PEAK_MORNING_START",
    "WEEKDAY_PEAK_MORNING_END",
    "WEEKDAY_OFFPEAK_DAY_START",
    "WEEKDAY_OFFPEAK_DAY_END",
    "LUNCH_START",
    "LUNCH_END",
    "WEEKDAY_PEAK_EVENING_START",
    "WEEKDAY_PEAK_EVENING_END",
    "WEEKDAY_OFFPEAK_NIGHT_START",
    "WEEKDAY_OFFPEAK_NIGHT_END",
    "WEEKEND_DAY_START",
    "WEEKEND_DAY_END",
    "WEEKEND_NIGHT_START",
    "WEEKEND_NIGHT_END",
    "WEEKDAY_TIME_WINDOWS",
    "WEEKEND_TIME_WINDOWS",
    "TIME_BUCKET_PRIORITY",
    "TIME_WINDOWS_SECONDS",
    "DAY_OF_WEEK_SPECIAL_EVENTS",
    "events_for_day",
    "resolve_time_bucket",
    "BASE_OFFSETS_FROM_LOBBY",
    "BASE_OFFSETS_FROM_UPPER",
    "HOTSPOT_MULTIPLIERS",
    "FLOOR_SPECIFIC_BONUS",
]
