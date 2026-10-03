from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np

from .schema import Observation


def generate_observations(subjects: int = 8, days: int = 40, seed: int = 17) -> list[Observation]:
    """Simulated physiology patterns for software plumbing only; they are not diagnoses."""
    rng = np.random.default_rng(seed)
    origin = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    channels = [("heart_rate", "bpm"), ("eda", "us"), ("skin_temperature", "c"),
                ("respiration", "breaths/min"), ("steps", "count"), ("sleep_duration", "hours")]
    result = []
    for person in range(subjects):
        offset = rng.normal(0, 1.0)
        for day in range(days):
            gradual = max(0.0, day - days * 0.55) / days
            timestamp = origin + timedelta(days=day)
            for channel, unit in channels:
                if rng.random() < (0.12 + (0.22 if person == 0 and 23 <= day <= 28 else 0)):
                    continue
                nuisance = 3.0 if (channel == "heart_rate" and day in {8, 9}) else 0.0
                centers = {"heart_rate": 66 + offset * 2 + gradual * 9 + nuisance,
                           "eda": 4.0 + offset * 0.2 + gradual * 0.9,
                           "skin_temperature": 33.0 + offset * 0.1,
                           "respiration": 14 + offset * 0.3 + gradual * 1.5,
                           "steps": 6500 - gradual * 900, "sleep_duration": 7.2 - gradual * 0.6}
                scale = {"heart_rate": 4, "eda": 1.2, "skin_temperature": 0.4,
                         "respiration": 1.5, "steps": 1400, "sleep_duration": 0.7}[channel]
                value = max(0, rng.normal(centers[channel], scale))
                quality = "artifact" if rng.random() < 0.015 else "good"
                available = timestamp + (timedelta(days=1) if channel == "sleep_duration" else timedelta())
                result.append(Observation(f"sim-{person + 1:03d}", timestamp, available, "sim-watch-v1",
                                          "simulated_daily_summary", channel, float(value), unit,
                                          {"period": "daily"}, quality, {"simulated": True}))
    return result
