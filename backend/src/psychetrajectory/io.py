from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .schema import Observation, SymptomLabel, parse_utc


def read_observations(path: str | Path) -> list[Observation]:
    path = Path(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("Parquet support requires `pip install -e '.[parquet]'`") from exc
        rows = pq.read_table(path).to_pylist()
    else:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    observations = []
    for row in rows:
        observations.append(Observation(
            subject_id=str(row["subject_id"]), event_time_utc=parse_utc(row["event_time_utc"]),
            available_at_utc=parse_utc(row["available_at_utc"]), device=str(row.get("device", "unknown")),
            source=str(row.get("source", "unknown")), signal_name=str(row["signal_name"]),
            value=float(row["value"]), unit=str(row["unit"]),
            sampling_metadata=_json_field(row.get("sampling_metadata")), quality=str(row.get("quality") or "unknown"),
            context=_json_field(row.get("context")), schema_version=str(row.get("schema_version") or "observations-v1"),
        ))
    return observations


def write_observations(path: str | Path, observations: Iterable[Observation]) -> None:
    path = Path(path)
    rows = [item.as_dict() for item in observations]
    if path.suffix.lower() in {".parquet", ".pq"}:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("Parquet support requires `pip install -e '.[parquet]'`") from exc
        for row in rows:
            row["sampling_metadata"] = json.dumps(row["sampling_metadata"], sort_keys=True)
            row["context"] = json.dumps(row["context"], sort_keys=True)
        pq.write_table(pa.Table.from_pylist(rows), path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [
            "schema_version", "subject_id", "event_time_utc", "available_at_utc", "device", "source",
            "signal_name", "value", "unit", "sampling_metadata", "quality", "context",
        ])
        writer.writeheader()
        for row in rows:
            row["sampling_metadata"] = json.dumps(row["sampling_metadata"], sort_keys=True)
            row["context"] = json.dumps(row["context"], sort_keys=True)
            writer.writerow(row)


def read_labels(path: str | Path) -> list[SymptomLabel]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [SymptomLabel(
            subject_id=row["subject_id"], instrument=row["instrument"], instrument_version=row["instrument_version"],
            target=row["target"], score=float(row["score"]), population=row["population"],
            age_band=row.get("age_band") or None, assessment_time_utc=parse_utc(row["assessment_time_utc"]),
            recall_interval_days=int(row["recall_interval_days"]), provenance=row["provenance"],
        ) for row in rows]


def _json_field(value: object) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise ValueError("metadata fields must contain JSON objects")
    return parsed
