from __future__ import annotations

from dataclasses import dataclass, field

from .legal_move import LegalMove
from .piece import Piece


@dataclass(frozen=True)
class Observation:
    team: str
    turn: int
    active_team: str
    board_size: int = 8
    own_pieces: dict[str, Piece] = field(default_factory=dict)
    occupied_positions: list[dict[str, int]] = field(default_factory=list)
    legal_moves_by_piece: dict[str, list[LegalMove]] = field(default_factory=dict)
    attack_count_by_square: dict[str, int] = field(default_factory=dict)
    defense_count_by_square: dict[str, int] = field(default_factory=dict)
    is_in_check: bool = False
    is_checkmate: bool = False
    is_stalemate: bool = False

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
            "legal_moves_by_piece": {
                piece_id: [move.to_dict() for move in moves]
                for piece_id, moves in sorted(self.legal_moves_by_piece.items())
            },
            "attack_count_by_square": dict(sorted(self.attack_count_by_square.items())),
            "defense_count_by_square": dict(sorted(self.defense_count_by_square.items())),
            "is_in_check": self.is_in_check,
            "is_checkmate": self.is_checkmate,
            "is_stalemate": self.is_stalemate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Observation":
        own_pieces_data = data.get("own_pieces", {})
        if not isinstance(own_pieces_data, dict):
            raise TypeError("own_pieces must be a dict")

        occupied_positions_data = data.get("occupied_positions", [])
        if not isinstance(occupied_positions_data, list):
            raise TypeError("occupied_positions must be a list")

        legal_moves_data = data.get("legal_moves_by_piece", {})
        if not isinstance(legal_moves_data, dict):
            raise TypeError("legal_moves_by_piece must be a dict")

        attack_count_data = data.get("attack_count_by_square", {})
        if not isinstance(attack_count_data, dict):
            raise TypeError("attack_count_by_square must be a dict")

        defense_count_data = data.get("defense_count_by_square", {})
        if not isinstance(defense_count_data, dict):
            raise TypeError("defense_count_by_square must be a dict")

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
            legal_moves_by_piece={
                str(piece_id): [
                    LegalMove.from_dict(move_data)
                    for move_data in moves
                    if isinstance(move_data, dict)
                ]
                for piece_id, moves in legal_moves_data.items()
                if isinstance(moves, list)
            },
            attack_count_by_square={
                str(square): int(count)
                for square, count in attack_count_data.items()
            },
            defense_count_by_square={
                str(square): int(count)
                for square, count in defense_count_data.items()
            },
            is_in_check=bool(data.get("is_in_check", False)),
            is_checkmate=bool(data.get("is_checkmate", False)),
            is_stalemate=bool(data.get("is_stalemate", False)),
        )
