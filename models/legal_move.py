from __future__ import annotations

from dataclasses import dataclass

from .position import Position


@dataclass(frozen=True)
class LegalMove:
    target: Position
    occupied: bool
    capture: bool
    enemy_attack_count: int
    friendly_defense_count: int
    promotion_kind: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target.to_dict(),
            "occupied": self.occupied,
            "capture": self.capture,
            "enemy_attack_count": self.enemy_attack_count,
            "friendly_defense_count": self.friendly_defense_count,
            "promotion_kind": self.promotion_kind,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "LegalMove":
        target_data = data["target"]
        if not isinstance(target_data, dict):
            raise TypeError("legal move target must be a dict")

        promotion_kind = data.get("promotion_kind")
        return cls(
            target=Position.from_dict(target_data),
            occupied=bool(data["occupied"]),
            capture=bool(data["capture"]),
            enemy_attack_count=int(data["enemy_attack_count"]),
            friendly_defense_count=int(data["friendly_defense_count"]),
            promotion_kind=str(promotion_kind) if promotion_kind is not None else None,
        )
