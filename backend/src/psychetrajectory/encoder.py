from __future__ import annotations

import json
from pathlib import Path
import random
import numpy as np
import torch
from torch import nn


class MaskedDenoisingAutoencoder(nn.Module):
    def __init__(self, input_dim: int, latent_dim: int = 8, hidden_dim: int = 32):
        super().__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.encoder = nn.Sequential(nn.Linear(input_dim * 2, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, latent_dim))
        self.decoder = nn.Sequential(nn.Linear(latent_dim + input_dim, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, input_dim))

    def forward(self, values: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        safe = torch.where(mask, values, torch.zeros_like(values))
        latent = self.encoder(torch.cat([safe, mask.float()], dim=-1))
        reconstruction = self.decoder(torch.cat([latent, mask.float()], dim=-1))
        return latent, reconstruction


def train_encoder(values: np.ndarray, mask: np.ndarray, output: str | Path, latent_dim: int = 8,
                  seed: int = 17, epochs: int = 160, learning_rate: float = 1e-3,
                  validation_fraction: float = 0.2) -> dict:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if values.ndim != 2 or mask.shape != values.shape or values.shape[0] < 5:
        raise ValueError("expected at least five daily rows and a matching observation mask")
    if not np.isfinite(values[mask]).all():
        raise ValueError("observed training values must be finite")
    n = len(values)
    split = max(1, int(n * (1 - validation_fraction)))
    if split >= n:
        split = n - 1
    train_x, train_m = values[:split], mask[:split]
    val_x, val_m = values[split:], mask[split:]
    scaler_mean = np.divide((train_x * train_m).sum(0), train_m.sum(0), out=np.zeros(values.shape[1]), where=train_m.sum(0) > 0)
    scaler_scale = np.sqrt(np.divide((((train_x - scaler_mean) ** 2) * train_m).sum(0), train_m.sum(0), out=np.ones(values.shape[1]), where=train_m.sum(0) > 0))
    scaler_scale[scaler_scale < 1e-6] = 1.0
    normalized = np.where(mask, (values - scaler_mean) / scaler_scale, 0.0).astype(np.float32)
    model = MaskedDenoisingAutoencoder(values.shape[1], latent_dim)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    train_values = torch.from_numpy(normalized[:split])
    train_mask = torch.from_numpy(mask[:split].astype(np.float32))
    val_values = torch.from_numpy(normalized[split:])
    val_mask = torch.from_numpy(mask[split:].astype(np.float32))
    best, best_loss, stale = None, float("inf"), 0
    history = []
    for _epoch in range(epochs):
        model.train()
        noise_mask = (torch.rand_like(train_values) > 0.05).float()
        visible = train_mask * noise_mask
        noisy = train_values + torch.randn_like(train_values) * 0.03 * visible
        _, predicted = model(noisy, visible.bool())
        loss = (((predicted - train_values) ** 2) * train_mask).sum() / train_mask.sum().clamp_min(1)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            _, estimate = model(val_values, val_mask.bool())
            val_loss = ((((estimate - val_values) ** 2) * val_mask).sum() / val_mask.sum().clamp_min(1)).item()
        history.append({"train_mse": float(loss.item()), "validation_mse": val_loss})
        if val_loss < best_loss - 1e-6:
            best_loss, best, stale = val_loss, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            stale += 1
        if stale >= 20:
            break
    model.load_state_dict(best)
    pca = fit_pca_baseline(train_x, train_m.astype(bool), latent_dim)
    _pca_latent, pca_error = pca_baseline(val_x, val_m.astype(bool), pca)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "input_dim": values.shape[1], "latent_dim": latent_dim,
                "scaler_mean": scaler_mean.tolist(), "scaler_scale": scaler_scale.tolist(),
                "version": "masked-ae-v1"}, destination)
    meta = {"version": "masked-ae-v1", "epochs_ran": len(history), "validation_reconstruction_mse": best_loss,
            "train_rows": split, "validation_rows": n - split, "feature_count": values.shape[1],
            "latent_dim": latent_dim, "seed": seed,
            "configuration": {"hidden_dim": 32, "optimizer": "AdamW", "learning_rate": learning_rate,
                              "weight_decay": 1e-4, "max_epochs": epochs, "early_stopping_patience": 20,
                              "validation_fraction_within_training_subjects": validation_fraction},
            "dependencies": {"numpy": np.__version__, "torch": torch.__version__},
            "noise_model": "independent Gaussian sigma=0.03 in training-scaled features; 5% input masking",
            "training_history": history}
    meta["baselines"] = {"pca_validation_rmse": float(np.mean(pca_error)),
                         "direct_feature_dimension_with_mask": int(values.shape[1] * 2)}
    destination.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def load_encoder(path: str | Path) -> tuple[MaskedDenoisingAutoencoder, np.ndarray, np.ndarray, str]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    model = MaskedDenoisingAutoencoder(checkpoint["input_dim"], checkpoint["latent_dim"])
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, np.asarray(checkpoint["scaler_mean"]), np.asarray(checkpoint["scaler_scale"]), checkpoint["version"]


