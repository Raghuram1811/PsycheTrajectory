from __future__ import annotations

from datetime import datetime
import numpy as np

from .kalman import LocalTrendFilter
from .schema import FilterState, InferenceResult, Observation, parse_utc


def infer_window(subject_id: str, observations: list[Observation], timestamp: datetime | str,
                 state: FilterState | None, filter_core: LocalTrendFilter, embedding: np.ndarray | None = None,
                 request_id: str | None = None) -> tuple[FilterState, InferenceResult]:
    cutoff = parse_utc(timestamp)
    eligible = [row for row in observations if row.subject_id == subject_id and row.available_at_utc <= cutoff]
    quality = len(eligible) / max(1, len(observations))
    next_state, detail = filter_core.step(subject_id, cutoff, embedding, state, quality, request_id)
    n = filter_core.dimension
    result = InferenceResult(
        subject_id, cutoff.isoformat(), "exploratory", filter_core.artifact_version,
        float(np.clip(quality, 0, 1)), [] if eligible else ["no_available_observations"],
        "unavailable", None, np.asarray(next_state.mean)[:n, 0].tolist(),
        np.asarray(next_state.mean)[n:, 0].tolist(), np.asarray(next_state.covariance).tolist(),
        detail["prediction_only"], detail["prediction_only"],
        {"depression_symptom": None, "anxiety_symptom": None, "adhd_symptom": None},
        ["baseline_not_supplied", "symptom_head_unavailable:depression_symptom",
         "symptom_head_unavailable:anxiety_symptom", "symptom_head_unavailable:adhd_symptom"],
    )
    return next_state, result
