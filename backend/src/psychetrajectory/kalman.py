from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import numpy as np

from .schema import FilterState, parse_utc


class LocalTrendFilter:
    """Causal linear-Gaussian level/velocity filter; time units are days."""

    def __init__(self, dimension: int, process_level: float = 0.02, process_velocity: float = 0.005,
                 observation_variance: float = 0.15, long_gap_reset_days: float = 30.0,
                 artifact_version: str = "latent-v1", quality_r_inflation_max: float = 4.0):
        if dimension < 1 or min(process_level, process_velocity, observation_variance) <= 0 or quality_r_inflation_max < 1:
            raise ValueError("dimension and noise variances must be positive")
        self.dimension = dimension
        self.process_level = process_level
        self.process_velocity = process_velocity
        self.observation_variance = observation_variance
        self.long_gap_reset_days = long_gap_reset_days
        self.quality_r_inflation_max = quality_r_inflation_max
        self.artifact_version = artifact_version

    def initial_state(self, subject_id: str, timestamp: datetime | str, mean: np.ndarray | None = None,
                      covariance_scale: float = 10.0) -> FilterState:
        state_mean = np.zeros((2 * self.dimension, 1))
        if mean is not None:
            state_mean[:self.dimension, 0] = np.asarray(mean, dtype=float).reshape(self.dimension)
        covariance = np.eye(2 * self.dimension) * covariance_scale
        return FilterState(subject_id, state_mean, covariance, parse_utc(timestamp).isoformat(), self.artifact_version)

    def step(self, subject_id: str, timestamp: datetime | str, observation: np.ndarray | None,
             state: FilterState | None = None, quality: float = 1.0, request_id: str | None = None) -> tuple[FilterState, dict]:
        now = parse_utc(timestamp)
        if state is None:
            if observation is None:
                raise ValueError("a first filter step needs an observation")
            state = self.initial_state(subject_id, now, np.asarray(observation, dtype=float))
            state.last_request_id = request_id
            return state, {"prediction_only": False, "reset": False, "innovation": None}
        if state.subject_id != subject_id:
            raise ValueError("filter state belongs to a different subject")
        if state.artifact_version != self.artifact_version:
            raise ValueError("filter state artifact version mismatch")
        if request_id and request_id == state.last_request_id:
            return state, {"prediction_only": observation is None, "reset": False, "innovation": None, "idempotent": True}
        previous = parse_utc(state.timestamp)
        dt = (now - previous).total_seconds() / 86400
        if dt <= 0:
            raise ValueError("duplicate or out-of-order timestamps are rejected")
        if dt > self.long_gap_reset_days:
            fresh = self.initial_state(subject_id, now, observation, covariance_scale=10.0) if observation is not None else self.initial_state(subject_id, now)
            fresh.last_request_id = request_id
            return fresh, {"prediction_only": observation is None, "reset": True, "innovation": None}

        n = self.dimension
        identity = np.eye(n)
        transition = np.block([[identity, dt * identity], [np.zeros_like(identity), identity]])
        process = np.block([
            [self.process_level * dt * identity + self.process_velocity * (dt ** 3 / 3) * identity,
             self.process_velocity * (dt ** 2 / 2) * identity],
            [self.process_velocity * (dt ** 2 / 2) * identity, self.process_velocity * dt * identity],
        ])
        mean = transition @ np.asarray(state.mean, dtype=float)
        covariance = transition @ np.asarray(state.covariance, dtype=float) @ transition.T + process
        predicted_only = observation is None
        innovation = None
        if observation is not None:
            z = np.asarray(observation, dtype=float).reshape(n, 1)
            if not np.all(np.isfinite(z)):
                raise ValueError("observations must be finite")
            h = np.block([identity, np.zeros_like(identity)])
            bounded_quality = float(np.clip(quality, 0.05, 1.0))
            r = np.eye(n) * (self.observation_variance * min(self.quality_r_inflation_max, 1 / bounded_quality))
            residual = z - h @ mean
            innovation_cov = h @ covariance @ h.T + r
            gain = np.linalg.solve(innovation_cov.T, (covariance @ h.T).T).T
            mean = mean + gain @ residual
            left = np.eye(2 * n) - gain @ h
            covariance = left @ covariance @ left.T + gain @ r @ gain.T
            innovation = residual[:, 0].tolist()
        covariance = (covariance + covariance.T) * 0.5
        if np.linalg.eigvalsh(covariance).min() < -1e-8:
            covariance += np.eye(2 * n) * 1e-8
        next_state = FilterState(subject_id, mean, covariance, now.isoformat(), self.artifact_version, request_id)
        return next_state, {"prediction_only": predicted_only, "reset": False, "innovation": innovation,
                            "innovation_covariance": innovation_cov.tolist() if observation is not None else None}

    @staticmethod
    def state_dict(state: FilterState) -> dict:
        result = asdict(state)
        result["mean"] = np.asarray(state.mean).tolist()
        result["covariance"] = np.asarray(state.covariance).tolist()
        return result

    @staticmethod
    def from_dict(value: dict) -> FilterState:
        return FilterState(value["subject_id"], np.asarray(value["mean"], dtype=float),
                           np.asarray(value["covariance"], dtype=float), value["timestamp"],
                           value["artifact_version"], value.get("last_request_id"))
