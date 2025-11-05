from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Sequence, Tuple

from models import config as cfg
from models.request import generate_requests_weekday, generate_requests_weekend
from scheduler.mpc_scheduler.destination_prediction import (
    DestinationLogisticModel,
    EvaluationResult,
    TrainingResult,
)


DAY_SCHEDULE: Sequence[Tuple[str, str]] = (
    ("Mon", "weekday"),
    ("Tue", "weekday"),
    ("Wed", "weekday"),
    ("Thu", "weekday"),
    ("Fri", "weekday"),
    ("Sat", "weekend"),
    ("Sun", "weekend"),
)

DAY_NAME_TO_WEEKDAY: Dict[str, int] = {
    label: idx for idx, (label, _) in enumerate(DAY_SCHEDULE)
}


def _select_day(day_label: str) -> Tuple[str, str]:
    normalized = day_label.strip().title()
    for label, day_type in DAY_SCHEDULE:
        if label == normalized:
            return label, day_type
    raise ValueError(
        f"Unknown day label '{day_label}'. Expected one of: "
        f"{', '.join(label for label, _ in DAY_SCHEDULE)}"
    )


def _format_metrics(
    epoch: int, train_result: TrainingResult | None, metrics: EvaluationResult | None
) -> str:
    train_loss = train_result.final_loss if train_result else float("nan")
    sample_count = train_result.total_samples if train_result else 0
    if metrics is None:
        return (
            f"    Epoch {epoch:4d} | train_loss={train_loss:.4f} | "
            f"batch_samples={sample_count}"
        )
    return (
        f"    Epoch {epoch:4d} | train_loss={train_loss:.4f} | "
        f"eval_loss={metrics.log_loss:.4f} | top1={metrics.top1_accuracy*100:5.2f}% | "
        f"top3={metrics.top3_accuracy*100:5.2f}% | batch_samples={sample_count} | "
        f"eval_samples={metrics.samples}"
    )


def _chunk_requests(requests: Sequence[object], batch_size: int) -> List[List[object]]:
    batch_size = max(1, batch_size)
    return [list(requests[i : i + batch_size]) for i in range(0, len(requests), batch_size)]


