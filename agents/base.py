from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from models import Action, AgentDecision, Observation, Piece, Position


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
        piece = self._select_piece(observation)
        if piece is None:
            return AgentDecision(
                proposed_action=Action.wait(),
                message="No own pieces available; waiting.",
                confidence=1.0,
            )

        legal_moves = observation.legal_moves_by_piece.get(piece.id, [])
        if not legal_moves:
            message = f"No legal chess moves for {piece.id}; waiting."
            if observation.is_checkmate:
                message = f"{piece.id} is checkmated; waiting."
            elif observation.is_stalemate:
                message = f"{piece.id} is stalemated; waiting."
            return AgentDecision(
                proposed_action=Action.wait(),
                message=message,
                confidence=1.0,
            )

        selected_move = sorted(
            legal_moves,
            key=lambda move: (
                not move.capture,
                move.enemy_attack_count,
                -move.friendly_defense_count,
                move.target.row,
                move.target.col,
            ),
        )[0]

        return AgentDecision(
            proposed_action=Action.move(
                piece_id=piece.id,
                target=selected_move.target,
            ),
            message=f"Selected deterministic legal move for {piece.id}.",
            confidence=1.0,
        )

    def _select_piece(self, observation: Observation) -> Piece | None:
        own_pieces = list(observation.own_pieces.values())
        if not own_pieces:
            return None
        return sorted(own_pieces, key=lambda current_piece: current_piece.id)[0]
