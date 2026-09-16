from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyFloor:
    emergency: bool
    reason: str | None = None


_EMERGENCY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(not breathing|stopped breathing|cannot breathe|can't breathe)\b", re.I),
        "severe breathing difficulty",
    ),
    (
        re.compile(r"\b(unconscious|won't wake|will not wake|collapsed and unresponsive)\b", re.I),
        "loss of consciousness",
    ),
    (
        re.compile(r"\b(chest pain|tightness in (?:my|the) chest)\b", re.I),
        "chest pain",
    ),
    (
        re.compile(r"\b(face droop|slurred speech|sudden weakness on one side)\b", re.I),
        "possible stroke signs",
    ),
    (
        re.compile(r"\b(severe bleeding|bleeding won't stop|bleeding will not stop)\b", re.I),
        "severe bleeding",
    ),
    (
        re.compile(r"\b(overdose|about to kill myself|immediate danger of self[- ]harm)\b", re.I),
        "immediate danger",
    ),
)

_NEGATION = re.compile(
    r"\b(?:no(?:\s+longer)?|without|denies(?:\s+having)?|"
    r"(?:do not|don't|does not|doesn't)\s+(?:have|feel|experience)|"
    r"not(?:\s+(?:having|feeling|experiencing))?)\s+(?:any\s+)?$",
    re.I,
)


def safety_floor(message: str) -> SafetyFloor:
    """Escalate matched danger phrases unless they are explicitly negated."""

    message = message.replace("’", "'")
    for pattern, reason in _EMERGENCY_PATTERNS:
        for match in pattern.finditer(message):
            # Only an adjacent negation suppresses a match; another symptom or clause must not.
            if not _NEGATION.search(message[: match.start()]):
                return SafetyFloor(emergency=True, reason=reason)
    return SafetyFloor(emergency=False)
