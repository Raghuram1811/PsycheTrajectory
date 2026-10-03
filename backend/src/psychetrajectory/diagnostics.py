from __future__ import annotations

import numpy as np

_CHI_SQUARE_95 = (0.0, 3.841459, 5.991465, 7.814728, 9.487729, 11.070498,
                  12.591587, 14.067140, 15.507313, 16.918978, 18.307038,
                  19.675138, 21.026070, 22.362032, 23.684791, 24.995790,
                  26.296228)


def innovation_diagnostics(sequences: list[tuple[np.ndarray, np.ndarray]]) -> dict:
    """Summarize normalized innovation coverage and within-sequence lag-1 correlation."""
    mahalanobis, autocorrelations, residual_squares = [], [], []
    dimension = 0
    for residuals, covariances in sequences:
        residuals = np.asarray(residuals, dtype=float)
        covariances = np.asarray(covariances, dtype=float)
        if residuals.size == 0:
            continue
        dimension = residuals.shape[1]
        for residual, covariance in zip(residuals, covariances):
            mahalanobis.append(float(residual @ np.linalg.solve(covariance, residual)))
            residual_squares.append(float(residual @ residual))
        for coordinate in range(dimension):
            values = residuals[:, coordinate]
            if len(values) > 2 and np.std(values[:-1]) > 1e-10 and np.std(values[1:]) > 1e-10:
                autocorrelations.append(float(np.corrcoef(values[:-1], values[1:])[0, 1]))
    if not mahalanobis:
        return {"innovations": 0, "coverage_95": None, "mean_mahalanobis": None,
                "mean_abs_lag1_autocorrelation": None, "innovation_rmse": None}
    if dimension < len(_CHI_SQUARE_95):
        threshold = _CHI_SQUARE_95[dimension]
    else:
        z95 = 1.959963984540054
        threshold = dimension * (1 - 2 / (9 * dimension) + z95 * np.sqrt(2 / (9 * dimension))) ** 3
    return {"innovations": len(mahalanobis),
            "coverage_95": float(np.mean(np.asarray(mahalanobis) <= threshold)),
            "chi_square_95_threshold": float(threshold),
            "mean_mahalanobis": float(np.mean(mahalanobis)),
            "mean_abs_lag1_autocorrelation": float(np.mean(np.abs(autocorrelations))) if autocorrelations else None,
            "innovation_rmse": float(np.sqrt(np.mean(residual_squares)))}
