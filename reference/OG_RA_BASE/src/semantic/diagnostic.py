"""Diagnostic model for compile-time analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class Diagnostic:
    """A single compiler diagnostic message.

    Attributes
    ----------
    message  : str      — human-readable description.
    severity : Severity — ERROR, WARNING, or INFO.
    line     : int      — 1-based source line number.
    column   : int      — 1-based column number (0 when unknown).
    """

    message: str
    severity: Severity
    line: int
    column: int = 0
