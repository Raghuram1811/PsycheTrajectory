"""Optional FastAPI surface. Install with `pip install -e '.[api]'`."""

from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .kalman import LocalTrendFilter
from .schema import FilterState


app = FastAPI(title="PsycheTrajectory Research API", version="0.1.0")
STATE_DB = Path(os.environ.get("PSYCHETRAJECTORY_STATE_DB", "backend/artifacts/api-state.sqlite3"))


class WindowRequest(BaseModel):
    subject_id: str = Field(min_length=1)
    timestamp: datetime
    embedding: list[float] | None = None
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    request_id: str | None = None
    artifact_version: str = "demo-latent-v1"


@app.post("/v1/infer")
def infer(request: WindowRequest) -> dict[str, Any]:
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(STATE_DB, timeout=15, isolation_level="IMMEDIATE") as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS filter_states (subject_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT payload FROM filter_states WHERE subject_id = ?", (request.subject_id,)).fetchone()
        prior = FilterState(**json.loads(row[0])) if row else None
        if request.embedding is None and prior is None:
            raise HTTPException(422, "first request requires an embedding")
        dimension = len(request.embedding) if request.embedding is not None else len(prior.mean) // 2
        core = LocalTrendFilter(dimension, artifact_version=request.artifact_version)
        if prior is not None:
            prior.mean = np.asarray(prior.mean)
            prior.covariance = np.asarray(prior.covariance)
        try:
            updated, detail = core.step(request.subject_id, request.timestamp,
                                        None if request.embedding is None else np.asarray(request.embedding),
                                        prior, request.quality, request.request_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        payload = {"subject_id": updated.subject_id, "mean": np.asarray(updated.mean).tolist(),
                   "covariance": np.asarray(updated.covariance).tolist(), "timestamp": updated.timestamp,
                   "artifact_version": updated.artifact_version, "last_request_id": updated.last_request_id}
        connection.execute("INSERT INTO filter_states(subject_id, payload) VALUES (?, ?) ON CONFLICT(subject_id) DO UPDATE SET payload=excluded.payload",
                            (request.subject_id, json.dumps(payload)))
    mean = np.asarray(updated.mean)
    n = core.dimension
    return {"subject_id": request.subject_id, "timestamp": updated.timestamp, "mode": "exploratory",
            "artifact_version": updated.artifact_version, "latent_level": mean[:n, 0].tolist(),
            "latent_velocity_per_day": mean[n:, 0].tolist(), "covariance": np.asarray(updated.covariance).tolist(),
            "feature_coverage": request.quality, "quality_flags": [],
            "baseline_status": "not_supplied", "baseline_deviation": None,
            "stale": detail["prediction_only"], "prediction_only": detail["prediction_only"],
            "symptom_estimates": {"depression_symptom": None, "anxiety_symptom": None, "adhd_symptom": None},
            "abstention_reasons": ["baseline_not_supplied", "symptom_head_unavailable:depression_symptom",
                                   "symptom_head_unavailable:anxiety_symptom", "symptom_head_unavailable:adhd_symptom"]}
