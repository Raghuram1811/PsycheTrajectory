from datetime import datetime, timedelta, timezone
import numpy as np
import pytest

from psychetrajectory.kalman import LocalTrendFilter
from psychetrajectory.heads import predict_symptom_heads, train_ridge_heads
from psychetrajectory.inference import infer_window
from psychetrajectory.encoder import direct_feature_baseline, fit_pca_baseline, pca_baseline
from psychetrajectory.diagnostics import innovation_diagnostics
from psychetrajectory.preprocessing import aggregate_daily, causal_impute
from psychetrajectory.pipeline import subject_split
from psychetrajectory.schema import Observation, SymptomLabel


def observation(subject="s1", signal="heart_rate", value=70, event=None, available=None, unit="bpm", quality="good"):
    event = event or datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    available = available or event
    return Observation(subject, event, available, "watch", "summary", signal, value, unit, {}, quality)


def test_availability_cutoff_and_delayed_sleep():
    event = datetime(2026, 1, 1, 20, tzinfo=timezone.utc)
    delayed = observation(signal="sleep_duration", value=7, unit="hours", event=event,
                          available=event + timedelta(days=1))
    early = aggregate_daily([delayed], event + timedelta(hours=3))
    assert early == []
    later = aggregate_daily([delayed], event + timedelta(days=1, hours=1))
    assert later[0].day_utc == "2026-01-02"
    assert later[0].values["sleep_hours"] == 7


def test_invalid_availability_order_is_rejected():
    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="cannot precede"):
        observation(event=start, available=start - timedelta(days=1))


def test_missing_modality_and_hrv_requires_beat_intervals():
    rows = [observation(signal="heart_rate", value=65), observation(signal="heart_rate", value=72,
             event=datetime(2026, 1, 1, 13, tzinfo=timezone.utc))]
    daily = aggregate_daily(rows, datetime(2026, 1, 2, tzinfo=timezone.utc))[0]
    assert daily.values["heart_rate_bpm"] == 68.5
    assert daily.values["hrv_rmssd_ms"] is None
    assert daily.observed["eda_us"] is False


def test_hrv_from_usable_beat_intervals_only():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [observation(signal="ibi", value=v, unit="ms", event=start + timedelta(seconds=i))
            for i, v in enumerate([800, 810, 790, 820])]
    result = aggregate_daily(rows, start + timedelta(days=1))[0]
    assert result.values["hrv_rmssd_ms"] == pytest.approx(np.sqrt((100 + 400 + 900) / 3))
    rejected = [observation(signal="ibi", value=800, unit="ms", event=start, quality="artifact")]
    assert aggregate_daily(rejected, start + timedelta(days=1))[0].values["hrv_rmssd_ms"] is None


def test_causal_imputation_is_bounded_and_per_subject():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = aggregate_daily([observation(value=70, event=start)], start + timedelta(days=1))
    from psychetrajectory.schema import DailyFeature
    rows += [DailyFeature("s1", "2026-01-02", {"heart_rate_bpm": None}, {"heart_rate_bpm": False}, 0.0),
             DailyFeature("s1", "2026-01-05", {"heart_rate_bpm": None}, {"heart_rate_bpm": False}, 0.0),
             DailyFeature("s2", "2026-01-02", {"heart_rate_bpm": None}, {"heart_rate_bpm": False}, 0.0)]
    result = causal_impute(rows, 1)
    lookup = {(r.subject_id, r.day_utc): r for r in result}
    assert lookup[("s1", "2026-01-02")].values["heart_rate_bpm"] == 70
    assert lookup[("s1", "2026-01-05")].values["heart_rate_bpm"] is None
    assert lookup[("s2", "2026-01-02")].values["heart_rate_bpm"] is None


def test_subject_disjoint_split():
    split = subject_split([f"s{i}" for i in range(20)], seed=2)
    groups = [set(split[key]) for key in ("train", "validation", "test")]
    assert not groups[0] & groups[1]
    assert not groups[0] & groups[2]
    assert not groups[1] & groups[2]


def test_filter_gap_covariance_symmetry_and_subject_isolation():
    core = LocalTrendFilter(2)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state, _ = core.step("s1", timestamp, np.array([1.0, -1.0]))
    before = np.trace(state.covariance)
    state, detail = core.step("s1", timestamp + timedelta(days=4), None, state)
    assert detail["prediction_only"]
    assert np.trace(state.covariance) > before
    assert np.allclose(state.covariance, state.covariance.T)
    with pytest.raises(ValueError, match="different subject"):
        core.step("s2", timestamp + timedelta(days=5), np.zeros(2), state)


def test_filter_recovers_known_linear_trend_and_rejects_version_mix():
    core = LocalTrendFilter(1, process_level=1e-4, process_velocity=1e-4,
                            observation_variance=0.02, artifact_version="encoder-a")
    state = None
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for day in range(35):
        state, _ = core.step("s1", start + timedelta(days=day), np.array([0.4 + 0.08 * day]), state)
    assert float(state.mean[1, 0]) == pytest.approx(0.08, abs=0.025)
    other = LocalTrendFilter(1, artifact_version="encoder-b")
    with pytest.raises(ValueError, match="version mismatch"):
        other.step("s1", start + timedelta(days=35), np.array([3.0]), state)


def test_duplicate_request_is_idempotent_and_order_is_checked():
    core = LocalTrendFilter(1)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state, _ = core.step("s", start, np.array([2.0]), request_id="one")
    same, detail = core.step("s", start + timedelta(days=1), np.array([99.0]), state, request_id="one")
    assert detail["idempotent"]
    assert same is state
    with pytest.raises(ValueError, match="out-of-order"):
        core.step("s", start, np.array([2.0]), state)


