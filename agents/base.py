from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from models import Action, AgentDecision, Observation


class Agent(Protocol):
    team: str

    def act(self, observation: Observation) -> AgentDecision:
        """Return a JSON-serializable decision for a partial observation.

        Concrete LLM-backed agents are intentionally not implemented yet.
        """
        ...


@dataclass
class PassiveAgent:
    team: str

    def act(self, observation: Observation) -> AgentDecision:
        return AgentDecision(
            proposed_action=Action.wait(),
            message="No action proposed by stub agent.",
            confidence=1.0,
        )
