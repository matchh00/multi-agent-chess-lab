from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    row: int
    col: int

    def is_on_board(self, size: int = 8) -> bool:
        return 0 <= self.row < size and 0 <= self.col < size

    def to_dict(self) -> dict[str, int]:
        return {"row": self.row, "col": self.col}

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "Position":
        return cls(row=data["row"], col=data["col"])
