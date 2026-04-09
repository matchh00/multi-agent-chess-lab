from __future__ import annotations

from dataclasses import dataclass, field

from .piece import Piece


@dataclass(frozen=True)
class Observation:
    team: str
    turn: int
    active_team: str
    board_size: int = 8
    own_pieces: dict[str, Piece] = field(default_factory=dict)
    occupied_positions: list[dict[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "team": self.team,
            "turn": self.turn,
            "active_team": self.active_team,
            "board_size": self.board_size,
            "own_pieces": {
                piece_id: piece.to_dict()
                for piece_id, piece in sorted(self.own_pieces.items())
            },
            "occupied_positions": list(self.occupied_positions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Observation":
        own_pieces_data = data.get("own_pieces", {})
        if not isinstance(own_pieces_data, dict):
            raise TypeError("own_pieces must be a dict")

        occupied_positions_data = data.get("occupied_positions", [])
        if not isinstance(occupied_positions_data, list):
            raise TypeError("occupied_positions must be a list")

        return cls(
            team=str(data["team"]),
            turn=int(data["turn"]),
            active_team=str(data["active_team"]),
            board_size=int(data.get("board_size", 8)),
            own_pieces={
                str(piece_id): Piece.from_dict(piece_data)
                for piece_id, piece_data in own_pieces_data.items()
                if isinstance(piece_data, dict)
            },
            occupied_positions=[
                dict(position)
                for position in occupied_positions_data
                if isinstance(position, dict)
            ],
        )
