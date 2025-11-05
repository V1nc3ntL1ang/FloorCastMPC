"""
Destination floor prediction model powered by sklearn's SGDClassifier.

The model approximates P(dest | origin, time_of_day, weekday) using a
multinomial logistic regression trained via stochastic gradient descent.
It provides convenience helpers for MPC integration (top-k predictions,
distribution dictionaries) and persistence utilities (save/load).
"""

from __future__ import annotations

import math
import os
import pickle
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
for _var, _value in (
    ("KMP_AFFINITY", "disabled"),
    ("KMP_HW_SUBSET", "1t"),
    ("KMP_INIT_AT_FORK", "FALSE"),
    ("KMP_DUPLICATE_LIB_OK", "TRUE"),
):
    os.environ.setdefault(_var, _value)
_kmp_dir = os.path.join(os.getcwd(), "._kmp_shared")
os.makedirs(_kmp_dir, exist_ok=True)
os.environ.setdefault("KMP_SHARED_FILES_DIRECTORY", _kmp_dir)

import numpy as np
from sklearn.linear_model import SGDClassifier

from models import config as cfg


SECONDS_PER_DAY = 24 * 3600.0


def _time_fourier_features(time_s: float) -> tuple[float, float]:
    phase = (time_s % SECONDS_PER_DAY) / SECONDS_PER_DAY
    angle = phase * 2.0 * math.pi
    return math.sin(angle), math.cos(angle)


def _one_hot(index: int, size: int) -> np.ndarray:
    vec = np.zeros(size, dtype=np.float64)
    if 0 <= index < size:
        vec[index] = 1.0
    return vec


@dataclass
class EvaluationResult:
    samples: int
    log_loss: float
    top1_accuracy: float
    top3_accuracy: float


@dataclass
class TrainingResult:
    epochs: int
    final_loss: float
    total_samples: int


