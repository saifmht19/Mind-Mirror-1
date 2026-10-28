"""Contract-injected loader for MindMirror's multi-label conversation annotations.

Track A owns the versioned JSON Schema and taxonomy. No tactic names are
invented here: callers inject the canonical taxonomy from that contract.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SUPPORTED_CONTEXT_WINDOWS = (0, 2, 4, 6)
V6_ESCALATION_PRESSURE_THRESHOLD = 2  # canonical rule: pressure 2 or 3 after a prior refusal


@dataclass(frozen=True)
class AnnotationContract:
    """Field adapter for schema v1.0.0; `tactic_names` comes from Track A's schema."""
    tactic_names: tuple[str, ...]
    id_field: str = "conversation_id"
    turns_field: str = "turns"
    turn_annotations_field: str = "turn_annotations"
    speaker_field: str = "speaker"
    text_field: str = "text"
    turn_index_field: str = "turn_index"
    label_source_field: str = "label_source"
    refusal_field: str = "refusal"
    tactic_set_field: str = "tactic_set"
    primary_tactic_field: str = "primary_tactic"
    pressure_field: str = "pressure_level"
    tactic_spans_field: str = "tactic_spans"
    conversation_annotation_field: str = "conversation_annotation"
    escalating_field: str = "escalating"
    onset_field: str = "onset_turn_index"

    @classmethod
    def from_schema_document(cls, schema: Mapping[str, Any]) -> "AnnotationContract":
        """Read the tactic inventory from Track A's canonical JSON Schema document."""
        try:
            tactics = tuple(schema["$defs"]["tactic"]["enum"])
        except (KeyError, TypeError) as exc:
            raise ValueError("schema is missing $defs.tactic.enum") from exc
        return cls(tactic_names=tactics)

    @classmethod
    def from_json_schema(cls, path: str | Path) -> "AnnotationContract":
        """Load Track A's schema from disk and adapt its taxonomy inventory."""
        schema = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_schema_document(schema)
    def __post_init__(self) -> None:
        if not self.tactic_names or len(set(self.tactic_names)) != len(self.tactic_names):
            raise ValueError("tactic_names must be a non-empty sequence of unique names from the owner contract")


@dataclass(frozen=True)
class ParsedTurn:
    turn_index: int
    speaker: str
    text: str
    refusal: bool | None = None
    tactic_set: tuple[str, ...] | None = None
    primary_tactic: str | None = None
    pressure: int | None = None
    label_source: str | None = None


