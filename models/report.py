from __future__ import annotations

from dataclasses import dataclass, field

from .legal_move import LegalMove
from .piece import Piece
from .position import Position


@dataclass(frozen=True)
class VisiblePieceReport:
    piece_id: str
    piece_kind: str
    team: str
    position: Position

    @classmethod
    def from_piece(cls, piece: Piece) -> "VisiblePieceReport":
        return cls(
            piece_id=piece.id,
            piece_kind=piece.kind,
            team=piece.team,
            position=piece.position,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "piece_id": self.piece_id,
            "piece_kind": self.piece_kind,
            "team": self.team,
            "position": self.position.to_dict(),
        }


@dataclass(frozen=True)
class LegalCandidateMoveReport:
    piece_id: str
    from_position: Position
    target: Position
    occupied: bool
    capture: bool
    enemy_attack_count: int
    friendly_defense_count: int
    promotion_kind: str | None = None

    @classmethod
    def from_legal_move(
        cls, piece_id: str, from_position: Position, move: LegalMove
    ) -> "LegalCandidateMoveReport":
        return cls(
            piece_id=piece_id,
            from_position=from_position,
            target=move.target,
            occupied=move.occupied,
            capture=move.capture,
            enemy_attack_count=move.enemy_attack_count,
            friendly_defense_count=move.friendly_defense_count,
            promotion_kind=move.promotion_kind,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "piece_id": self.piece_id,
            "from_position": self.from_position.to_dict(),
            "target": self.target.to_dict(),
            "occupied": self.occupied,
            "capture": self.capture,
            "enemy_attack_count": self.enemy_attack_count,
            "friendly_defense_count": self.friendly_defense_count,
            "promotion_kind": self.promotion_kind,
        }


@dataclass(frozen=True)
class PieceObservationReport:
    piece_id: str
    piece_kind: str
    team: str
    current_position: Position
    visible_squares: list[dict[str, int]] = field(default_factory=list)
    visible_allies: list[VisiblePieceReport] = field(default_factory=list)
    visible_enemies: list[VisiblePieceReport] = field(default_factory=list)
    attack_counts_by_square: dict[str, int] = field(default_factory=dict)
    defense_counts_by_square: dict[str, int] = field(default_factory=dict)
    legal_candidate_moves: list[LegalCandidateMoveReport] = field(default_factory=list)
    short_local_note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "piece_id": self.piece_id,
            "piece_kind": self.piece_kind,
            "team": self.team,
            "current_position": self.current_position.to_dict(),
            "visible_squares": list(self.visible_squares),
            "visible_allies": [piece.to_dict() for piece in self.visible_allies],
            "visible_enemies": [piece.to_dict() for piece in self.visible_enemies],
            "attack_counts_by_square": dict(sorted(self.attack_counts_by_square.items())),
            "defense_counts_by_square": dict(sorted(self.defense_counts_by_square.items())),
            "legal_candidate_moves": [move.to_dict() for move in self.legal_candidate_moves],
            "short_local_note": self.short_local_note,
        }


@dataclass(frozen=True)
class TeamObservationReport:
    team: str
    turn: int
    active_team: str
    piece_reports: list[PieceObservationReport] = field(default_factory=list)
    visible_square_union: list[dict[str, int]] = field(default_factory=list)
    team_visible_enemies: list[VisiblePieceReport] = field(default_factory=list)
    team_candidate_moves: list[LegalCandidateMoveReport] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "team": self.team,
            "turn": self.turn,
            "active_team": self.active_team,
            "piece_reports": [report.to_dict() for report in self.piece_reports],
            "visible_square_union": list(self.visible_square_union),
            "team_visible_enemies": [piece.to_dict() for piece in self.team_visible_enemies],
            "team_candidate_moves": [move.to_dict() for move in self.team_candidate_moves],
            "metadata": dict(sorted(self.metadata.items())),
        }
