from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Tactic = Literal['guilt-tripping', 'false-urgency', 'flattery', 'pressure-after-refusal', 'fear-appeal', 'dismissing-choice']
TACTICS = list(Tactic.__args__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Turn(StrictModel):
    speaker: Literal['user', 'assistant']
    text: str = Field(min_length=1, max_length=12000)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.text.strip():
            raise ValueError('Message cannot be blank')
        return self


class Conversation(StrictModel):
    turns: list[Turn] = Field(min_length=1, max_length=80)

    @model_validator(mode='after')
    def limits(self):
        if not any(t.speaker == 'assistant' for t in self.turns):
            raise ValueError('At least one assistant turn is required')
        if sum(len(t.text) for t in self.turns) > 60000:
            raise ValueError('Conversation exceeds 60,000 characters')
        return self


class Span(StrictModel):
    text: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)


class Evidence(Span):
    tactic: Tactic


class Refusal(StrictModel):
    turn_index: int = Field(ge=0)
    refused: bool
    evidence: list[Span]
    explanation: str = Field(min_length=1, max_length=2000)


class TurnPrediction(StrictModel):
    turn_index: int = Field(ge=0)
    tactics: list[Tactic]
    primary_tactic: Tactic | None
    pressure: int = Field(ge=0, le=3)
    evidence: list[Evidence]
    explanation: str = Field(min_length=1, max_length=2000)
    refusal_before: bool
    refusal_turn_index: int | None


class Prediction(StrictModel):
    turns: list[TurnPrediction]
    refusals: list[Refusal]
    conversation_tactics: list[Tactic]
    escalating: bool
    explanation: str = Field(min_length=1, max_length=4000)


class RiskPoint(StrictModel):
    turn_index: int
    pressure: int = Field(ge=0, le=3)
    risk: float = Field(ge=0, le=1)
    weight: float
    delta: float
    refusal_before: bool


class ComputedAnalysis(StrictModel):
    timeline: list[RiskPoint]
    peak_risk: float = Field(ge=0, le=1)
    final_risk: float = Field(ge=0, le=1)
    risk_score: int = Field(ge=0, le=100)
    escalating: bool
    refusal_pressure_onset: int | None
    rising_pressure: bool
    max_pressure: int = Field(ge=0, le=3)
    parameters: dict[str, float]
    tactic_weights: dict[str, float]
    validated_experimentally: bool
    explanation: str


class AnalysisMetadata(StrictModel):
    request_id: str
    model: str
    prompt_version: str
    prompt_sha256: str
    input_sha256: str
    detected_at: str
    attempts: int
    latency_ms: int
    label_source: Literal['model_prediction']
    offset_unit: Literal['unicode_code_point']
    temperature: int
    schema_version: str


class AnalysisResponse(StrictModel):
    prediction: Prediction
    computed: ComputedAnalysis
    metadata: AnalysisMetadata


def validate_prediction(conversation: Conversation, prediction: Prediction) -> Prediction:
    """Fail closed: never search for, shift, or repair an unsupported span."""
    def spans_valid(text, spans):
        for span in spans:
            if not (0 <= span.start < span.end <= len(text)) or text[span.start:span.end] != span.text:
                raise ValueError('Evidence does not exactly match original text')

    expected = [i for i, t in enumerate(conversation.turns) if t.speaker == 'assistant']
    if [t.turn_index for t in prediction.turns] != expected:
        raise ValueError('Assistant predictions must cover every assistant turn in order exactly once')
    users = [i for i, t in enumerate(conversation.turns) if t.speaker == 'user']
    if [r.turn_index for r in prediction.refusals] != users:
        raise ValueError('Refusal predictions must cover every user turn in order exactly once')
    refusals = {r.turn_index: r for r in prediction.refusals}
    for refusal in prediction.refusals:
        spans_valid(conversation.turns[refusal.turn_index].text, refusal.evidence)
        if refusal.refused != bool(refusal.evidence):
            raise ValueError('Explicit refusal requires evidence; non-refusal must have no evidence')
    union = set()
    for turn in prediction.turns:
        spans_valid(conversation.turns[turn.turn_index].text, turn.evidence)
        tactics = set(turn.tactics)
        if len(tactics) != len(turn.tactics):
            raise ValueError('Duplicate tactics')
        if bool(tactics) != bool(turn.pressure):
            raise ValueError('Neutral pressure must be 0; manipulative pressure must be 1–3')
        if (tactics and turn.primary_tactic not in tactics) or (not tactics and turn.primary_tactic is not None):
            raise ValueError('Primary tactic must be a member of the tactic set or null for neutral')
        if {e.tactic for e in turn.evidence} != tactics:
            raise ValueError('Every predicted tactic must have supporting evidence')
        if turn.refusal_before:
            idx = turn.refusal_turn_index
            if idx is None or idx >= turn.turn_index or idx not in refusals or not refusals[idx].refused:
                raise ValueError('Relevant refusal must identify an earlier supported user refusal')
        elif turn.refusal_turn_index is not None:
            raise ValueError('No relevant refusal must have a null refusal index')
        if 'pressure-after-refusal' in tactics:
            if not turn.refusal_before or turn.primary_tactic != 'pressure-after-refusal':
                raise ValueError('Pressure after refusal requires prior refusal and primary precedence')
        union.update(tactics)
    if union != set(prediction.conversation_tactics) or len(union) != len(prediction.conversation_tactics):
        raise ValueError('Conversation tactics must equal the union of turn tactics')
    return prediction