def _load_offline_dataset(data_dir: str) -> List[Dict[str, object]]:
    root = Path(data_dir)
    if not root.exists():
        print(f"[Offline] Data directory not found: {data_dir}")
        return []

    dataset: List[Dict[str, object]] = []
    for file_path in sorted(root.glob("*.json")):
        try:
            with file_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except Exception as exc:
            print(f"[Offline] Failed to load {file_path}: {exc}")
            continue

        if isinstance(payload, dict) and "requests" in payload:
            records = payload.get("requests", [])
            weekday = int(payload.get("weekday", 0))
            day_label = payload.get("day_label", file_path.stem)
            day_index = int(payload.get("day_index", len(dataset)))
        elif isinstance(payload, list):
            records = payload
            weekday = int(payload[0].get("weekday", 0)) if payload else 0
            day_label = file_path.stem
            day_index = len(dataset)
        else:
            continue

        requests_list: List[SimpleNamespace] = []
        for rec in records:
            try:
                requests_list.append(
                    SimpleNamespace(
                        origin=int(rec["origin"]),
                        destination=int(rec["destination"]),
                        arrival_time=float(rec["arrival_time"]),
                        load=float(rec.get("load", 0.0)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

        dataset.append(
            {
                "weekday": weekday,
                "day_label": day_label,
                "day_index": day_index,
                "requests": requests_list,
            }
        )

    dataset.sort(key=lambda item: item.get("day_index", 0))
    return dataset


def _train_from_directory(
    data_dir: str,
    *,
    load_model_path: str | None,
    save_model_path: str | None,
    batch_size: int,
    epochs: int,
    learning_rate: float,
    l2_strength: float,
) -> None:
    dataset = _load_offline_dataset(data_dir)
    if not dataset:
        print(f"[Offline] No training data found in {data_dir}.")
        return

    if load_model_path and Path(load_model_path).exists():
        model = DestinationLogisticModel.load(load_model_path)
        model.set_learning_rate(learning_rate)
        model.set_regularisation(l2_strength)
        print(f"[Offline] Loaded existing model from {load_model_path}")
    else:
        if load_model_path:
            print(
                f"[Offline] Warning: load-model '{load_model_path}' not found. Starting fresh."
            )
        model = DestinationLogisticModel(
            weekday_cardinality=7,
            learning_rate=learning_rate,
            l2_strength=l2_strength,
            epochs_per_update=1,
        )

    total_samples = 0
    for entry in dataset:
        weekday = int(entry.get("weekday", 0))
        day_label = entry.get("day_label", "?")
        requests = entry.get("requests", [])
        if not requests:
            continue
        print(
            f"[Offline] Training {day_label} (weekday {weekday}) with {len(requests)} samples."
        )
        for batch in _chunk_requests(requests, batch_size):
            model.fit_batch(batch, weekday=weekday, epochs=epochs)
            total_samples += len(batch)

    if save_model_path:
        os.makedirs(os.path.dirname(save_model_path) or ".", exist_ok=True)
        model.save(save_model_path)
        print(
            f"[Offline] Saved model to {save_model_path} (trained on {total_samples} samples)."
        )

def train_single_day(
    day_label: str,
    *,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weekday_requests: int,
    weekend_requests: int,
    eval_samples: int | None = None,
    log_interval: int = 10,
    l2_strength: float = 1e-4,
    seed_shift: int = 0,
    model: DestinationLogisticModel | None = None,
    save_path: str | None = None,
) -> Tuple[DestinationLogisticModel, EvaluationResult | None]:
    label, day_type = _select_day(day_label)
    weekday_index = DAY_NAME_TO_WEEKDAY[label]

    if model is None:
        model = DestinationLogisticModel(
            weekday_cardinality=7,
            learning_rate=learning_rate,
            l2_strength=l2_strength,
            epochs_per_update=1,
            random_seed=1234 + seed_shift,
        )
    else:
        model.set_learning_rate(learning_rate)
        model.set_regularisation(l2_strength)

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if log_interval <= 0:
        log_interval = 10

    generator = (
        generate_requests_weekday if day_type == "weekday" else generate_requests_weekend
    )
    total_requests = weekday_requests if day_type == "weekday" else weekend_requests
    requests = generator(total_requests, seed_shift=seed_shift)
    if not requests:
        raise RuntimeError("No requests generated; cannot train")

    rng = random.Random(seed_shift + 2025)
    if eval_samples is not None and eval_samples > 0 and eval_samples < len(requests):
        eval_set = rng.sample(requests, eval_samples)
    else:
        eval_set = list(requests)

    print(
        f"\n=== Training on {label} ({day_type}) | epochs={epochs} | batch={batch_size} ==="
    )

    last_metrics: EvaluationResult | None = None
    for epoch in range(1, epochs + 1):
        lr_factor = 0.5 ** (epoch // 500)
        model.set_learning_rate(learning_rate * lr_factor)

        if batch_size >= len(requests):
            batch = requests
        else:
            batch = rng.sample(requests, batch_size)

        train_result = model.fit_batch(batch, weekday=weekday_index, epochs=1)

        should_log = (epoch % log_interval == 0) or (epoch == 1) or (epoch == epochs)
        if should_log:
            metrics = model.evaluate(eval_set, weekday=weekday_index)
            print(_format_metrics(epoch, train_result, metrics))
            last_metrics = metrics

    if save_path:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        model.save(save_path)
        print(f"Saved model to: {save_path}")

    return model, last_metrics


def train_full_week(
    *,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weekday_requests: int,
    weekend_requests: int,
    eval_samples: int | None,
    log_interval: int,
    l2_strength: float,
    seed: int,
    reset_each_day: bool,
    save_per_day_dir: str | None = None,
) -> DestinationLogisticModel:
    model: DestinationLogisticModel | None = None
    for day_offset, (label, _) in enumerate(DAY_SCHEDULE):
        if reset_each_day:
            model = None

        per_day_path = None
        if save_per_day_dir:
            os.makedirs(save_per_day_dir, exist_ok=True)
            per_day_path = os.path.join(save_per_day_dir, f"dest_model_{label}.pkl")

        model, _ = train_single_day(
            label,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            weekday_requests=weekday_requests,
            weekend_requests=weekend_requests,
            eval_samples=eval_samples,
            log_interval=log_interval,
            l2_strength=l2_strength,
            seed_shift=seed + day_offset,
            model=model,
            save_path=per_day_path,
        )

    if model is None:
        raise RuntimeError("Training failed to produce a model")
    return model


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train the destination predictor on a single day or over an entire week."
        )
    )
    parser.add_argument(
        "--day",
        type=str,
        default="Mon",
        help="Day label to train on (e.g., Mon). Ignored when --week is set.",
    )
    parser.add_argument(
        "--week",
        action="store_true",
        help="Train sequentially across the full week (Mon-Sun).",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="",
        help="Directory containing offline JSON request logs for training.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of epochs for each day (default: 50).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of samples per epoch batch update (default: 500).",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.1,
        help="Base learning rate for SGD updates (default: 0.1).",
    )
    parser.add_argument(
        "--l2",
        type=float,
        default=1e-4,
        help="L2 regularisation strength (default: 1e-4).",
    )
    parser.add_argument(
        "--weekday-requests",
        type=int,
        default=cfg.WEEKDAY_TOTAL_REQUESTS,
        help="Number of weekday requests to sample from (default: config value).",
    )
    parser.add_argument(
        "--weekend-requests",
        type=int,
        default=cfg.WEEKEND_TOTAL_REQUESTS,
        help="Number of weekend requests to sample from (default: config value).",
    )
    parser.add_argument(
        "--eval-samples",
        type=int,
        default=1000,
        help="Evaluation sample size (default: 1000; <=0 for full pool).",
    )
    parser.add_argument(
        "--log-interval",
        type=int,
        default=10,
        help="Log metrics every N epochs (default: 10).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed shift for reproducible sampling (default: 0).",
    )
    parser.add_argument(
        "--reset-each-day",
        action="store_true",
        help="When running --week, reinitialise the model for each day.",
    )
    parser.add_argument(
        "--save-model",
        type=str,
        default="",
        help="Optional path to save the final model (single day or after full week).",
    )
    parser.add_argument(
        "--save-per-day",
        type=str,
        default="",
        help="When --week is set, save model after each day into this directory.",
    )
    parser.add_argument(
        "--load-model",
        type=str,
        default="",
        help="Optional path to an existing model to initialise from.",
    )

    args = parser.parse_args()

    data_dir = args.data_dir.strip() or None
    load_model_path = args.load_model.strip() or None
    final_save_path = args.save_model.strip() or None
    per_day_dir = args.save_per_day.strip() or None

    if data_dir:
        _train_from_directory(
            data_dir,
            load_model_path=load_model_path,
            save_model_path=final_save_path,
            batch_size=args.batch_size,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            l2_strength=args.l2,
        )
        return

    eval_samples = (
        None
        if args.eval_samples is not None and args.eval_samples <= 0
        else args.eval_samples
    )

    if args.week:
        model = train_full_week(
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            weekday_requests=args.weekday_requests,
            weekend_requests=args.weekend_requests,
            eval_samples=eval_samples,
            log_interval=args.log_interval,
            l2_strength=args.l2,
            seed=args.seed,
            reset_each_day=args.reset_each_day,
            save_per_day_dir=per_day_dir,
        )
        if final_save_path:
            os.makedirs(os.path.dirname(final_save_path) or ".", exist_ok=True)
            model.save(final_save_path)
            print(f"Saved final model to: {final_save_path}")
    else:
        model, _ = train_single_day(
            args.day,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            weekday_requests=args.weekday_requests,
            weekend_requests=args.weekend_requests,
            eval_samples=eval_samples,
            log_interval=args.log_interval,
            l2_strength=args.l2,
            seed_shift=args.seed,
            save_path=final_save_path,
        )
        if final_save_path is None:
            # Inform user they can still save manually
            pass


if __name__ == "__main__":
    main()
