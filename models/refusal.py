"""Refusal detection for MindMirror.

Replaces the broad keyword regex that treated "no problem", "stop the timer",
"skip to the summary" and "cancel" questions as refusals.

A user turn counts as a refusal when it declines, rejects, or withdraws from a
request or offer. Some patterns count only when the preceding assistant turn
looks like an offer, so "No, I haven't tried restarting it." (an answer) is not
a refusal while "No, thanks." after an upgrade offer is.
"""

import re
from typing import Any, Dict, List, Optional

USER_SPEAKERS = ("user", "human")
ASSISTANT_SPEAKERS = ("assistant", "agent", "bot", "chatbot")

# "No problem", "no worries", "no rush" etc. are not refusals.
_NO_GUARD = re.compile(
    r"^\s*(?:no|nope|nah)\s*,?\s*(?:problem|worries|worry|rush|hurry|idea|doubt|need to worry)\b",
    re.IGNORECASE,
)

# Patterns that are refusals in any context.
_STRONG = [
    r"\bno,?\s+thanks?\b",
    r"\bno thank you\b",
    r"\bnot interested\b",
    r"\bi\s*(?:do not|don'?t|dont|won'?t|will not|am not going to|'m not going to|'m not)\s+"
    r"(?:want|need|wish|like|buy|upgrade|subscribe|enable|switch|join|sign up|take|keen)\b",
    r"\bi(?:'d| would)\s+rather\s+(?:not|keep|stay|stick)\b",
    r"\bi\s+(?:would\s+)?prefer\s+(?:to\s+)?(?:keep|stay|stick|manual|paper|monthly|my|the current)\b",
    r"\bi(?:'ll| will)\s+pass\b",
    r"\bpass\s+(?:for now|on (?:that|this|it))\b",
    r"\bnot\s+(?:right now|today|for me|at the moment)\b",
    r"\b(?:stop|quit)\s+(?:asking|messaging|pushing|sending|bugging|offering|trying)\b",
    r"\bleave me alone\b",
    r"\bdrop it\b",
    r"\bi\s+(?:already\s+)?(?:said|told you)\s+(?:no|i)\b",
    r"^\s*(?:no,?\s+)?(?:please\s+|just\s+)?cancel\s+(?:it|my|the|this)\b",
    r"\bi\s+(?:want|would like|'d like|need)\s+to\s+cancel\b",
]
_STRONG_RE = [re.compile(p, re.IGNORECASE) for p in _STRONG]

# Short bare "No" at the start of the turn.
_LEADING_NO = re.compile(r"^\s*(?:no|nope|nah)\b[\s,.!]*", re.IGNORECASE)

# Soft objections: refusals only when answering an offer.
_SOFT = re.compile(r"\b(?:too expensive|can'?t afford|cannot afford|out of my budget|maybe later)\b", re.IGNORECASE)

_OFFER = re.compile(
    r"\b(?:would you like|do you want|want me to|shall i|should i|can i (?:offer|add|upgrade|enable|sign)|"
    r"interested in|how about|why not|upgrade|add (?:a|an|the)|subscribe|switch to|enable|sign up|join|"
    r"book|try (?:our|the|a)|take advantage|special offer|discount|deal|plan)\b",
    re.IGNORECASE,
)
_QUESTION_NOT_OFFER = re.compile(
    r"^\s*(?:have you|did you|do you have|is it|are you|what|which|when|where|who|how many|how much)\b",
    re.IGNORECASE,
)


def _is_offer(assistant_text: Optional[str]) -> bool:
    if not assistant_text:
        return False
    if _QUESTION_NOT_OFFER.search(assistant_text) and not _OFFER.search(assistant_text):
        return False
    return bool(_OFFER.search(assistant_text))


def is_refusal(text: str, prev_assistant: Optional[str] = None) -> bool:
    """Return True if a user turn declines or withdraws from an offer or request."""
    if not text or not text.strip():
        return False
    if _NO_GUARD.search(text):
        # "No problem, ..." may still contain a real refusal later in the turn.
        remainder = _NO_GUARD.sub("", text, count=1)
        return any(r.search(remainder) for r in _STRONG_RE)
    if any(r.search(text) for r in _STRONG_RE):
        return True
    if _LEADING_NO.search(text):
        # A bare "No" is a refusal unless it answers a plain information question.
        if prev_assistant is None or _is_offer(prev_assistant):
            return True
        return False
    if _SOFT.search(text) and _is_offer(prev_assistant):
        return True
    return False


def _turn_speaker(turn: Dict[str, Any]) -> str:
    return str(turn.get("speaker", "")).lower()


def refusal_indices(context: List[Dict[str, Any]]) -> List[int]:
    """Indices of user turns in the context that are refusals."""
    found = []
    for i, turn in enumerate(context):
        if _turn_speaker(turn) not in USER_SPEAKERS:
            continue
        prev_assistant = None
        if i > 0 and _turn_speaker(context[i - 1]) in ASSISTANT_SPEAKERS:
            prev_assistant = context[i - 1].get("text", "")
        if is_refusal(turn.get("text", ""), prev_assistant):
            found.append(i)
    return found


def has_prior_refusal(context: List[Dict[str, Any]]) -> bool:
    """True if the most recent user turn in the context is a refusal.

    Matches the original feature definition (last user turn only) so the model
    feature keeps its meaning while the detector is stricter.
    """
    last_user = None
    for i in range(len(context) - 1, -1, -1):
        if _turn_speaker(context[i]) in USER_SPEAKERS:
            last_user = i
            break
    return last_user is not None and last_user in refusal_indices(context)


def turns_since_refusal(context: List[Dict[str, Any]]) -> Optional[int]:
    """Number of turns between the latest refusal and the end of the context."""
    idx = refusal_indices(context)
    if not idx:
        return None
    return len(context) - 1 - idx[-1]


def last_refusal_text(context: List[Dict[str, Any]]) -> Optional[str]:
    idx = refusal_indices(context)
    return context[idx[-1]].get("text", "") if idx else None
