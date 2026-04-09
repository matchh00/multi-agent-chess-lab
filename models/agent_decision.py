from __future__ import annotations

from dataclasses import dataclass

from .action import Action


@dataclass(frozen=True)
class AgentDecision:
    proposed_action: Action
    message: str
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, object]:
        return {
            "proposed_action": self.proposed_action.to_dict(),
            "message": self.message,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AgentDecision":
        action_data = data["proposed_action"]
        if not isinstance(action_data, dict):
            raise TypeError("proposed_action must be a dict")

        return cls(
            proposed_action=Action.from_dict(action_data),
            message=str(data["message"]),
            confidence=float(data["confidence"]),
        )
