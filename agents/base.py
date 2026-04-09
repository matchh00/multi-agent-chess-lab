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

        occupied_positions = {
            (position["row"], position["col"])
            for position in observation.occupied_positions
            if "row" in position and "col" in position
        }

        for row_delta, col_delta in self._nearby_offsets():
            target_row = piece.position.row + row_delta
            target_col = piece.position.col + col_delta
            if not (0 <= target_row < observation.board_size):
                continue
            if not (0 <= target_col < observation.board_size):
                continue
            if (target_row, target_col) in occupied_positions:
                continue

            return AgentDecision(
                proposed_action=Action.move(
                    piece_id=piece.id,
                    target=Position(row=target_row, col=target_col),
                ),
                message=f"Trying nearby move for {piece.id}.",
                confidence=1.0,
            )

        return AgentDecision(
            proposed_action=Action.wait(),
            message=f"No valid nearby square for {piece.id}; waiting.",
            confidence=1.0,
        )

    def _select_piece(self, observation: Observation) -> Piece | None:
        own_pieces = list(observation.own_pieces.values())
        if not own_pieces:
            return None
        return sorted(own_pieces, key=lambda current_piece: current_piece.id)[0]

    def _nearby_offsets(self) -> tuple[tuple[int, int], ...]:
        # Fixed probe order keeps behavior deterministic.
        return (
            (-1, 0),  # up
            (0, 1),   # right
            (1, 0),   # down
            (0, -1),  # left
            (-1, 1),  # up-right
            (1, 1),   # down-right
            (1, -1),  # down-left
            (-1, -1), # up-left
        )
