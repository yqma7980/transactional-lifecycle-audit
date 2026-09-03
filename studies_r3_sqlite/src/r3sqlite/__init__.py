"""SQLite lifecycle-audit study for M-2026-003 R3."""

from .adjudicator import adjudicate
from .model import Verdict
from .subject import execute_case

__all__ = ["Verdict", "adjudicate", "execute_case"]

