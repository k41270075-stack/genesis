"""The shared matcher and terminal reward (published code, section 05 of the task)."""

from .findings import MAX_EVIDENCE, MAX_EXPLANATION_CHARS, MAX_FINDINGS, Finding, validate
from .grade import grade
from .match import match
from .reward import f1, precision, recall, shared_reward
from .truth import ISSUE_TYPES, Issue

__all__ = [
    "ISSUE_TYPES", "MAX_EVIDENCE", "MAX_EXPLANATION_CHARS", "MAX_FINDINGS",
    "Finding", "Issue", "f1", "grade", "match", "precision", "recall",
    "shared_reward", "validate",
]
