from __future__ import annotations

from dataclasses import dataclass

from .position import Position


@dataclass(frozen=True)
class Action:
    type: str
    piece_id: str | None = None
    target: Position | None = None

    @classmethod
    def wait(cls) -> "Action":
        return cls(type="wait")

    @classmethod
    def move(cls, piece_id: str, target: Position) -> "Action":
        return cls(type="move", piece_id=piece_id, target=target)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "type": self.type,
            "piece_id": self.piece_id,
            "target": None,
        }
        if self.target is not None:
            data["target"] = self.target.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Action":
        target_data = data.get("target")
        target = None
        if isinstance(target_data, dict):
            target = Position.from_dict(target_data)

        piece_id = data.get("piece_id")
        return cls(
            type=str(data["type"]),
            piece_id=str(piece_id) if piece_id is not None else None,
            target=target,
        )
