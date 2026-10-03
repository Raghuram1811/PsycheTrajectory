from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import numpy as np

from .schema import SymptomLabel, parse_utc
from .splits import subject_split


_SUPPORTED = {"depression_symptom": {"phq-9", "phq9"}, "anxiety_symptom": {"gad-7", "gad7"}}
_ALL_TARGETS = ("depression_symptom", "anxiety_symptom", "adhd_symptom")


def train_ridge_heads(trajectory_rows: list[dict[str, Any]], labels: list[SymptomLabel], seed: int = 17,
                      alpha: float = 1.0, min_subjects: int = 5) -> dict:
    """Train independent score regressions; one causal row is paired to each assessment."""
    groups: dict[str, list[tuple[np.ndarray, float, str]]] = {name: [] for name in _ALL_TARGETS}
    by_subject: dict[str, list[dict]] = {}
    for row in trajectory_rows:
        by_subject.setdefault(row["subject_id"], []).append(row)
    for rows in by_subject.values():
        rows.sort(key=lambda item: parse_utc(item["timestamp"]))
    for label in labels:
        allowed = _SUPPORTED.get(label.target)
        if not allowed or label.instrument.strip().lower() not in allowed:
            continue
        candidates = [row for row in by_subject.get(label.subject_id, [])
                      if parse_utc(row["timestamp"]) <= parse_utc(label.assessment_time_utc)
                      and row.get("latent_level") and row.get("latent_velocity_per_day")]
        if not candidates:
            continue
        row = candidates[-1]
        vector = np.asarray(row["latent_level"] + row["latent_velocity_per_day"], dtype=float)
        if not np.all(np.isfinite(vector)) or not np.isfinite(label.score):
            continue
        groups[label.target].append((vector, float(label.score), label.subject_id))

    split = subject_split((row["subject_id"] for row in trajectory_rows), seed)
    heads: dict[str, dict | None] = {target: None for target in _ALL_TARGETS}
    reports = {}
    for target, examples in groups.items():
        # Do not fit a head unless the participant-disjoint training partition is adequate.
        train = [item for item in examples if item[2] in split["train"]]
        validation = [item for item in examples if item[2] in split["validation"]]
        if target == "adhd_symptom" or len({item[2] for item in train}) < min_subjects:
            reports[target] = {"status": "unavailable", "reason": "insufficient supported participant-disjoint labels"}
            continue
        x_train = np.stack([item[0] for item in train])
        y_train = np.asarray([item[1] for item in train])
        mean, scale = x_train.mean(0), x_train.std(0)
        scale[scale < 1e-8] = 1.0
        x_scaled = (x_train - mean) / scale
        design = np.column_stack([np.ones(len(x_scaled)), x_scaled])
        penalty = np.eye(design.shape[1]) * alpha
        penalty[0, 0] = 0
        coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y_train)
        heads[target] = {"instrument": next(iter(_SUPPORTED[target])), "feature_names": "latent_level followed by latent_velocity_per_day",
                         "mean": mean.tolist(), "scale": scale.tolist(), "coefficients": coefficients.tolist(),
                         "alpha": alpha, "training_subjects": sorted({item[2] for item in train}),
                         "target_semantics": "questionnaire symptom score estimate; not diagnosis"}
        if validation:
            x_val = np.stack([item[0] for item in validation])
            y_val = np.asarray([item[1] for item in validation])
            design_val = np.column_stack([np.ones(len(x_val)), (x_val - mean) / scale])
            errors = design_val @ coefficients - y_val
            metrics = {"mae": float(np.abs(errors).mean()), "rmse": float(np.sqrt(np.mean(errors ** 2))),
                       "validation_participants": len({item[2] for item in validation})}
        else:
            metrics = {"status": "unavailable", "reason": "no validation participants"}
        reports[target] = {"status": "trained", "metrics": metrics, "validation_is_external": False}
    return {"schema_version": "symptom-heads-v1", "mode": "research_labeled", "heads": heads,
            "reports": reports, "participant_split": split, "clinical_validation": False,
            "label_pairing": "one latest available causal filtered state at or before each assessment timestamp",
            "minimum_training_subjects_per_head": min_subjects, "seed": seed,
            "ridge_alpha": alpha, "prediction_task": "contemporaneous questionnaire symptom score estimate"}


def write_heads(path: str | Path, artifact: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


def predict_symptom_heads(artifact: dict, latent_level: np.ndarray, latent_velocity: np.ndarray) -> dict:
    output = {target: None for target in _ALL_TARGETS}
    for target in _ALL_TARGETS:
        head = artifact.get("heads", {}).get(target)
        if not head:
            continue
        mean = np.asarray(head["mean"], dtype=float)
        scale = np.asarray(head["scale"], dtype=float)
        coefficients = np.asarray(head["coefficients"], dtype=float)
        vector = np.concatenate([latent_level, latent_velocity])
        if vector.shape != mean.shape:
            continue
        estimate = coefficients[0] + np.dot((vector - mean) / scale, coefficients[1:])
        dimension = len(latent_level)
        daily_change = float(np.dot(coefficients[1:1 + dimension] / scale[:dimension], latent_velocity))
        output[target] = {"score_estimate": float(estimate), "score_trend_per_day": daily_change,
                          "trend": "increasing" if daily_change > 1e-6 else "decreasing" if daily_change < -1e-6 else "stable",
                          "instrument": head["instrument"], "interpretation": "symptom score estimate, not diagnosis"}
    return output
