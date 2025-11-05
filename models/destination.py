"""
Destination generation model / 目标楼层生成模型.

Provides a non-uniform distribution for selecting destination floors conditioned
on (weekday, time of day, origin floor). This is used for simulation realism and
as ground-truth for downstream models.
"""

from __future__ import annotations

import random
from typing import Dict

from models import floor_config as fc

NUM_FLOORS = fc.BUILDING_FLOORS
LOBBY_FLOOR = fc.LOBBY_FLOOR


def _day_type(weekday: int) -> str:
    return "weekend" if weekday >= 5 else "weekday"


def _origin_key(origin_floor: int) -> str:
    return "from_lobby" if origin_floor == LOBBY_FLOOR else "from_upper"


def _base_weight(origin_key: str, tags: set[str]) -> float:
    offsets = (
        fc.BASE_OFFSETS_FROM_LOBBY
        if origin_key == "from_lobby"
        else fc.BASE_OFFSETS_FROM_UPPER
    )
    weight = offsets.get("base", 0.5)
    for tag in tags:
        weight += offsets.get(tag, 0.0)
    return max(weight, 0.0)


def _apply_hotspot_multipliers(
    weight: float,
    *,
    day_type: str,
    origin_key: str,
    bucket: str,
    tags: set[str],
) -> float:
    multipliers = (
        fc.HOTSPOT_MULTIPLIERS.get(day_type, {}).get(origin_key, {}).get(bucket, {})
    )
    for tag in tags:
        factor = multipliers.get(tag)
        if factor is not None:
            weight *= factor
    return weight


def _apply_floor_bonus(
    weight: float, *, day_type: str, bucket: str, floor: int
) -> float:
    bonus = fc.FLOOR_SPECIFIC_BONUS.get(day_type, {}).get(bucket, {}).get(floor)
    if bonus is not None:
        weight *= bonus
    return weight


def _apply_interactions(
    weight: float,
    *,
    origin_floor: int,
    dest_floor: int,
    origin_tags: set[str],
    dest_tags: set[str],
    day_type: str,
    bucket: str,
) -> float:
    if "residential" in origin_tags and "residential" in dest_tags:
        damp = 0.55 if day_type == "weekday" else 0.65
        if bucket in {"night"}:
            damp *= 0.8
        weight *= damp

    if "residential" in origin_tags and "amenity" in dest_tags:
        if day_type == "weekday" and bucket in {"lunch"}:
            weight *= 1.8
        elif day_type == "weekday" and bucket == "day":
            weight *= 1.4
        elif day_type == "weekend" and bucket in {"morning", "brunch", "day"}:
            weight *= 2.1

    if origin_floor == LOBBY_FLOOR and "amenity" in dest_tags and day_type == "weekend":
        if bucket in {"brunch", "day", "evening"}:
            weight *= 1.6

    if "amenity" in origin_tags and "residential" in dest_tags:
        weight *= 0.7

    if dest_floor in fc.PANORAMIC_FLOORS and bucket in {"evening", "night", "brunch"}:
        weight *= 1.3 if day_type == "weekday" else 1.5

    if dest_floor in fc.NIGHTLIFE_FLOORS and bucket == "night":
        weight *= 1.5 if day_type == "weekend" else 1.3

    return weight


def _normalize(weights: list[float]) -> list[float]:
    total = sum(weights)
    if total <= 0:
        n = len(weights)
        return [1.0 / n] * n if n else []
    return [w / total for w in weights]


def destination_distribution(
    weekday: int,
    time_s: float,
    origin_floor: int,
) -> Dict[int, float]:
    """
    返回楼层→概率 dict，表示 P(dest | weekday, time_s, origin_floor)。
    """
    if origin_floor < 1 or origin_floor > NUM_FLOORS:
        raise ValueError("origin_floor out of range.")

    day_type = _day_type(weekday)
    bucket = fc.resolve_time_bucket(day_type, time_s)
    origin_key = _origin_key(origin_floor)
    origin_tags = fc.floor_tags(origin_floor)

    candidate_floors = [f for f in range(1, NUM_FLOORS + 1) if f != origin_floor]
    weights: list[float] = []

    for floor in candidate_floors:
        tags = fc.floor_tags(floor)
        weight = _base_weight(origin_key, tags)
        if weight <= 0.0:
            weights.append(0.0)
            continue

        weight = _apply_hotspot_multipliers(
            weight,
            day_type=day_type,
            origin_key=origin_key,
            bucket=bucket,
            tags=tags,
        )
        weight = _apply_floor_bonus(
            weight, day_type=day_type, bucket=bucket, floor=floor
        )
        weight = _apply_interactions(
            weight,
            origin_floor=origin_floor,
            dest_floor=floor,
            origin_tags=origin_tags,
            dest_tags=tags,
            day_type=day_type,
            bucket=bucket,
        )

        weights.append(max(weight, 0.0))

    probs = _normalize(weights)
    return {floor: p for floor, p in zip(candidate_floors, probs)}


def sample_destination(
    weekday: int,
    time_s: float,
    origin_floor: int,
    *,
    exclude: set[int] | None = None,
) -> int:
    """
    从 P(dest | weekday, time_s, origin_floor) 中采样一个具体的目的楼层。
    """
    dist = destination_distribution(weekday, time_s, origin_floor)
    if exclude:
        filtered = {f: w for f, w in dist.items() if f not in exclude}
        if not filtered:
            raise RuntimeError("Exclude set removes all candidate floors.")
        total = sum(filtered.values())
        dist = {f: w / total for f, w in filtered.items()}
    if not dist:
        raise RuntimeError("No candidate floors available for sampling.")
    floors = list(dist.keys())
    weights = list(dist.values())
    return random.choices(floors, weights=weights, k=1)[0]


__all__ = ["destination_distribution", "sample_destination"]
