from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from typing import Any


def parse_utc(value: str | datetime) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Observation:
    subject_id: str
    event_time_utc: datetime
    available_at_utc: datetime
    device: str
    source: str
    signal_name: str
    value: float
    unit: str
    sampling_metadata: dict[str, Any] = field(default_factory=dict)
    quality: str = "unknown"
    context: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "observations-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_time_utc", parse_utc(self.event_time_utc))
        object.__setattr__(self, "available_at_utc", parse_utc(self.available_at_utc))
        if not self.subject_id or not self.signal_name:
            raise ValueError("subject_id and signal_name are required")
        if self.available_at_utc < self.event_time_utc:
            raise ValueError("available_at_utc cannot precede event_time_utc")
        if not math.isfinite(self.value):
            raise ValueError("observation value must be finite")

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["event_time_utc"] = self.event_time_utc.isoformat().replace("+00:00", "Z")
        result["available_at_utc"] = self.available_at_utc.isoformat().replace("+00:00", "Z")
        return result


@dataclass(frozen=True)
class DailyFeature:
    subject_id: str
    day_utc: str
    values: dict[str, float | None]
    observed: dict[str, bool]
    coverage: float
    quality_flags: tuple[str, ...] = ()
    feature_version: str = "daily-v1"


@dataclass
class FilterState:
    subject_id: str
    mean: Any
    covariance: Any
    timestamp: str
    artifact_version: str
    last_request_id: str | None = None


@dataclass(frozen=True)
class SymptomLabel:
    subject_id: str
    instrument: str
    instrument_version: str
    target: str
    score: float
    population: str
    age_band: str | None
    assessment_time_utc: datetime
    recall_interval_days: int
    provenance: str
    schema_version: str = "labels-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_time_utc", parse_utc(self.assessment_time_utc))
        if not self.subject_id or not self.instrument or not self.target or not self.provenance:
            raise ValueError("label subject, instrument, target, and provenance are required")
        if self.recall_interval_days < 1 or not math.isfinite(self.score):
            raise ValueError("labels require a positive recall interval and finite score")


@dataclass
class InferenceResult:
    subject_id: str
    timestamp: str
    mode: str
    artifact_version: str
    feature_coverage: float
    quality_flags: list[str]
    baseline_status: str
    baseline_deviation: list[float] | None
    latent_level: list[float] | None
    latent_velocity_per_day: list[float] | None
    covariance: list[list[float]] | None
    stale: bool
    prediction_only: bool
    symptom_estimates: dict[str, dict[str, Any] | None]
    abstention_reasons: list[str]
