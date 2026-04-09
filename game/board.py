from __future__ import annotations

from dataclasses import dataclass

from models import Piece, Position


@dataclass(frozen=True)
class Board:
    size: int = 8

    def contains(self, position: Position) -> bool:
        return position.is_on_board(self.size)

    def get_piece_at(
        self, pieces: dict[str, Piece], position: Position
    ) -> Piece | None:
        for piece in pieces.values():
            if piece.position == position:
                return piece
        return None

    def as_grid(self, pieces: dict[str, Piece]) -> list[list[str | None]]:
        grid: list[list[str | None]] = [
            [None for _ in range(self.size)] for _ in range(self.size)
        ]
        for piece in pieces.values():
            grid[piece.position.row][piece.position.col] = piece.id
        return grid
