from __future__ import annotations

from typing import Iterable
import numpy as np


def subject_split(subjects: Iterable[str], seed: int = 17) -> dict[str, list[str]]:
    unique = sorted(set(subjects))
    rng = np.random.default_rng(seed)
    rng.shuffle(unique)
    n = len(unique)
    train_end = max(1, int(n * 0.6))
    val_end = max(train_end + 1, int(n * 0.8)) if n >= 3 else train_end
    return {"train": unique[:train_end], "validation": unique[train_end:val_end], "test": unique[val_end:]}
