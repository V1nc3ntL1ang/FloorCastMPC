"""
Floor-specific configuration for the Load-Aware Elevator simulator.

Defines structural parameters (floor count, lobby index, height), residential
zones, time buckets, and destination hotspot multipliers used when generating
non-uniform OD patterns.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Sequence

from models.utils import h2s

# ------------------------
# Building structure
# ------------------------

BUILDING_FLOORS = 15  # 总楼层数 / total floors in the building
BUILDING_FLOOR_HEIGHT = 3.5  # 单层高度 (m) / per-floor height in meters
LOBBY_FLOOR = 1  # 大堂所在楼层 / lobby floor index

# ------------------------
# Residential / amenity zoning
# ------------------------

OFFICE_FLOOR_MIN = 5  # 住宅主力区下界 / start of dense residential zone
OFFICE_FLOOR_MAX = 12  # 住宅主力区上界 / end of dense residential zone

RESIDENTIAL_FLOORS = list(range(5, 13))
FAMILY_RESIDENTIAL = [5, 6, 7]
PROFESSIONAL_RESIDENTIAL = [8, 9, 10]
PREMIUM_RESIDENTIAL = [11, 12]
SKY_RESIDENCE = [13]

AMENITY_FLOORS: Mapping[str, int] = {
    "cafe": 2,
    "fitness": 3,
    "community": 4,
    "sky_garden": 14,
    "sky_bar": 15,
}

PANORAMIC_FLOORS = [14, 15]
NIGHTLIFE_FLOORS = [15]
DINING_FLOORS = [2, 14, 15]
FITNESS_FLOORS = [3]
COMMUNITY_FLOORS = [4]

# ------------------------
# Floor tags for category-based weighting
# ------------------------

FLOOR_TAGS: Dict[int, set[str]] = {
    1: {"lobby", "public"},
    2: {"amenity", "dining", "public"},
    3: {"amenity", "fitness", "public"},
    4: {"amenity", "cowork", "community"},
    14: {"amenity", "panorama", "dining"},
    15: {"amenity", "panorama", "dining", "nightlife"},
}

for floor in FAMILY_RESIDENTIAL:
    FLOOR_TAGS[floor] = {"residential", "family"}
for floor in PROFESSIONAL_RESIDENTIAL:
    FLOOR_TAGS[floor] = {"residential", "professional"}
for floor in PREMIUM_RESIDENTIAL:
    FLOOR_TAGS[floor] = {"residential", "premium"}
for floor in SKY_RESIDENCE:
    FLOOR_TAGS[floor] = {"residential", "premium", "panorama"}
for level in range(LOBBY_FLOOR, BUILDING_FLOORS + 1):
    FLOOR_TAGS.setdefault(level, {"residential"})

# ------------------------
# Time windows (aligned with config.py period declarations)
# ------------------------

WEEKDAY_PEAK_MORNING_START = (7, 0)
WEEKDAY_PEAK_MORNING_END = (10, 30)

WEEKDAY_OFFPEAK_DAY_START = (10, 30)
WEEKDAY_OFFPEAK_DAY_END = (17, 0)

LUNCH_START = (11, 30)
LUNCH_END = (13, 30)

WEEKDAY_PEAK_EVENING_START = (17, 0)
WEEKDAY_PEAK_EVENING_END = (21, 0)

WEEKDAY_OFFPEAK_NIGHT_START = (21, 0)
WEEKDAY_OFFPEAK_NIGHT_END = (7 + 24, 0)

WEEKEND_DAY_START = (9, 0)
WEEKEND_DAY_END = (21, 0)
WEEKEND_NIGHT_START = (21, 0)
WEEKEND_NIGHT_END = (9 + 24, 0)

WEEKDAY_TIME_WINDOWS: Dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "morning": (WEEKDAY_PEAK_MORNING_START, WEEKDAY_PEAK_MORNING_END),
    "lunch": (LUNCH_START, LUNCH_END),
    "day": (WEEKDAY_OFFPEAK_DAY_START, WEEKDAY_OFFPEAK_DAY_END),
    "evening": (WEEKDAY_PEAK_EVENING_START, WEEKDAY_PEAK_EVENING_END),
    "night": (WEEKDAY_OFFPEAK_NIGHT_START, WEEKDAY_OFFPEAK_NIGHT_END),
}

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
    day_seconds = 24 * 3600.0
    if end >= day_seconds:
        if t >= start:
            return True
        return t <= (end - day_seconds)
    if end < start:
        return t >= start or t <= end
    return start <= t <= end


def resolve_time_bucket(day_type: str, time_s: float) -> str:
    """Return the configured time bucket for the given day type and seconds-of-day."""
    windows = TIME_WINDOWS_SECONDS[day_type]
    for bucket in TIME_BUCKET_PRIORITY[day_type]:
        start, end = windows[bucket]
        if _in_window(start, end, time_s):
            return bucket
    # Fallback: default to the longest duration bucket
    if day_type == "weekday":
        return "day"
    return "day"


# ------------------------
# Base category offsets (additive) for initial weighting
# ------------------------

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

# ------------------------
# Time-dependent hotspot multipliers
# ------------------------

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

# Additional per-floor boosts for signature destinations
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
    "resolve_time_bucket",
    "BASE_OFFSETS_FROM_LOBBY",
    "BASE_OFFSETS_FROM_UPPER",
    "HOTSPOT_MULTIPLIERS",
    "FLOOR_SPECIFIC_BONUS",
]