def test_long_gap_resets_filter():
    core = LocalTrendFilter(1, long_gap_reset_days=3)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state, _ = core.step("s", start, np.array([2.0]))
    state, detail = core.step("s", start + timedelta(days=4), None, state)
    assert detail["reset"] and detail["prediction_only"]


def test_independent_heads_use_one_latest_causal_row_and_keep_adhd_null():
    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    rows, labels = [], []
    for index in range(10):
        subject = f"p{index}"
        rows.extend([
            {"subject_id": subject, "timestamp": (start + timedelta(days=1)).isoformat(),
             "latent_level": [float(index), 1.0], "latent_velocity_per_day": [0.1, 0.0]},
            {"subject_id": subject, "timestamp": (start + timedelta(days=2)).isoformat(),
             "latent_level": [float(index + 1), 1.0], "latent_velocity_per_day": [0.1, 0.0]},
        ])
        labels.append(SymptomLabel(subject, "PHQ-9", "9", "depression_symptom", float(index), "adult", "18+",
                                   start + timedelta(days=3), 14, "synthetic plumbing fixture"))
        labels.append(SymptomLabel(subject, "GAD-7", "7", "anxiety_symptom", float(index) / 2, "adult", "18+",
                                   start + timedelta(days=3), 14, "synthetic plumbing fixture"))
        labels.append(SymptomLabel(subject, "ADHD-RS", "5", "adhd_symptom", float(index), "adult", "18+",
                                   start + timedelta(days=3), 30, "synthetic plumbing fixture"))
    artifact = train_ridge_heads(rows, labels, min_subjects=5)
    assert artifact["heads"]["depression_symptom"] is not None
    assert artifact["heads"]["anxiety_symptom"] is not None
    assert artifact["heads"]["adhd_symptom"] is None
    estimate = predict_symptom_heads(artifact, np.array([2.0, 1.0]), np.array([0.1, 0.0]))
    assert estimate["depression_symptom"]["interpretation"].endswith("not diagnosis")
    assert estimate["adhd_symptom"] is None


def test_unsupported_head_outputs_are_null():
    outputs = predict_symptom_heads({}, np.zeros(2), np.zeros(2))
    assert outputs == {"depression_symptom": None, "anxiety_symptom": None, "adhd_symptom": None}


def test_incremental_inference_matches_batch_filter_replay():
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    embeddings = [np.array([np.sin(day / 3), day / 10]) for day in range(8)]
    batch_core = LocalTrendFilter(2, artifact_version="fixed-encoder")
    incremental_core = LocalTrendFilter(2, artifact_version="fixed-encoder")
    batch_state, incremental_state = None, None
    for day, embedding in enumerate(embeddings):
        timestamp = start + timedelta(days=day)
        batch_state, _ = batch_core.step("s", timestamp, embedding, batch_state, request_id=str(day))
        event = observation(subject="s", event=timestamp, available=timestamp)
        incremental_state, result = infer_window("s", [event], timestamp, incremental_state,
                                                 incremental_core, embedding, request_id=str(day))
    assert np.allclose(batch_state.mean, incremental_state.mean)
    assert np.allclose(batch_state.covariance, incremental_state.covariance)
    assert result.symptom_estimates == {"depression_symptom": None, "anxiety_symptom": None, "adhd_symptom": None}


def test_sqlite_api_persists_subject_state_and_is_idempotent(tmp_path, monkeypatch):
    from psychetrajectory import api
    from fastapi import HTTPException

    monkeypatch.setattr(api, "STATE_DB", tmp_path / "state.sqlite3")
    first = api.infer(api.WindowRequest(subject_id="s1", timestamp="2026-01-01T00:00:00Z",
                                        embedding=[1.0, 2.0], request_id="day-1"))
    second = api.infer(api.WindowRequest(subject_id="s1", timestamp="2026-01-02T00:00:00Z",
                                         embedding=[9.0, 9.0], request_id="day-1"))
    assert second["timestamp"] == first["timestamp"]
    with pytest.raises(HTTPException) as other:
        api.infer(api.WindowRequest(subject_id="s2", timestamp="2026-01-02T00:00:00Z"))
    assert other.value.status_code == 422
    with pytest.raises(HTTPException) as mismatch:
        api.infer(api.WindowRequest(subject_id="s1", timestamp="2026-01-02T00:00:00Z",
                                    embedding=[1.0, 2.0], artifact_version="new-encoder"))
    assert mismatch.value.status_code == 409


def test_pca_and_direct_feature_baselines_keep_missingness_explicit():
    values = np.array([[1.0, 3.0, 2.0], [2.0, 4.0, 0.0], [3.0, 0.0, 6.0], [4.0, 5.0, 8.0]])
    mask = np.array([[1, 1, 1], [1, 1, 0], [1, 0, 1], [1, 1, 1]], dtype=bool)
    pca = fit_pca_baseline(values[:3], mask[:3], latent_dim=2)
    latent, diagnostic = pca_baseline(values[3:], mask[3:], pca)
    direct = direct_feature_baseline(values[3:], mask[3:], pca["mean"], pca["scale"])
    assert latent.shape == (1, 2)
    assert diagnostic.shape == (1,)
    assert direct.shape == (1, 6)
    assert direct[0, 5] == 1


def test_innovation_coverage_and_autocorrelation_diagnostics():
    rng = np.random.default_rng(31)
    residuals = rng.normal(size=(4000, 2))
    covariances = np.repeat(np.eye(2)[None, :, :], len(residuals), axis=0)
    report = innovation_diagnostics([(residuals, covariances)])
    assert report["innovations"] == 4000
    assert 0.93 < report["coverage_95"] < 0.97
    assert report["mean_abs_lag1_autocorrelation"] < 0.05