@dataclass(frozen=True)
class PreparedExample:
    conversation_id: str
    domain: str | None
    turn_index: int
    input_text: str
    tactic_targets: tuple[int, ...] | None
    primary_target: str | None
    pressure_target: int | None
    target_label_source: str | None
    prior_refusal: bool
    escalating_target: bool | None
    onset_turn_index: int | None
    conversation_label_source: str | None
    annotator_type: str | None


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read JSONL without mutating source records; fail with precise line errors."""
    records = []
    with Path(path).open(encoding="utf-8-sig") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_no}: conversation must be a JSON object")
            records.append(record)
    return records


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_turns(record: dict[str, Any], contract: AnnotationContract) -> list[ParsedTurn]:
    cid = str(record.get(contract.id_field, "<missing-id>"))
    source_turns = record.get(contract.turns_field)
    if not isinstance(source_turns, list) or not source_turns:
        raise ValueError(f"{cid}: '{contract.turns_field}' must be a non-empty list")
    annotations = record.get(contract.turn_annotations_field)
    if annotations is None:
        # Unannotated source transcripts remain loadable; missing labels stay unknown.
        annotations = [{} for _ in source_turns]
    if not isinstance(annotations, list) or len(annotations) != len(source_turns):
        raise ValueError(f"{cid}: turn_annotations must align one-to-one with turns")
    parsed = []
    for index, (turn, annotation) in enumerate(zip(source_turns, annotations)):
        if not isinstance(turn, dict) or not isinstance(annotation, dict):
            raise ValueError(f"{cid}: turn and annotation {index} must be objects")
        speaker = turn.get(contract.speaker_field)
        text = turn.get(contract.text_field)
        if speaker not in ("user", "assistant"):
            raise ValueError(f"{cid}: turn {index} has unsupported speaker {speaker!r}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{cid}: turn {index} text must be non-empty")
        annotation_index = annotation.get(contract.turn_index_field, index)
        annotation_speaker = annotation.get(contract.speaker_field, speaker)
        if annotation_index != index or annotation_speaker != speaker:
            raise ValueError(f"{cid}: turn annotation {index} does not align with source turn index/speaker")
        refusal_raw = annotation.get(contract.refusal_field) if speaker == "user" else None
        refusal = refusal_raw if isinstance(refusal_raw, bool) else None
        raw_set = annotation.get(contract.tactic_set_field) if speaker == "assistant" else None
        tactic_set: tuple[str, ...] | None
        if speaker != "assistant" or raw_set is None:
            tactic_set = None
        elif not isinstance(raw_set, list):
            raise ValueError(f"{cid}: assistant turn {index} tactic_set must be a list or null")
        else:
            tactic_set = tuple(str(tactic) for tactic in raw_set)
            unknown = set(tactic_set) - set(contract.tactic_names)
            if unknown:
                raise ValueError(f"{cid}: assistant turn {index} has tactics outside the injected contract: {sorted(unknown)}")
            if len(set(tactic_set)) != len(tactic_set):
                raise ValueError(f"{cid}: assistant turn {index} repeats a tactic")
        primary = annotation.get(contract.primary_tactic_field) if speaker == "assistant" else None
        if primary is not None:
            primary = str(primary)
            if primary != "neutral" and primary not in contract.tactic_names:
                raise ValueError(f"{cid}: assistant turn {index} primary tactic is outside the injected contract")
        pressure_raw = annotation.get(contract.pressure_field) if speaker == "assistant" else None
        pressure = None
        if pressure_raw is not None:
            if isinstance(pressure_raw, bool) or not isinstance(pressure_raw, int) or pressure_raw not in range(4):
                raise ValueError(f"{cid}: assistant turn {index} pressure_level must be an integer in [0, 3]")
            pressure = pressure_raw
        label_source = annotation.get(contract.label_source_field)
        parsed.append(ParsedTurn(index, speaker, text, refusal, tactic_set, primary, pressure,
                                 str(label_source) if label_source is not None else None))
    return parsed


def _derive_escalation(turns: Sequence[ParsedTurn]) -> tuple[bool | None, int | None]:
    refusal_seen = False
    unknown_refusal = False
    unknown_pressure_after_refusal = False
    onset = None
    for turn in turns:
        if turn.speaker == "user":
            if turn.refusal is True:
                refusal_seen = True
            elif turn.refusal is None:
                unknown_refusal = True
        elif refusal_seen:
            if turn.pressure is None:
                unknown_pressure_after_refusal = True
            elif turn.pressure >= V6_ESCALATION_PRESSURE_THRESHOLD:
                onset = turn.turn_index
                break
    if onset is not None:
        return True, onset
    if unknown_refusal or unknown_pressure_after_refusal:
        return None, None
    return False, None


def _conversation_target(record: dict[str, Any], turns: Sequence[ParsedTurn], contract: AnnotationContract) -> tuple[bool | None, int | None, str | None]:
    annotation = _mapping(record.get(contract.conversation_annotation_field))
    derived_escalating, derived_onset = _derive_escalation(turns)
    explicit = annotation.get(contract.escalating_field)
    explicit_onset = annotation.get(contract.onset_field)
    if explicit is not None and not isinstance(explicit, bool):
        raise ValueError("conversation escalation annotation must be boolean or null")
    if explicit_onset is not None and (isinstance(explicit_onset, bool) or not isinstance(explicit_onset, int)):
        raise ValueError("onset turn index must be integer or null")
    return (explicit if explicit is not None else derived_escalating,
            explicit_onset if contract.onset_field in annotation else derived_onset,
            str(annotation[contract.label_source_field]) if annotation.get(contract.label_source_field) is not None else None)


def prepare_examples(record: dict[str, Any], contract: AnnotationContract, context_window: int,
                     refusal_marker: str = "[REFUSAL]") -> list[PreparedExample]:
    """Create one assistant-turn example with at most k preceding turns.

    A refusal marker is emitted only for an explicitly annotated true refusal.
    The model input excludes annotation content and source/generator metadata.
    """
    if context_window not in SUPPORTED_CONTEXT_WINDOWS:
        raise ValueError(f"context_window must be one of {SUPPORTED_CONTEXT_WINDOWS}")
    turns = parse_turns(record, contract)
    escalation, onset, conversation_label_source = _conversation_target(record, turns, contract)
    cid = str(record.get(contract.id_field, "<missing-id>"))
    domain = record.get("domain")
    annotator_type = _mapping(record.get("annotator")).get("annotator_type")
    prepared = []
    for target in turns:
        if target.speaker != "assistant":
            continue
        previous = turns[max(0, target.turn_index - context_window):target.turn_index]
        messages = []
        prior_refusal = False
        for turn in previous:
            marker = ""
            if turn.speaker == "user" and turn.refusal is True:
                marker = refusal_marker + " "
                prior_refusal = True
            messages.append(f"{turn.speaker.upper()}: {marker}{turn.text}")
        messages.append(f"ASSISTANT: {target.text}")
        target_vector = None if target.tactic_set is None else tuple(int(tactic in target.tactic_set) for tactic in contract.tactic_names)
        prepared.append(PreparedExample(
            conversation_id=cid, domain=str(domain) if domain is not None else None,
            turn_index=target.turn_index, input_text="\n".join(messages),
            tactic_targets=target_vector, primary_target=target.primary_tactic,
            pressure_target=target.pressure, target_label_source=target.label_source,
            prior_refusal=prior_refusal, escalating_target=escalation,
            onset_turn_index=onset, conversation_label_source=conversation_label_source,
            annotator_type=str(annotator_type) if annotator_type is not None else None,
        ))
    return prepared


def prepare_dataset(records: Iterable[dict[str, Any]], contract: AnnotationContract, context_window: int) -> list[PreparedExample]:
    return [example for record in records for example in prepare_examples(record, contract, context_window)]


