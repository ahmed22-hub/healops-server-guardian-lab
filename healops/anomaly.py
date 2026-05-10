#!/usr/bin/env python3
"""
HealOps anomaly detection engine.

Simple baseline-based anomaly detection using z-score logic.
No heavy ML dependency required for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable, Optional


@dataclass
class AnomalyResult:
    is_anomaly: bool
    score: float
    level: str
    reason: str
    baseline_mean: float
    baseline_std: float
    current_value: float


def calculate_z_score(current_value: float, baseline_values: Iterable[float]) -> AnomalyResult:
    values = [float(v) for v in baseline_values if v is not None]

    if len(values) < 5:
        return AnomalyResult(
            is_anomaly=False,
            score=0.0,
            level="none",
            reason="not_enough_baseline_data",
            baseline_mean=0.0,
            baseline_std=0.0,
            current_value=float(current_value),
        )

    baseline_mean = mean(values)
    baseline_std = pstdev(values)

    if baseline_std == 0:
        score = 0.0 if current_value == baseline_mean else 10.0
    else:
        score = abs((float(current_value) - baseline_mean) / baseline_std)

    if score >= 4:
        level = "critical"
    elif score >= 3:
        level = "high"
    elif score >= 2:
        level = "medium"
    else:
        level = "none"

    return AnomalyResult(
        is_anomaly=score >= 2,
        score=round(score, 2),
        level=level,
        reason="z_score_threshold_exceeded" if score >= 2 else "normal",
        baseline_mean=round(baseline_mean, 2),
        baseline_std=round(baseline_std, 2),
        current_value=round(float(current_value), 2),
    )


def moving_average(values: Iterable[float], window: int = 5) -> Optional[float]:
    clean_values = [float(v) for v in values if v is not None]

    if len(clean_values) < window:
        return None

    return round(mean(clean_values[-window:]), 2)


def detect_spike(current_value: float, historical_values: Iterable[float]) -> AnomalyResult:
    return calculate_z_score(current_value, historical_values)


def detect_restart_anomaly(current_restarts: float, historical_restarts: Iterable[float]) -> AnomalyResult:
    return calculate_z_score(current_restarts, historical_restarts)