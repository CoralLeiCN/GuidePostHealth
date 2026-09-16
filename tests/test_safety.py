import pytest
from nhs_rag.safety.urgency import safety_floor


@pytest.mark.parametrize(
    "message",
    [
        "I have no fever but chest pain",
        "No cough but I cannot breathe",
        "Earlier no chest pain, now chest pain",
        "I have not only chest pain but a cough",
        "No chest pain. My partner has chest pain",
        "I can’t breathe",
        "They are not breathing",
    ],
)
def test_negation_does_not_hide_a_positive_danger_phrase(message: str) -> None:
    assert safety_floor(message).emergency


@pytest.mark.parametrize(
    "message",
    [
        "I have no chest pain",
        "I do not have chest pain",
        "I don't have any chest pain",
        "I don’t have chest pain",
        "They are not unconscious",
        "They are no longer unconscious",
        "I have a cough without chest pain",
    ],
)
def test_explicit_adjacent_negation_is_respected(message: str) -> None:
    assert not safety_floor(message).emergency
