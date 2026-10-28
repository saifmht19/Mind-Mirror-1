"""Estimator adapter interfaces. Implementations are intentionally absent here."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence
from .data import PreparedExample


@dataclass(frozen=True)
class ModelRequest:
    family: str
    context_window: int
    refusal_conditioned: bool = False

    def __post_init__(self) -> None:
        allowed = {"tfidf", "deberta_single_turn", "deberta_context", "refusal_conditioned", "escalation_scorer"}
        if self.family not in allowed:
            raise ValueError(f"family must be one of {sorted(allowed)}")
        if self.family == "deberta_single_turn" and self.context_window != 0:
            raise ValueError("single-turn DeBERTa requires context_window=0")
        if self.family == "deberta_context" and self.context_window == 0:
            raise ValueError("context-aware DeBERTa requires a positive context window")


class MultiLabelPredictor(Protocol):
    """Common inference boundary for a future fitted adapter."""
    def predict_proba(self, examples: Sequence[PreparedExample]) -> list[list[float]]: ...


class TfidfAdapter(MultiLabelPredictor, Protocol):
    """Sparse text baseline interface; no vectorizer or classifier is fit here."""


class DebertaSingleTurnAdapter(MultiLabelPredictor, Protocol):
    """Single assistant-turn transformer interface; no model is loaded here."""


class DebertaContextAdapter(MultiLabelPredictor, Protocol):
    """Context-window transformer interface; no model is loaded here."""


class RefusalConditionedAdapter(MultiLabelPredictor, Protocol):
    """Predictor that consumes annotated/verified refusal markers as context."""


class EscalationScorer(Protocol):
    """Separate conversation-level scorer interface; does not redefine escalation."""
    def score(self, examples: Sequence[PreparedExample]) -> list[float]: ...
