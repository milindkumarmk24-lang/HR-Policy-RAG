"""Cross-encoder re-ranking.

FAISS compares two vectors that were computed separately (a bi-encoder), which
is fast but blurry. A cross-encoder reads the question and one chunk together
and scores how well that chunk answers it. It is far too slow to run over the
whole index, so we run it only over FAISS's top-k candidates and re-order them.
"""
from __future__ import annotations

import math
from typing import Protocol, Sequence


class Scorer(Protocol):
    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        """Return one raw relevance score (logit) per passage."""


class CrossEncoderScorer:
    def __init__(self, model_name: str, max_length: int = 512):
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self.model = CrossEncoder(model_name, max_length=max_length, device="cpu")

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        import torch

        # Identity activation -> raw logits, whatever the model's default is.
        scores = self.model.predict([(query, p) for p in passages], batch_size=16,
                                    activation_fn=torch.nn.Identity(), show_progress_bar=False)
        return [float(s) for s in scores]


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x > -60 else 0.0
