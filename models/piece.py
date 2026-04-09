from __future__ import annotations

from dataclasses import dataclass

from .position import Position


@dataclass
class Piece:
    id: str
    team: str
    position: Position

    @property
    def kind(self) -> str:
        normalized_id = self.id.lower()
        piece_kinds = ("pawn", "knight", "bishop", "rook", "queen", "king")
        for piece_kind in piece_kinds:
            team_prefix = self.team[0].lower()
            if normalized_id.startswith(f"{team_prefix}_{piece_kind}_"):
                return piece_kind
            if normalized_id == f"{team_prefix}_{piece_kind}":
                return piece_kind
        raise ValueError(f"Unable to infer piece kind from id: {self.id}")

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
