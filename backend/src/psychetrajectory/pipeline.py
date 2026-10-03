from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable
import numpy as np

from .encoder import embed, load_encoder, train_encoder
from .heads import predict_symptom_heads
from .kalman import LocalTrendFilter
from .preprocessing import FEATURES, aggregate_daily, causal_impute
from .schema import DailyFeature, InferenceResult, Observation
from .splits import subject_split


def feature_matrix(rows: list[DailyFeature], feature_names: tuple[str, ...] = FEATURES) -> tuple[np.ndarray, np.ndarray]:
    values = np.array([[row.values.get(name) or 0.0 for name in feature_names] for row in rows], dtype=float)
    mask = np.array([[bool(row.observed.get(name)) for name in feature_names] for row in rows], dtype=bool)
    return values, mask


def dataset_fingerprint(observations: list[Observation]) -> str:
    canonical = "\n".join(json.dumps(row.as_dict(), sort_keys=True, default=str) for row in sorted(
        observations, key=lambda x: (x.subject_id, x.event_time_utc, x.signal_name, x.source)))
    return hashlib.sha256(canonical.encode()).hexdigest()


def train_daily_encoder(observations: list[Observation], output: str | Path, seed: int = 17,
                        latent_dim: int = 8) -> dict:
    daily = aggregate_daily(observations, max(x.available_at_utc for x in observations))
    split = subject_split((row.subject_id for row in daily), seed)
    train_rows = [row for row in daily if row.subject_id in split["train"]]
    # Fit scaler and encoder only on training participants. Rows remain chronological within each subject.
    values, masks = feature_matrix(train_rows)
    metrics = train_encoder(values, masks, output, latent_dim=latent_dim, seed=seed)
    metrics["split_subjects"] = split
    metrics["dataset_fingerprint"] = dataset_fingerprint(observations)
    metrics["evaluation_note"] = "Reconstruction only; no clinical or symptom validity is established."
    Path(output).with_suffix(".json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def replay_subject(subject_id: str, observations: list[Observation], encoder_path: str | Path,
                   config: dict | None = None, symptom_heads: dict | None = None) -> list[InferenceResult]:
    config = config or {}
    selected = [item for item in observations if item.subject_id == subject_id]
    if not selected:
        return []
    daily = causal_impute(aggregate_daily(selected, max(x.available_at_utc for x in selected),
                                          float(config.get("min_daily_coverage", 0.25))),
                          int(config.get("imputation_max_days", 1)))
    model, scaler_mean, scaler_scale, encoder_version = load_encoder(encoder_path)
    values, masks = feature_matrix(daily)
    latents, _reconstruction = embed(model, values, masks, scaler_mean, scaler_scale)
    encoder_hash = hashlib.sha256(Path(encoder_path).read_bytes()).hexdigest()
    expected_hash = config.get("encoder_sha256")
    if expected_hash and expected_hash != encoder_hash:
        raise ValueError("filter configuration was tuned for a different encoder artifact")
    version = f"{encoder_version}:{encoder_hash[:12]}"
    filt = _filter(config, latents.shape[1], version)
    state = None
    results = []
    eligible_baseline = []
    minimum = int(config.get("baseline_min_days", 7))
    for row, latent in zip(daily, latents):
        usable = row.coverage >= float(config.get("min_daily_coverage", 0.25))
        observed = latent if usable else None
        state, details = filt.step(subject_id, datetime.fromisoformat(row.day_utc).replace(tzinfo=timezone.utc), observed,
                                  state, quality=max(0.05, row.coverage), request_id=row.day_utc)
        level = np.asarray(state.mean)[:len(latent), 0]
        baseline_ready = len(eligible_baseline) >= minimum
        baseline = np.mean(eligible_baseline, axis=0) if baseline_ready else None
        deviation = (level - baseline).tolist() if baseline is not None else None
        if usable and len(eligible_baseline) < minimum:
            eligible_baseline.append(level.copy())
        reasons = []
        if not usable:
            reasons.append("insufficient_feature_coverage")
        if not baseline_ready:
            reasons.append("baseline_history_insufficient")
        estimates = predict_symptom_heads(symptom_heads or {}, level, np.asarray(state.mean)[len(latent):, 0])
        reasons.extend(f"symptom_head_unavailable:{name}" for name, estimate in estimates.items() if estimate is None)
        results.append(InferenceResult(
            subject_id, row.day_utc + "T23:59:59Z", "exploratory", version, row.coverage,
            list(row.quality_flags), "ready" if baseline_ready else "building",
            deviation, level.tolist(), np.asarray(state.mean)[len(latent):, 0].tolist(),
            np.asarray(state.covariance).tolist(), details["prediction_only"], details["prediction_only"],
            estimates, reasons))
    return results


def save_replay(path: str | Path, results: list[InferenceResult]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(json.dumps(result.__dict__, sort_keys=True) for result in results) + "\n", encoding="utf-8")


def _filter(config: dict, dim: int, version: str) -> LocalTrendFilter:
    return LocalTrendFilter(dim, float(config.get("kalman_process_level", 0.02)),
                            float(config.get("kalman_process_velocity", 0.005)),
                            float(config.get("kalman_observation_variance", 0.15)),
                            float(config.get("long_gap_reset_days", 30)), version,
                            float(config.get("quality_r_inflation_max", 4.0)))
