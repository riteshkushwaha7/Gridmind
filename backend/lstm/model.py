"""LSTM load-forecast model.

2-layer LSTM with per-zone learned embeddings concatenated to each timestep.
Input  : numeric features (B, T, F) + zone_idx (B,) → effective input (B, T, F + E)
Output : (B, H) — H-step demand_kwh forecast.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from config import (
    LSTM_DROPOUT,
    LSTM_HIDDEN,
    LSTM_HORIZON,
    LSTM_LAYERS,
    LSTM_NUM_FEATURES,
    LSTM_ZONE_EMB_DIM,
    ZONES,
)

NUM_ZONES = len(ZONES)


class LoadForecastLSTM(nn.Module):
    def __init__(
        self,
        num_features: int = LSTM_NUM_FEATURES,
        zone_emb_dim: int = LSTM_ZONE_EMB_DIM,
        hidden: int = LSTM_HIDDEN,
        num_layers: int = LSTM_LAYERS,
        dropout: float = LSTM_DROPOUT,
        horizon: int = LSTM_HORIZON,
        num_zones: int = NUM_ZONES,
    ) -> None:
        super().__init__()
        self.zone_emb = nn.Embedding(num_zones, zone_emb_dim)
        self.lstm = nn.LSTM(
            input_size=num_features + zone_emb_dim,
            hidden_size=hidden,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden),
            nn.Dropout(dropout),
            nn.Linear(hidden, horizon),
        )

    def forward(self, x: torch.Tensor, zone_idx: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F)  zone_idx: (B,)
        B, T, _ = x.shape
        emb = self.zone_emb(zone_idx).unsqueeze(1).expand(B, T, -1)
        z = torch.cat([x, emb], dim=-1)
        out, _ = self.lstm(z)
        last = out[:, -1, :]
        return self.head(last)


def build_optimizer_scheduler(model: nn.Module, lr: float):
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(optim, mode="min", patience=3, factor=0.5)
    return optim, sched


def huber_loss() -> nn.Module:
    return nn.HuberLoss(delta=1.0)
