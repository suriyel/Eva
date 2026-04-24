"""F19 · Bk-Dispatch — spawn-time model resolution + ticket classification.

Public facade re-exports for F18 (ClaudeCodeAdapter.build_argv) + F20
(RunOrchestrator) consumption.
"""

from __future__ import annotations

from .classifier import ClassifierService
from .model import ModelResolver

__all__ = ["ModelResolver", "ClassifierService"]
