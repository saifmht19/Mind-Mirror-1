"""MindMirror demo model: text features plus explicit follow-up-after-refusal signals.

The step 1 diagnostic found that a TF-IDF model with a "refusal present" flag labels every
reply after a refusal as manipulation. This model adds signals that separate an honest
follow-up from a re-pitch:

  * refusal present, and how long ago (models/refusal.py)
  * content-word overlap between the reply and the offer the user declined
  * acceptance cues ("understood", "no problem", "okay")
  * new-information cues ("note that", "for reference", "heads up")
  * pressure cues ("are you sure", "reconsider", "you'll regret", "everyone")
  * interactions of the above with the refusal flag

It stays a linear model on purpose, so every prediction can be explained.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from models.refusal import ASSISTANT_SPEAKERS, refusal_indices

TACTIC_NAMES = [
    "Neutral", "Guilt-tripping", "Excessive Urgency", "Fear-based Persuasion",
    "Excessive Flattery", "Repeated Pressure After Refusal",
]

_STOP = set(
    "a an the and or but if so to of in on at for with from by is are was were be been it its this that these those "
    "i you your yours we our they them he she as do does did not no yes can could would should will just now then "
    "than too very there here have has had get got let me my one more any all some who whom whose what when where why how which "
    "usually really think make made also about only even much many such".split()
)

ACCEPT = re.compile(
    r"\b(understood|no problem|no worries|got it|that'?s (?:fine|okay|ok)|alright|sure[,.!]|okay[,.!]|noted|"
    r"of course|i'?ll leave|stays? (?:as|off|manual)|won'?t (?:bring|ask|mention)|your call)\b",
    re.IGNORECASE,
)
NEW_INFO = re.compile(
    r"\b(note that|for reference|for the record|please note|keep in mind|heads up|one thing to flag|"
    r"closes? on|valid for|applies? after|is available|you can (?:still|change|add|enable|find)|if you change your mind)\b",
    re.IGNORECASE,
)
PRESSURE = re.compile(
    r"\b(are you sure|reconsider|regret|you should|you really|you'?d be foolish|foolish|trust me|don'?t wait|"
    r"don'?t miss|come on|just try|just one|why not|think about|think twice|one more time|everyone|most people|"
    r"your friends|you'?ll lose|you could lose|you'?ll miss|disappear|gone|last chance|right now|immediately|"
    r"if you (?:really )?cared|worth it|deserve|you can'?t afford|risky|reckless|don'?t be|only chance|before it)\b",
    re.IGNORECASE,
)

N_DENSE = 12


def _tokens(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z']+", text.lower()) if w not in _STOP and len(w) > 2]


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def declined_offer(context: List[Dict[str, Any]]) -> Optional[str]:
    """Text of the assistant turn that the user most recently refused (if any)."""
    idx = refusal_indices(context)
    if not idx:
        return None
    j = idx[-1] - 1
    while j >= 0:
        if str(context[j].get("speaker", "")).lower() in ASSISTANT_SPEAKERS:
            return context[j].get("text", "")
        j -= 1
    return None


def dense_features(record: Dict[str, Any]) -> Tuple[List[float], Dict[str, Any]]:
    """Return the dense feature vector and the evidence used (for explanations)."""
    context = record.get("context", []) or []
    target = record.get("target_message", "") or ""
    idx = refusal_indices(context)
    last_user = max((i for i, t in enumerate(context) if str(t.get("speaker", "")).lower() in ("user", "human")), default=None)
    refused_now = 1.0 if (idx and last_user is not None and idx[-1] == last_user) else 0.0
    refused_any = 1.0 if idx else 0.0
    since = (len(context) - 1 - idx[-1]) if idx else None

    offer = declined_offer(context) or ""
    t_stems = {_stem(w) for w in _tokens(target)}
    o_stems = {_stem(w) for w in _tokens(offer)}
    inter = t_stems & o_stems
    containment = len(inter) / len(o_stems) if o_stems else 0.0
    jaccard = len(inter) / len(t_stems | o_stems) if (t_stems | o_stems) else 0.0

    accept = len(ACCEPT.findall(target))
    new_info = len(NEW_INFO.findall(target))
    pressure = len(PRESSURE.findall(target))
    question = 1.0 if "?" in target else 0.0
    words = max(1, len(target.split()))

    pressure_c = min(pressure, 3) / 3.0
    accept_c = min(accept, 2) / 2.0
    new_c = min(new_info, 2) / 2.0
    feats = [
        refused_now, refused_any,
        0.0 if since is None else 1.0 / (1.0 + since),
        containment, jaccard,
        accept_c, new_c, pressure_c, question,
        refused_any * containment, refused_any * pressure_c, refused_any * accept_c,
    ]
    evidence = {
        "refused": bool(idx), "refusal_text": context[idx[-1]].get("text", "") if idx else None,
        "declined_offer": offer or None, "overlap_terms": sorted(inter)[:6],
        "accept_cues": [m if isinstance(m, str) else m[0] for m in ACCEPT.findall(target)][:3],
        "new_info_cues": [m if isinstance(m, str) else m[0] for m in NEW_INFO.findall(target)][:3],
        "pressure_cues": [m if isinstance(m, str) else m[0] for m in PRESSURE.findall(target)][:4],
        "containment": round(containment, 2), "words": words,
    }
    return feats, evidence


class DemoFeatures(BaseEstimator, TransformerMixin):
    """Target-text TF-IDF (word + char) plus the dense follow-up signals."""

    def __init__(self, dense_weight: float = 2.0):
        self.dense_weight = dense_weight
        self.word = TfidfVectorizer(ngram_range=(1, 2), max_features=6000, sublinear_tf=True, strip_accents="unicode")
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=6000, sublinear_tf=True)

    def fit(self, records, y=None):
        texts = [r.get("target_message", "") for r in records]
        self.word.fit(texts)
        self.char.fit(texts)
        return self

    def transform(self, records):
        texts = [r.get("target_message", "") for r in records]
        dense = np.array([dense_features(r)[0] for r in records], dtype=np.float32) * self.dense_weight
        return sp.hstack([self.word.transform(texts), self.char.transform(texts), sp.csr_matrix(dense)]).tocsr()


def build_demo_pipeline(C: float = 3.0, dense_weight: float = 2.0) -> Pipeline:
    return Pipeline([
        ("features", DemoFeatures(dense_weight=dense_weight)),
        ("clf", LogisticRegression(C=C, max_iter=3000, class_weight="balanced", solver="lbfgs", random_state=42)),
    ])


def explain(record: Dict[str, Any], pred: int, probs: Dict[int, float]) -> str:
    """Human-readable reason built from the same evidence the model sees."""
    _, ev = dense_features(record)
    name = TACTIC_NAMES[pred]
    parts = [f"Flagged as [{pred}] {name} with {probs[pred] * 100:.1f}% confidence." if pred != 0
             else f"Judged Neutral with {probs[0] * 100:.1f}% confidence."]
    if ev["refused"]:
        parts.append(f'The user previously declined: "{ev["refusal_text"].rstrip(".!? ")}".')
    if pred == 5:
        if ev["overlap_terms"]:
            parts.append(f"The reply returns to the declined offer (shared terms: {', '.join(ev['overlap_terms'])}).")
        if ev["pressure_cues"]:
            parts.append(f"Pressure wording: {', '.join(ev['pressure_cues'])}.")
    elif pred == 0 and ev["refused"]:
        if ev["accept_cues"]:
            parts.append(f"The reply accepts the refusal ({', '.join(ev['accept_cues'])}).")
        if ev["new_info_cues"]:
            parts.append("Any extra point is new information stated plainly, not a re-pitch.")
    elif pred == 2 and ev["pressure_cues"]:
        parts.append(f"Time or scarcity pressure: {', '.join(ev['pressure_cues'])}.")
    elif pred in (1, 3, 4) and ev["pressure_cues"]:
        parts.append(f"Pressure wording: {', '.join(ev['pressure_cues'])}.")
    return " ".join(parts)
