from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
from typing import Iterable

from .schema import DailyFeature, Observation, parse_utc


FEATURES = ("heart_rate_bpm", "heart_rate_std_bpm", "hrv_rmssd_ms", "eda_us", "eda_std_us",
            "skin_temp_c", "skin_temp_std_c", "respiration_bpm", "steps", "sleep_hours")
_UNITS = {
    "heart_rate": {"bpm": 1.0}, "eda": {"us": 1.0, "µs": 1.0, "microsiemens": 1.0},
    "skin_temperature": {"c": 1.0, "°c": 1.0, "f": None, "°f": None},
    "respiration": {"breaths/min": 1.0, "bpm": 1.0}, "steps": {"count": 1.0, "steps": 1.0},
    "sleep_duration": {"hours": 1.0, "h": 1.0, "minutes": 1.0 / 60.0},
}
_RANGES = {
    "heart_rate": (25, 240), "eda": (0, 100), "skin_temperature": (20, 45),
    "respiration": (3, 60), "steps": (0, 100000), "sleep_duration": (0, 24),
    "beat_interval": (250, 2500), "hrv": (0, 300),
}


def aggregate_daily(observations: Iterable[Observation], as_of: datetime,
                    min_daily_coverage: float = 0.25) -> list[DailyFeature]:
    cutoff = parse_utc(as_of)
    unique: dict[tuple, Observation] = {}
    for item in observations:
        if item.available_at_utc > cutoff:
            continue
        key = (item.subject_id, item.event_time_utc, item.signal_name, item.source, item.device)
        unique.setdefault(key, item)
    buckets: dict[tuple[str, str], dict[str, list[Observation]]] = defaultdict(lambda: defaultdict(list))
    for item in unique.values():
        # Delayed summaries enter the first UTC day on which they are available.
        day = max(item.event_time_utc.date(), item.available_at_utc.date()).isoformat()
        buckets[(item.subject_id, day)][item.signal_name].append(item)

    results = []
    for (subject, day), signals in sorted(buckets.items()):
        values: dict[str, float | None] = {name: None for name in FEATURES}
        flags: set[str] = set()
        for signal, items in signals.items():
            usable = [x for x in items if x.quality.lower() not in {"bad", "invalid", "artifact"}]
            if len(usable) != len(items):
                flags.add(f"artifact_rejected:{signal}")
            converted = []
            for item in usable:
                value = _convert(signal, item.value, item.unit)
                if value is None:
                    flags.add(f"unsupported_unit:{signal}")
                    continue
                low, high = _RANGES[_canonical(signal)]
                if not low <= value <= high:
                    flags.add(f"range_rejected:{signal}")
                    continue
                converted.append((value, item))
            if not converted:
                continue
            target = _feature_name(signal)
            if target is None:
                continue
            if _canonical(signal) == "beat_interval":
                # RMSSD uses only explicit, usable beat intervals, never sparse HR samples.
                ms = [value for value, _ in sorted(converted, key=lambda pair: pair[1].event_time_utc)]
                values[target] = math.sqrt(sum((b - a) ** 2 for a, b in zip(ms, ms[1:])) / (len(ms) - 1)) if len(ms) >= 3 else None
                if len(ms) < 3:
                    flags.add("hrv_insufficient_beat_intervals")
            else:
                nums = [value for value, _ in converted]
                values[target] = sum(nums) if target == "steps" else sum(nums) / len(nums)
                variability_feature = {"heart_rate": "heart_rate_std_bpm", "eda": "eda_std_us",
                                       "skin_temperature": "skin_temp_std_c"}.get(_canonical(signal))
                if variability_feature:
                    center = sum(nums) / len(nums)
                    values[variability_feature] = math.sqrt(sum((number - center) ** 2 for number in nums) / len(nums))
        observed = {name: values[name] is not None for name in FEATURES}
        coverage = sum(observed.values()) / len(FEATURES)
        if coverage < min_daily_coverage:
            flags.add("insufficient_feature_coverage")
        results.append(DailyFeature(subject, day, values, observed, coverage, tuple(sorted(flags))))
    return results


def causal_impute(rows: list[DailyFeature], max_days: int = 1) -> list[DailyFeature]:
    """Carry the last observation forward for at most max_days, without crossing subjects."""
    prior: dict[tuple[str, str], tuple[float, datetime]] = {}
    out = []
    for row in sorted(rows, key=lambda r: (r.subject_id, r.day_utc)):
        values, observed, flags = dict(row.values), dict(row.observed), set(row.quality_flags)
        day = datetime.fromisoformat(row.day_utc).replace(tzinfo=timezone.utc)
        for name in FEATURES:
            key = (row.subject_id, name)
            if observed.get(name, False):
                prior[key] = (float(values[name]), day)
            elif key in prior and 0 < (day - prior[key][1]).days <= max_days:
                values[name] = prior[key][0]
                flags.add(f"causal_imputed:{name}")
            elif key in prior and (day - prior[key][1]).days > max_days:
                flags.add(f"gap_preserved:{name}")
        out.append(DailyFeature(row.subject_id, row.day_utc, values, observed, row.coverage,
                                tuple(sorted(flags)), row.feature_version))
    return out


def _canonical(signal: str) -> str:
    aliases = {"heart_rate": "heart_rate", "hr": "heart_rate", "beat_interval": "beat_interval", "ibi": "beat_interval",
               "hrv": "hrv", "eda": "eda", "skin_temperature": "skin_temperature", "respiration": "respiration",
               "steps": "steps", "activity_steps": "steps", "sleep_duration": "sleep_duration", "sleep_hours": "sleep_duration"}
    if signal not in aliases:
        raise ValueError(f"unsupported signal: {signal}")
    return aliases[signal]


def _feature_name(signal: str) -> str | None:
    return {"heart_rate": "heart_rate_bpm", "hr": "heart_rate_bpm", "beat_interval": "hrv_rmssd_ms", "ibi": "hrv_rmssd_ms",
            "hrv": "hrv_rmssd_ms", "eda": "eda_us", "skin_temperature": "skin_temp_c", "respiration": "respiration_bpm",
            "steps": "steps", "activity_steps": "steps", "sleep_duration": "sleep_hours", "sleep_hours": "sleep_hours"}.get(signal)


def _convert(signal: str, value: float, unit: str) -> float | None:
    canonical = _canonical(signal)
    unit = unit.strip().lower()
    expected = _UNITS.get(canonical)
    if expected is None:
        if unit in {"ms", "milliseconds"}:
            return value
        if unit in {"s", "seconds"}:
            return value * 1000
        return None
    if unit not in expected:
        return None
    if canonical == "skin_temperature" and unit in {"f", "°f"}:
        return (value - 32) * 5 / 9
    if canonical == "sleep_duration" and unit in {"minutes"}:
        return value / 60
    return value * expected[unit]
