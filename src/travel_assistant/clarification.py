"""Bounded clarification policy (deterministic, unit-testable).

The LLM-facing policy text lives in prompts.py (M5). This module is the
deterministic primitive that decides, given the current TripRequest and how
many clarification rounds already happened, whether to ask focused questions
(bounded) or proceed with defaults (never loops forever).
"""
from dataclasses import dataclass, field

from travel_assistant.models import TripRequest

MAX_CLARIFICATION_ROUNDS = 2
MAX_QUESTIONS_PER_ROUND = 3


@dataclass
class ClarificationDecision:
    should_ask: bool
    questions: list[str] = field(default_factory=list)
    proceed_with_defaults: bool = False


def decide_clarification(
    trip_request: TripRequest, round_index: int
) -> ClarificationDecision:
    """Decide the next clarification step.

    - 0 missing critical fields -> do not ask, do not default (ready).
    - round_index >= MAX_CLARIFICATION_ROUNDS and still missing -> proceed
      with defaults (prevents infinite clarification loops).
    - exactly 1 missing -> ask exactly 1 focused question.
    - 2+ missing -> ask up to MAX_QUESTIONS_PER_ROUND (3) focused questions.
    """
    targets = trip_request.clarification_targets()
    if not targets:
        return ClarificationDecision(should_ask=False)
    if round_index >= MAX_CLARIFICATION_ROUNDS:
        return ClarificationDecision(should_ask=False, proceed_with_defaults=True)
    if len(targets) == 1:
        questions = [targets[0].label]
    else:
        questions = [t.label for t in targets[:MAX_QUESTIONS_PER_ROUND]]
    return ClarificationDecision(should_ask=True, questions=questions)
