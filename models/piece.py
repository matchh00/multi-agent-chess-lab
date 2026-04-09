from __future__ import annotations

from dataclasses import dataclass

from .position import Position


@dataclass
class Piece:
    id: str
    team: str
    position: Position

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "team": self.team,
            "position": self.position.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Piece":
        position_data = data["position"]
        if not isinstance(position_data, dict):
            raise TypeError("piece position must be a dict")

        return cls(
            id=str(data["id"]),
            team=str(data["team"]),
            position=Position.from_dict(position_data),
        )
