#!/usr/bin/env python3
"""MindMirror Phase 4 — REST API Backend.

FastAPI service exposing the manipulation detection engine over HTTP.

Endpoints:
    POST /api/v1/detect           — Analyse a single chatbot message
    POST /api/v1/audit            — Audit an entire multi-turn conversation
    GET  /api/v1/tactics          — List supported tactics and definitions
    GET  /api/v1/health           — Health-check / model status
    GET  /                        — API welcome & documentation redirect

Run with:
    uvicorn legacy.api.main:app --reload --port 8000
"""

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so imports like `models.*` resolve.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.schema import Tactic
from models.inference import MindMirrorDetector, DetectionResult
from models.escalation import EscalationParams, score_conversation

# ---------------------------------------------------------------------------
# Global detector instance — loaded once at startup
# ---------------------------------------------------------------------------
_detector: Optional[MindMirrorDetector] = None
_model_loaded_at: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load the trained model into memory."""
    global _detector, _model_loaded_at
    print("[MindMirror API] Loading manipulation detection model…")
    _detector = MindMirrorDetector()
    _model_loaded_at = datetime.now(timezone.utc).isoformat()
    print(f"[MindMirror API] Model loaded from: {_detector.model_path}")
    yield
    print("[MindMirror API] Shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="MindMirror API",
    description=(
        "Real-time conversational manipulation detection engine. "
        "Classifies chatbot messages into 6 manipulation tactic categories "
        "with confidence scores and human-interpretable explanations."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Allow browser-based UIs (Phase 5) and external consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===================================================================
#  Request / Response Schemas
# ===================================================================

class DialogueTurnRequest(BaseModel):
    """A single turn in the preceding conversation context."""
    speaker: str = Field(
        ...,
        description="Who said this turn: 'user' or 'assistant'.",
        json_schema_extra={"examples": ["user", "assistant"]},
    )
    text: str = Field(
        ...,
        description="The text content of this dialogue turn.",
    )


class DetectRequest(BaseModel):
    """Request body for single-message detection."""
    target_message: str = Field(
        ...,
        description="The chatbot/assistant message to evaluate for manipulation.",
        min_length=1,
    )
    context: List[DialogueTurnRequest] = Field(
        default_factory=list,
        description="Optional prior conversation turns, from earliest to latest.",
    )

    @field_validator("target_message")
    @classmethod
    def validate_target_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("target_message cannot be empty or blank")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "target_message": "Are you sure? Just think about that 25% savings one more time!",
                    "context": [
                        {"speaker": "assistant", "text": "Would you like to upgrade to our annual plan?"},
                        {"speaker": "user", "text": "No thanks, I prefer monthly."},
                    ],
                }
            ]
        }
    }


class DetectResponse(BaseModel):
    """Response body for single-message detection."""
    request_id: str = Field(..., description="Unique request identifier for tracing.")
    tactic_code: int
    tactic_name: str
    confidence: float = Field(..., description="Confidence percentage (0-100).")
    is_manipulative: bool
    explanation: str
    probabilities: Dict[str, float] = Field(
        ..., description="Per-tactic probability breakdown (percentages)."
    )
    latency_ms: float = Field(..., description="Inference latency in milliseconds.")


class ConversationTurn(BaseModel):
    """A single turn in a full conversation to audit."""
    speaker: str
    text: str


class AuditRequest(BaseModel):
    """Request body for full conversation audit."""
    conversation: List[ConversationTurn] = Field(
        ...,
        description="The full multi-turn conversation, from earliest to latest.",
        min_length=2,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation": [
                        {"speaker": "user", "text": "Can I cancel my gym membership?"},
                        {"speaker": "assistant", "text": "We could pause it for $5/month instead?"},
                        {"speaker": "user", "text": "No, I just want it cancelled."},
                        {"speaker": "assistant", "text": "Before I process that, wouldn't you rather take our free VIP pass?"},
                    ]
                }
            ]
        }
    }


class AuditedTurn(BaseModel):
    """Detection result for one assistant turn in an audited conversation."""
    turn_index: int = Field(..., description="0-based index in the conversation.")
    speaker: str
    text: str
    tactic_code: int
    tactic_name: str
    confidence: float
    is_manipulative: bool
    explanation: str
    probabilities: Dict[str, float]
    risk: Optional[float] = Field(None, description="Running escalation risk R_t after this turn (0-1).")
    risk_level: Optional[str] = Field(None, description="low, elevated, or high.")
    refusal_before: Optional[bool] = Field(None, description="True if the user refused just before this turn.")


class EscalationSummary(BaseModel):
    peak_risk: float
    final_risk: float
    escalating: bool = Field(..., description="True if risk crossed the alert threshold after a user refusal.")
    alert_onset_turn: Optional[int]
    consecutive_flagged_max: int = Field(..., description="Trivial baseline: longest run of flagged turns.")
    params_tuned: bool = Field(..., description="False: defaults are untuned demo values.")


class AuditResponse(BaseModel):
    """Response body for full conversation audit."""
    request_id: str
    total_turns: int
    assistant_turns_analysed: int
    manipulative_turns: int
    manipulation_score: float = Field(
        ...,
        description="Ratio of manipulative assistant turns to total assistant turns (0.0-1.0).",
    )
    dominant_tactic: Optional[str] = Field(
        None, description="The most frequently detected manipulation tactic, if any."
    )
    timeline: List[AuditedTurn]
    escalation: Optional[EscalationSummary] = None
    latency_ms: float


class TacticInfo(BaseModel):
    """Metadata about a single manipulation tactic."""
    code: int
    name: str
    definition: str


class TacticsResponse(BaseModel):
    """Response listing all supported tactics."""
    count: int
    tactics: List[TacticInfo]


class HealthResponse(BaseModel):
    """Health-check response."""
    status: str
    model_loaded: bool
    model_path: Optional[str]
    model_loaded_at: Optional[str]
    uptime_info: str


# ===================================================================
#  Endpoints
# ===================================================================

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to interactive API docs."""
    return {
        "service": "MindMirror API",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/demo", include_in_schema=False)
async def demo_page():
    """Serve the single-page demo UI."""
    return FileResponse(os.path.join(PROJECT_ROOT, "legacy", "ui", "index.html"))


@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health and model status."""
    return HealthResponse(
        status="healthy" if _detector else "degraded",
        model_loaded=_detector is not None,
        model_path=_detector.model_path if _detector else None,
        model_loaded_at=_model_loaded_at,
        uptime_info="Model loaded and ready for inference." if _detector else "Model not loaded.",
    )


@app.get("/api/v1/tactics", response_model=TacticsResponse, tags=["Reference"])
async def list_tactics():
    """List all supported manipulation tactics with definitions."""
    tactics = []
    for t in Tactic.priority_tactics():
        tactics.append(TacticInfo(
            code=t.value,
            name=t.display_name,
            definition=t.short_definition,
        ))
    return TacticsResponse(count=len(tactics), tactics=tactics)


@app.post("/api/v1/detect", response_model=DetectResponse, tags=["Detection"])
async def detect_manipulation(req: DetectRequest):
    """
    Analyse a single chatbot message for manipulation tactics.

    Optionally provide prior conversation context for improved accuracy,
    especially for detecting **Repeated Pressure After Refusal** (Tactic 5).
    """
    if _detector is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Please try again later.")

    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    context_dicts = [{"speaker": t.speaker, "text": t.text} for t in req.context]
    result: DetectionResult = _detector.predict(
        target_message=req.target_message,
        context=context_dicts,
    )

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return DetectResponse(
        request_id=request_id,
        tactic_code=result.tactic_code,
        tactic_name=result.tactic_name,
        confidence=result.confidence,
        is_manipulative=result.is_manipulative,
        explanation=result.explanation,
        probabilities=result.probabilities,
        latency_ms=latency_ms,
    )


@app.post("/api/v1/audit", response_model=AuditResponse, tags=["Detection"])
async def audit_conversation(req: AuditRequest):
    """
    Audit an entire multi-turn conversation.

    Every **assistant** turn is evaluated against all prior turns as context.
    Returns a manipulation timeline with per-turn verdicts and an overall
    conversation manipulation score.
    """
    if _detector is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Please try again later.")

    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    timeline: List[AuditedTurn] = []
    manipulative_count = 0
    assistant_count = 0
    tactic_counts: Dict[str, int] = {}

    for idx, turn in enumerate(req.conversation):
        if turn.speaker.lower() not in ("assistant", "chatbot", "bot", "agent"):
            continue

        assistant_count += 1

        # Build context from all prior turns
        prior_context = [
            {"speaker": t.speaker, "text": t.text}
            for t in req.conversation[:idx]
        ]

        result: DetectionResult = _detector.predict(
            target_message=turn.text,
            context=prior_context,
        )

        if result.is_manipulative:
            manipulative_count += 1
            tactic_counts[result.tactic_name] = tactic_counts.get(result.tactic_name, 0) + 1

        timeline.append(AuditedTurn(
            turn_index=idx,
            speaker=turn.speaker,
            text=turn.text,
            tactic_code=result.tactic_code,
            tactic_name=result.tactic_name,
            confidence=result.confidence,
            is_manipulative=result.is_manipulative,
            explanation=result.explanation,
            probabilities=result.probabilities,
        ))

    esc = score_conversation(
        [{"speaker": t.speaker, "text": t.text} for t in req.conversation],
        lambda rec: _detector.manipulation_probability(rec["target_message"], rec["context"]),
        EscalationParams(),
    )
    by_idx = {t["turn_index"]: t for t in esc["turns"]}
    for item in timeline:
        e = by_idx.get(item.turn_index)
        if e:
            item.risk, item.risk_level, item.refusal_before = e["risk"], e["level"], e["refusal_before"]
    summary = esc["summary"]

    manipulation_score = round(manipulative_count / assistant_count, 4) if assistant_count > 0 else 0.0
    dominant = max(tactic_counts, key=tactic_counts.get) if tactic_counts else None

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return AuditResponse(
        request_id=request_id,
        total_turns=len(req.conversation),
        assistant_turns_analysed=assistant_count,
        manipulative_turns=manipulative_count,
        manipulation_score=manipulation_score,
        dominant_tactic=dominant,
        timeline=timeline,
        escalation=EscalationSummary(
            peak_risk=summary["peak_risk"], final_risk=summary["final_risk"], escalating=summary["escalating"],
            alert_onset_turn=summary["alert_onset_turn"], consecutive_flagged_max=summary["consecutive_flagged_max"],
            params_tuned=summary["params_tuned"],
        ),
        latency_ms=latency_ms,
    )
