"""Contract-injected conversation loader and context-window preparation.

Taxonomy names and annotation field names are supplied by the annotation
protocol owner. This module does not define or map the MindMirror taxonomy.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

SUPPORTED_CONTEXT_WINDOWS = (0, 2, 4, 6)


@dataclass(frozen=True)
class AnnotationContract:
    """Adapter mapping for the annotation contract; taxonomy is always injected."""
    tactic_names: tuple[str, ...]
    id_field: str = "conversation_id"
    turns_field: str = "turns"
    speaker_field: str = "speaker"
    text_field: str = "text"
    assistant_annotation_field: str = "assistant_annotation"
    tactic_set_field: str = "tactic_set"
    primary_tactic_field: str = "primary_tactic"
    pressure_field: str = "pressure_level_0_3"
    user_refusal_field: str = "user_refusal"
    refusal_value_field: str = "refusal"
    conversation_annotation_field: str = "conversation_annotation"
    escalating_field: str = "escalating"
    onset_field: str = "onset_turn_index"
    onset_pressure_threshold: int = 2

    def __post_init__(self) -> None:
        if not self.tactic_names or len(set(self.tactic_names)) != len(self.tactic_names):
            raise ValueError("tactic_names must be a non-empty sequence of unique names from the owner contract")
        if self.onset_pressure_threshold not in range(4):
            raise ValueError("pressure threshold must be in [0, 3]")


@dataclass(frozen=True)
class ParsedTurn:
    turn_index: int
    speaker: str
    text: str
    refusal: bool | None = None
    tactic_set: tuple[str, ...] | None = None
    primary_tactic: str | None = None
    pressure: int | None = None


@dataclass(frozen=True)
class PreparedExample:
    conversation_id: str
    domain: str | None
    turn_index: int
    input_text: str
    tactic_targets: tuple[int, ...] | None
    primary_target: str | None
    pressure_target: int | None
    prior_refusal: bool
    escalating_target: bool | None
    onset_turn_index: int | None


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


def _maybe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_turns(record: dict[str, Any], contract: AnnotationContract) -> list[ParsedTurn]:
    cid = str(record.get(contract.id_field, "<missing-id>"))
    turns = record.get(contract.turns_field)
    if not isinstance(turns, list) or not turns:
        raise ValueError(f"{cid}: '{contract.turns_field}' must be a non-empty list")
    parsed = []
    for index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            raise ValueError(f"{cid}: turn {index} must be an object")
        speaker = turn.get(contract.speaker_field)
        text = turn.get(contract.text_field)
        if speaker not in ("user", "assistant"):
            raise ValueError(f"{cid}: turn {index} has unsupported speaker {speaker!r}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{cid}: turn {index} text must be non-empty")
        refusal_obj = _maybe_mapping(turn.get(contract.user_refusal_field))
        refusal_raw = refusal_obj.get(contract.refusal_value_field)
        refusal = refusal_raw if isinstance(refusal_raw, bool) else None
        assistant_obj = _maybe_mapping(turn.get(contract.assistant_annotation_field))
        raw_set = assistant_obj.get(contract.tactic_set_field)
        tactic_set: tuple[str, ...] | None
        if raw_set is None:
            tactic_set = None
        elif not isinstance(raw_set, list):
            raise ValueError(f"{cid}: assistant turn {index} tactic set must be a list or null")
        else:
            tactic_set = tuple(str(tactic) for tactic in raw_set)
            unknown = set(tactic_set) - set(contract.tactic_names)
            if unknown:
                raise ValueError(f"{cid}: assistant turn {index} has tactics outside the injected contract: {sorted(unknown)}")
            if len(set(tactic_set)) != len(tactic_set):
                raise ValueError(f"{cid}: assistant turn {index} repeats a tactic")
        primary = assistant_obj.get(contract.primary_tactic_field)
        if primary is not None:
            primary = str(primary)
            if primary != "neutral" and primary not in contract.tactic_names:
                raise ValueError(f"{cid}: assistant turn {index} primary tactic is outside the injected contract")
        pressure_raw = assistant_obj.get(contract.pressure_field)
        pressure = None
        if pressure_raw is not None:
            if isinstance(pressure_raw, bool) or not isinstance(pressure_raw, int) or pressure_raw not in range(4):
                raise ValueError(f"{cid}: assistant turn {index} pressure must be an integer in [0, 3]")
            pressure = pressure_raw
        parsed.append(ParsedTurn(index, speaker, text, refusal, tactic_set, primary, pressure))
    return parsed


def _escalation(record: dict[str, Any], turns: Sequence[ParsedTurn], contract: AnnotationContract) -> tuple[bool | None, int | None]:
    conv_ann = _maybe_mapping(record.get(contract.conversation_annotation_field))
    explicit = conv_ann.get(contract.escalating_field)
    explicit_onset = conv_ann.get(contract.onset_field)
    if explicit is not None and not isinstance(explicit, bool):
        raise ValueError("conversation escalation annotation must be boolean or null")
    if explicit_onset is not None and (isinstance(explicit_onset, bool) or not isinstance(explicit_onset, int)):
        raise ValueError("onset turn index must be integer or null")
    if explicit is not None:
        return explicit, explicit_onset

    refusal_seen = False
    unknown_refusal = False
    unknown_pressure_after_refusal = False
    derived_onset = None
    for turn in turns:
        if turn.speaker == "user":
            if turn.refusal is True:
                refusal_seen = True
            elif turn.refusal is None:
                unknown_refusal = True
        elif refusal_seen:
            if turn.pressure is None:
                unknown_pressure_after_refusal = True
            elif turn.pressure >= contract.onset_pressure_threshold:
                derived_onset = turn.turn_index
                break
    if derived_onset is not None:
        return True, derived_onset
    if unknown_refusal or unknown_pressure_after_refusal:
        return None, None
    return False, None


def prepare_examples(
    record: dict[str, Any],
    contract: AnnotationContract,
    context_window: int,
    refusal_marker: str = "[REFUSAL]",
) -> list[PreparedExample]:
    """Create one assistant-turn example with the requested preceding context.

    Context window is the number of prior turns, not including the target turn.
    A refusal marker is emitted only from an annotated true refusal.
    """
    if context_window not in SUPPORTED_CONTEXT_WINDOWS:
        raise ValueError(f"context_window must be one of {SUPPORTED_CONTEXT_WINDOWS}")
    turns = parse_turns(record, contract)
    escalation, onset = _escalation(record, turns, contract)
    cid = str(record.get(contract.id_field, "<missing-id>"))
    domain = record.get("domain")
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
        target_set = target.tactic_set
        target_vector = None if target_set is None else tuple(int(tactic in target_set) for tactic in contract.tactic_names)
        prepared.append(PreparedExample(
            conversation_id=cid,
            domain=str(domain) if domain is not None else None,
            turn_index=target.turn_index,
            input_text="\n".join(messages),
            tactic_targets=target_vector,
            primary_target=target.primary_tactic,
            pressure_target=target.pressure,
            prior_refusal=prior_refusal,
            escalating_target=escalation,
            onset_turn_index=onset,
        ))
    return prepared


def prepare_dataset(records: Iterable[dict[str, Any]], contract: AnnotationContract, context_window: int) -> list[PreparedExample]:
    output = []
    for record in records:
        output.extend(prepare_examples(record, contract, context_window))
    return output