class DestinationLogisticModel:
    def __init__(
        self,
        *,
        weekday_cardinality: int = 7,
        learning_rate: float = 0.1,
        l2_strength: float = 1e-4,
        epochs_per_update: int = 40,
        random_seed: int | None = None,
    ) -> None:
        self.num_floors = cfg.BUILDING_FLOORS
        self.weekday_cardinality = weekday_cardinality
        self.learning_rate = float(learning_rate)
        self.l2_strength = float(l2_strength)
        self.epochs_per_update = max(1, epochs_per_update)
        self.random_seed = random_seed

        self._feature_dim = self.num_floors + 2 + self.weekday_cardinality + 1
        self._clf = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=self.l2_strength,
            learning_rate="constant",
            eta0=self.learning_rate,
            random_state=random_seed,
        )
        self._classes = np.arange(self.num_floors, dtype=np.int32)
        self._trained = False

    # ------------------------------------------------------------------ #
    # Hyper-parameter control
    # ------------------------------------------------------------------ #
    def set_learning_rate(self, eta: float) -> None:
        eta = float(max(1e-6, eta))
        self.learning_rate = eta
        self._clf.set_params(eta0=eta)

    def set_regularisation(self, alpha: float) -> None:
        alpha = float(max(0.0, alpha))
        self.l2_strength = alpha
        self._clf.set_params(alpha=alpha)

    # ------------------------------------------------------------------ #
    # Feature handling
    # ------------------------------------------------------------------ #
    def _encode(self, origin: int, time_s: float, weekday: int) -> np.ndarray:
        origin_vec = _one_hot(origin - 1, self.num_floors)
        sin_t, cos_t = _time_fourier_features(time_s)
        weekday_vec = _one_hot(int(weekday) % self.weekday_cardinality, self.weekday_cardinality)
        return np.concatenate(
            (
                origin_vec,
                np.array([sin_t, cos_t], dtype=np.float64),
                weekday_vec,
                np.array([1.0], dtype=np.float64),
            )
        )

    def _build_dataset(
        self, requests: Iterable[object], weekday: int
    ) -> tuple[np.ndarray, np.ndarray]:
        features: List[np.ndarray] = []
        labels: List[int] = []
        for req in requests:
            dest = int(req.destination) - 1
            if dest < 0 or dest >= self.num_floors:
                continue
            features.append(self._encode(req.origin, req.arrival_time, weekday))
            labels.append(dest)
        if not features:
            return (
                np.empty((0, self._feature_dim), dtype=np.float64),
                np.empty(0, dtype=np.int32),
            )
        X = np.vstack(features)
        y = np.asarray(labels, dtype=np.int32)
        return X, y

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def add_samples(self, requests: Iterable[object], *, weekday: int) -> None:
        X, y = self._build_dataset(requests, weekday)
        if X.shape[0] == 0:
            return
        if not self._trained:
            self._clf.partial_fit(X, y, classes=self._classes)
            self._trained = True
        else:
            self._clf.partial_fit(X, y)

    def train(self, epochs: int | None = None) -> TrainingResult | None:
        if not self._trained:
            return None
        return TrainingResult(epochs=0, final_loss=float("nan"), total_samples=0)

    def fit_batch(
        self,
        requests: Sequence[object],
        *,
        weekday: int,
        epochs: int | None = None,
    ) -> TrainingResult | None:
        X, y = self._build_dataset(requests, weekday)
        if X.shape[0] == 0:
            return None
        epochs_to_run = self.epochs_per_update if epochs is None else max(1, epochs)
        for _ in range(epochs_to_run):
            if not self._trained:
                self._clf.partial_fit(X, y, classes=self._classes)
                self._trained = True
            else:
                self._clf.partial_fit(X, y)
        loss = self._compute_log_loss(X, y)
        return TrainingResult(epochs=epochs_to_run, final_loss=loss, total_samples=X.shape[0])

    def evaluate(
        self, requests: Sequence[object], *, weekday: int
    ) -> EvaluationResult | None:
        if not self._trained:
            return None
        X, y = self._build_dataset(requests, weekday)
        if X.shape[0] == 0:
            return None
        probs = self._predict_proba_matrix(X)
        log_loss = self._compute_log_loss_from_probs(probs, y)
        top1 = float(np.mean(np.argmax(probs, axis=1) == y))
        k = min(3, probs.shape[1])
        topk_idx = np.argpartition(probs, kth=-k, axis=1)[:, -k:]
        top3 = float(np.mean([y[i] in topk_idx[i] for i in range(len(y))]))
        return EvaluationResult(samples=len(y), log_loss=log_loss, top1_accuracy=top1, top3_accuracy=top3)

    def predict_proba(self, origin: int, time_s: float, weekday: int) -> np.ndarray:
        if not self._trained:
            return np.full(self.num_floors, 1.0 / self.num_floors)
        X = self._encode(origin, time_s, weekday)[None, :]
        probs = self._predict_proba_matrix(X)[0]
        return probs

    # ------------------------------
    # Convenience helpers
    # ------------------------------
    def predict_distribution_dict(
        self,
        origin: int,
        time_s: float,
        weekday: int,
        *,
        exclude_origin: bool = True,
    ) -> Dict[int, float]:
        probs = self.predict_proba(origin, time_s, weekday).tolist()
        if exclude_origin and 1 <= origin <= self.num_floors:
            probs[origin - 1] = 0.0
            total = sum(probs)
            if total > 0:
                probs = [p / total for p in probs]
            else:
                probs = [1.0 / self.num_floors] * self.num_floors
        return {i + 1: float(p) for i, p in enumerate(probs)}

    def predict_topk(
        self,
        origin: int,
        time_s: float,
        weekday: int,
        *,
        k: int = 1,
        exclude_origin: bool = True,
    ) -> List[Tuple[int, float]]:
        dist = self.predict_distribution_dict(origin, time_s, weekday, exclude_origin=exclude_origin)
        return sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[: max(1, k)]

    def predict_argmax(
        self,
        origin: int,
        time_s: float,
        weekday: int,
        *,
        exclude_origin: bool = True,
    ) -> int:
        return self.predict_topk(origin, time_s, weekday, k=1, exclude_origin=exclude_origin)[0][0]

    # ------------------------------
    # Persistence
    # ------------------------------
    def save(self, path: str) -> None:
        payload = {
            "backend": "sklearn",
            "num_floors": self.num_floors,
            "weekday_cardinality": self.weekday_cardinality,
            "feature_dim": self._feature_dim,
            "learning_rate": self.learning_rate,
            "l2_strength": self.l2_strength,
            "epochs_per_update": self.epochs_per_update,
            "random_seed": self.random_seed,
            "clf": self._clf,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)

    @classmethod
    def load(cls, path: str) -> "DestinationLogisticModel":
        with open(path, "rb") as f:
            payload = pickle.load(f)
        if payload.get("backend") != "sklearn":
            raise ValueError("Unsupported model file format. Please retrain using the sklearn pipeline.")
        model = cls(
            weekday_cardinality=int(payload.get("weekday_cardinality", 7)),
            learning_rate=float(payload.get("learning_rate", 0.1)),
            l2_strength=float(payload.get("l2_strength", 1e-4)),
            epochs_per_update=int(payload.get("epochs_per_update", 1)),
            random_seed=payload.get("random_seed"),
        )
        model.num_floors = int(payload.get("num_floors", cfg.BUILDING_FLOORS))
        model._feature_dim = int(payload.get("feature_dim", model._feature_dim))
        model._clf = payload["clf"]
        model._classes = np.arange(model.num_floors, dtype=np.int32)
        model._trained = True
        return model

    # ------------------------------
    # Internal helpers
    # ------------------------------
    def _predict_proba_matrix(self, X: np.ndarray) -> np.ndarray:
        probs = self._clf.predict_proba(X)
        if probs.shape[1] != self.num_floors:
            full = np.zeros((probs.shape[0], self.num_floors), dtype=np.float64)
            classes = self._clf.classes_.astype(int)
            for idx, cls_idx in enumerate(classes):
                full[:, cls_idx] = probs[:, idx]
            probs = full
        return probs

    def _compute_log_loss(self, X: np.ndarray, y: np.ndarray) -> float:
        probs = self._predict_proba_matrix(X)
        return self._compute_log_loss_from_probs(probs, y)

    @staticmethod
    def _compute_log_loss_from_probs(probs: np.ndarray, y: np.ndarray) -> float:
        eps = 1e-12
        good = np.clip(probs[np.arange(len(y)), y], eps, 1.0)
        return float(-np.mean(np.log(good)))


__all__ = [
    "DestinationLogisticModel",
    "EvaluationResult",
    "TrainingResult",
]
