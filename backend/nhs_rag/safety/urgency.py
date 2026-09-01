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
    r"\b(?:no|not|without|denies|do not have|don't have)\b(?:\W+\w+){0,3}\W*$",
    re.I,
)


def safety_floor(message: str) -> SafetyFloor:
    """Escalate obvious danger wording; this rule can never downgrade NHS evidence."""

    for pattern, reason in _EMERGENCY_PATTERNS:
        match = pattern.search(message)
        if match and not _NEGATION.search(message[max(0, match.start() - 40) : match.start()]):
            return SafetyFloor(emergency=True, reason=reason)
    return SafetyFloor(emergency=False)
