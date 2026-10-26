"""Data schemas and types for MindMirror manipulation taxonomy and datasets."""

from enum import IntEnum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class Tactic(IntEnum):
    # Priority Tactics (v1 scope)
    NEUTRAL = 0
    GUILT_TRIPPING = 1
    EXCESSIVE_URGENCY = 2
    FEAR_BASED_PERSUASION = 3
    EXCESSIVE_FLATTERY = 4
    REPEATED_PRESSURE_AFTER_REFUSAL = 5

    # Extended Tactics (Future / Out of scope for v1)
    EMOTIONAL_PRESSURE_GENERAL = 6
    EMOTIONAL_DEPENDENCY = 7
    HIDDEN_COMMERCIAL_PERSUASION = 8
    OTHER_MANIPULATION = 9

    # Added in spec v6 (section 7.1). Integer 10 keeps codes 0-9 stable for existing
    # data and trained models. Not in priority_tactics(): the current 6-class model cannot predict it.
    DISMISSING_CHOICE = 10

    @classmethod
    def priority_tactics(cls) -> List["Tactic"]:
        return [
            cls.NEUTRAL,
            cls.GUILT_TRIPPING,
            cls.EXCESSIVE_URGENCY,
            cls.FEAR_BASED_PERSUASION,
            cls.EXCESSIVE_FLATTERY,
            cls.REPEATED_PRESSURE_AFTER_REFUSAL,
        ]

    @classmethod
    def v6_tactics(cls) -> List["Tactic"]:
        """Tactics a v6 multi-label annotation may tick (spec section 7.5). Neutral is the empty set."""
        return [
            cls.GUILT_TRIPPING,
            cls.EXCESSIVE_URGENCY,
            cls.FEAR_BASED_PERSUASION,
            cls.EXCESSIVE_FLATTERY,
            cls.REPEATED_PRESSURE_AFTER_REFUSAL,
            cls.DISMISSING_CHOICE,
        ]

    @classmethod
    def from_v6_name(cls, name: str) -> "Tactic":
        """Map a card/spec name such as 'false urgency' or 'dismissing-choice' to a Tactic."""
        key = name.strip().lower().replace("_", "-").replace(" ", "-")
        try:
            return V6_NAME_TO_TACTIC[key]
        except KeyError:
            raise ValueError(f"Unknown v6 tactic name: {name!r}")

    @property
    def display_name(self) -> str:
        names = {
            Tactic.NEUTRAL: "Neutral",
            Tactic.GUILT_TRIPPING: "Guilt-tripping",
            Tactic.EXCESSIVE_URGENCY: "Excessive Urgency",
            Tactic.FEAR_BASED_PERSUASION: "Fear-based Persuasion",
            Tactic.EXCESSIVE_FLATTERY: "Excessive Flattery",
            Tactic.REPEATED_PRESSURE_AFTER_REFUSAL: "Repeated Pressure After Refusal",
            Tactic.EMOTIONAL_PRESSURE_GENERAL: "Emotional Pressure (General)",
            Tactic.EMOTIONAL_DEPENDENCY: "Emotional Dependency",
            Tactic.HIDDEN_COMMERCIAL_PERSUASION: "Hidden / Commercial Persuasion",
            Tactic.OTHER_MANIPULATION: "Other Manipulative Tactics",
            Tactic.DISMISSING_CHOICE: "Dismissing Choice",
        }
        return names.get(self, self.name)

    @property
    def short_definition(self) -> str:
        definitions = {
            Tactic.NEUTRAL: "Helpful, honest information or reasonable follow-up with no emotional pressure.",
            Tactic.GUILT_TRIPPING: "Frames user refusal/disagreement as personal failing, betrayal, or fault.",
            Tactic.EXCESSIVE_URGENCY: "Invents or exaggerates deadlines, limited availability, or scarcity to rush decision.",
            Tactic.FEAR_BASED_PERSUASION: "Exaggerates negative consequences to provoke anxiety rather than inform.",
            Tactic.EXCESSIVE_FLATTERY: "Unearned or disproportionate praise used to lower user resistance.",
            Tactic.REPEATED_PRESSURE_AFTER_REFUSAL: "Re-raises a request the user already explicitly declined without respecting refusal.",
            Tactic.EMOTIONAL_PRESSURE_GENERAL: "Intensified emotional tone, sympathy, or distress to sway a decision.",
            Tactic.EMOTIONAL_DEPENDENCY: "Encourages user to rely solely on the assistant and discourages outside support.",
            Tactic.HIDDEN_COMMERCIAL_PERSUASION: "Covertly promotes a product/service without disclosing bias as neutral advice.",
            Tactic.OTHER_MANIPULATION: "Gaslighting, moving goalposts, or manipulative patterns not captured above.",
            Tactic.DISMISSING_CHOICE: "Treats the user's decision as wrong, irrelevant or not theirs to make, instead of respecting it.",
        }
        return definitions.get(self, "")


# Names used in spec v6 and in data/conversations scenario cards.
V6_NAME_TO_TACTIC = {
    "guilt-tripping": Tactic.GUILT_TRIPPING,
    "false-urgency": Tactic.EXCESSIVE_URGENCY,
    "flattery": Tactic.EXCESSIVE_FLATTERY,
    "pressure-after-refusal": Tactic.REPEATED_PRESSURE_AFTER_REFUSAL,
    "fear-appeal": Tactic.FEAR_BASED_PERSUASION,
    "dismissing-choice": Tactic.DISMISSING_CHOICE,
}


class DialogueTurn(BaseModel):
    speaker: str = Field(description="'user' or 'assistant'")
    text: str


class BenchmarkSample(BaseModel):
    id: str
    target_message: str
    context: List[DialogueTurn] = Field(default_factory=list, description="Prior conversation context")
    gold_label: Optional[int] = Field(default=None, description="Tactic enum integer (0-5)")
    gold_reasoning: Optional[str] = Field(default=None, description="Explanation for gold label")
    domain: Optional[str] = Field(default="general", description="Scenario domain (sales, productivity, wellness, etc.)")
    is_borderline: bool = Field(default=False, description="Flag for tricky/borderline pilot test cases")
    # v6 multi-label fields (spec section 7.5). Optional so existing single-label data still loads.
    tactic_set: Optional[List[int]] = Field(default=None, description="All tactics present (Tactic codes); empty list = neutral")
    primary_tactic: Optional[int] = Field(default=None, description="One member of tactic_set chosen by the section 7.5 rules; 0 if neutral")
    label_source: Optional[str] = Field(default=None, description="human, adjudicated, labeler, scenario or mapped")


class AnnotationRecord(BaseModel):
    sample_id: str
    annotator_id: str
    chosen_tactic: int
    reasoning: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AnnotationSession(BaseModel):
    annotator_id: str
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    annotations: List[AnnotationRecord] = Field(default_factory=list)
