"""
Lightweight prediction API for MPC integration.

This module keeps a process-level singleton of the destination predictor and
exposes tiny helper functions that MPC can call without caring about the model
internals. Intended usage:

    from scheduler.mpc_scheduler.prediction_api import (
        load_destination_model,
        predict_dest_top1,
        predict_dest_distribution,
        is_ready,
    )

    load_destination_model("path/to/model.pkl")
    if is_ready():
        dest = predict_dest_top1(origin, time_s, weekday)

You can also inject an already-constructed model via set_destination_model().
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from scheduler.mpc_scheduler.destination_prediction import DestinationLogisticModel

_MODEL: DestinationLogisticModel | None = None


def set_destination_model(model: DestinationLogisticModel) -> None:
    global _MODEL
    _MODEL = model


def load_destination_model(path: str) -> None:
    """Load a saved model (.pkl) and install it as the active predictor."""
    model = DestinationLogisticModel.load(path)
    set_destination_model(model)


def is_ready() -> bool:
    return _MODEL is not None


def predict_dest_distribution(
    origin: int,
    time_s: float,
    weekday: int,
    *,
    exclude_origin: bool = True,
) -> Dict[int, float]:
    if _MODEL is None:
        raise RuntimeError("Destination model not loaded. Call load_destination_model(path) first.")
    return _MODEL.predict_distribution_dict(origin, time_s, weekday, exclude_origin=exclude_origin)


def predict_dest_topk(
    origin: int,
    time_s: float,
    weekday: int,
    *,
    k: int = 1,
    exclude_origin: bool = True,
) -> List[Tuple[int, float]]:
    if _MODEL is None:
        raise RuntimeError("Destination model not loaded. Call load_destination_model(path) first.")
    return _MODEL.predict_topk(origin, time_s, weekday, k=k, exclude_origin=exclude_origin)


def predict_dest_top1(
    origin: int,
    time_s: float,
    weekday: int,
    *,
    exclude_origin: bool = True,
) -> int:
    if _MODEL is None:
        raise RuntimeError("Destination model not loaded. Call load_destination_model(path) first.")
    return _MODEL.predict_argmax(origin, time_s, weekday, exclude_origin=exclude_origin)


__all__ = [
    "set_destination_model",
    "load_destination_model",
    "is_ready",
    "predict_dest_distribution",
    "predict_dest_topk",
    "predict_dest_top1",
]
