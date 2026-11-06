"""Typed errors of the contract validator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

ErrorCode = Literal[
    "required",
    "type",
    "range",
    "format",
    "unknown_field",
    "reference",
    "duplicate",
    "version",
    "too_many",
    "too_deep",
    "too_many_errors",
]


@dataclass(frozen=True)
class FieldError:
    """One problem found in a document.

    Attributes:
        path: Location of the problem, for example ``findings[1].evidence[0]``; empty for the
            document root.
        code: Stable machine-readable code.
        message: Human-readable explanation; it never quotes input.
    """

    path: str
    code: ErrorCode
    message: str


class ContractError(Exception):
    """Raised when a document violates a contract.

    Attributes:
        errors: Every problem found, in document order (at most 101 entries).
        code: Always ``"invalid"``.
    """

    code: ClassVar[str] = "invalid"

    def __init__(self, errors: tuple[FieldError, ...]) -> None:
        self.errors = errors
        summary = f"{len(errors)} contract violation(s)"
        if errors:
            first = errors[0]
            summary += f"; first: {first.code} at {first.path or '<root>'}"
        super().__init__(summary[:200])