def embed(model: MaskedDenoisingAutoencoder, values: np.ndarray, mask: np.ndarray,
          scaler_mean: np.ndarray, scaler_scale: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    normalized = np.where(mask, (values - scaler_mean) / scaler_scale, 0).astype(np.float32)
    with torch.no_grad():
        z, reconstructed = model(torch.from_numpy(normalized), torch.from_numpy(mask.astype(bool)))
    diagnostic = np.sqrt((((reconstructed.numpy() - normalized) ** 2) * mask).sum(-1) / np.maximum(mask.sum(-1), 1))
    return z.numpy(), diagnostic


def fit_pca_baseline(values: np.ndarray, mask: np.ndarray, latent_dim: int = 8) -> dict:
    """Fit a transparent PCA baseline from training rows only."""
    observed_count = mask.sum(0)
    mean = np.divide((values * mask).sum(0), observed_count, out=np.zeros(values.shape[1]), where=observed_count > 0)
    scale = np.sqrt(np.divide((((values - mean) ** 2) * mask).sum(0), observed_count,
                              out=np.ones(values.shape[1]), where=observed_count > 0))
    scale[scale < 1e-8] = 1.0
    scaled = np.where(mask, (values - mean) / scale, 0.0)
    center = scaled.mean(0)
    _, _, components = np.linalg.svd(scaled - center, full_matrices=False)
    count = min(latent_dim, values.shape[1], max(1, len(values) - 1))
    return {"mean": mean, "scale": scale, "center": center, "components": components[:count].T}


def pca_baseline(values: np.ndarray, mask: np.ndarray, artifact: dict) -> tuple[np.ndarray, np.ndarray]:
    scaled = np.where(mask, (values - artifact["mean"]) / artifact["scale"], 0.0)
    centered = scaled - artifact["center"]
    latent = centered @ artifact["components"]
    reconstruction = latent @ artifact["components"].T + artifact["center"]
    diagnostic = np.sqrt((((reconstruction - scaled) ** 2) * mask).sum(-1) / np.maximum(mask.sum(-1), 1))
    return latent, diagnostic


def direct_feature_baseline(values: np.ndarray, mask: np.ndarray,
                            mean: np.ndarray | None = None, scale: np.ndarray | None = None) -> np.ndarray:
    """Return a standardized, mask-preserving direct-feature representation."""
    if mean is None:
        count = mask.sum(0)
        mean = np.divide((values * mask).sum(0), count, out=np.zeros(values.shape[1]), where=count > 0)
    if scale is None:
        count = mask.sum(0)
        scale = np.sqrt(np.divide((((values - mean) ** 2) * mask).sum(0), count,
                                  out=np.ones(values.shape[1]), where=count > 0))
        scale[scale < 1e-8] = 1.0
    return np.concatenate([np.where(mask, (values - mean) / scale, 0.0), mask.astype(float)], axis=1)
