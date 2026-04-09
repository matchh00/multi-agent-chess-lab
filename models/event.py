from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Event:
    turn: int
    team: str
    action: dict[str, object]
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Event":
        reason = data.get("reason")
        return cls(
            turn=int(data["turn"]),
            team=str(data["team"]),
            action=dict(data["action"]),
            status=str(data["status"]),
            reason=str(reason) if reason is not None else None,
        )
