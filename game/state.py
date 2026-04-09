from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from models import Action, Event, Observation, Piece, Position
from .board import Board


@dataclass
class GameState:
    board: Board = field(default_factory=Board)
    pieces: dict[str, Piece] = field(default_factory=dict)
    teams: tuple[str, ...] = ("white", "black")
    active_team_index: int = 0
    turn: int = 0
    is_finished: bool = False
    seed: int | None = None
    event_log: list[Event] = field(default_factory=list)

    @property
    def active_team(self) -> str:
        return self.teams[self.active_team_index]

    def add_piece(self, piece: Piece) -> None:
        if not self.board.contains(piece.position):
            raise ValueError(f"Piece {piece.id} is outside the board: {piece.position}")
        if self.get_piece_at(piece.position) is not None:
            raise ValueError(f"Position is already occupied: {piece.position}")

        self.pieces[piece.id] = piece

    def get_piece_at(self, position: Position) -> Piece | None:
        return self.board.get_piece_at(self.pieces, position)

    def as_grid(self) -> list[list[str | None]]:
        return self.board.as_grid(self.pieces)

    def observation_for(self, team: str) -> Observation:
        own_pieces = {
            piece_id: Piece(piece.id, piece.team, piece.position)
            for piece_id, piece in self.pieces.items()
            if piece.team == team
        }
        visible_positions = self._visible_positions(own_pieces.values())

        return Observation(
            team=team,
            turn=self.turn,
            active_team=self.active_team,
            board_size=self.board.size,
            own_pieces=own_pieces,
            occupied_positions=[
                piece.position.to_dict()
                for piece in sorted(self.pieces.values(), key=lambda item: item.id)
                if (piece.position.row, piece.position.col) in visible_positions
            ],
        )

    def observation_for_piece(self, piece_id: str) -> Observation:
        piece = self.pieces.get(piece_id)
        if piece is None:
            raise ValueError(f"unknown piece id: {piece_id}")

        own_piece = Piece(piece.id, piece.team, piece.position)
        visible_positions = self._visible_positions([own_piece])
        return Observation(
            team=piece.team,
            turn=self.turn,
            active_team=self.active_team,
            board_size=self.board.size,
            own_pieces={own_piece.id: own_piece},
            occupied_positions=[
                current_piece.position.to_dict()
                for current_piece in sorted(self.pieces.values(), key=lambda item: item.id)
                if (current_piece.position.row, current_piece.position.col) in visible_positions
            ],
        )

    def step(self, action: Action | None = None) -> Event:
        """Apply one explicit action and advance exactly one turn."""
        action = action or Action.wait()
        if self.is_finished:
            event = self._event(action, "ignored", "game is finished")
            self.event_log.append(event)
            return event

        event = self._apply_action(action)
        self.event_log.append(event)
        self.turn += 1
        self.active_team_index = (self.active_team_index + 1) % len(self.teams)
        return event

    def _apply_action(self, action: Action) -> Event:
        if action.type == "wait":
            return self._event(action, "applied")

        if action.type != "move":
            return self._event(action, "rejected", f"unknown action type: {action.type}")
        if action.piece_id is None or action.target is None:
            return self._event(action, "rejected", "move requires piece_id and target")

        piece = self.pieces.get(action.piece_id)
        if piece is None:
            return self._event(action, "rejected", f"unknown piece id: {action.piece_id}")
        if piece.team != self.active_team:
            return self._event(action, "rejected", "piece does not belong to active team")
        if not self.board.contains(action.target):
            return self._event(action, "rejected", "target is outside the board")

        occupant = self.get_piece_at(action.target)
        if occupant is not None and occupant.id != piece.id:
            return self._event(action, "rejected", "target is occupied")

        piece.position = action.target
        return self._event(action, "applied")

    def is_action_valid(self, action: Action) -> bool:
        if action.type == "wait":
            return True
        if action.type != "move":
            return False
        if action.piece_id is None or action.target is None:
            return False

        piece = self.pieces.get(action.piece_id)
        if piece is None:
            return False
        if piece.team != self.active_team:
            return False
        if not self.board.contains(action.target):
            return False

        occupant = self.get_piece_at(action.target)
        return occupant is None or occupant.id == piece.id

    def _visible_positions(self, pieces: Iterable[Piece]) -> set[tuple[int, int]]:
        return {
            (row, col)
            for piece in pieces
            for row in range(piece.position.row - 2, piece.position.row + 3)
            for col in range(piece.position.col - 2, piece.position.col + 3)
            if self.board.contains(Position(row=row, col=col))
        }

    def _event(self, action: Action, status: str, reason: str | None = None) -> Event:
        return Event(
            turn=self.turn,
            team=self.active_team,
            action=action.to_dict(),
            status=status,
            reason=reason,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "board": {"size": self.board.size},
            "pieces": {
                piece_id: {
                    "id": piece.id,
                    "team": piece.team,
                    "position": piece.position.to_dict(),
                }
                for piece_id, piece in sorted(self.pieces.items())
            },
            "teams": list(self.teams),
            "active_team_index": self.active_team_index,
            "turn": self.turn,
            "is_finished": self.is_finished,
            "seed": self.seed,
            "event_log": [event.to_dict() for event in self.event_log],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "GameState":
        board_data = data.get("board", {})
        if not isinstance(board_data, dict):
            raise TypeError("board must be a dict")

        pieces_data = data.get("pieces", {})
        if not isinstance(pieces_data, dict):
            raise TypeError("pieces must be a dict")

        event_log_data = data.get("event_log", [])
        if not isinstance(event_log_data, list):
            raise TypeError("event_log must be a list")

        teams_data = data.get("teams", ("white", "black"))
        if not isinstance(teams_data, (list, tuple)):
            raise TypeError("teams must be a list or tuple")

        return cls(
            board=Board(size=int(board_data.get("size", 8))),
            pieces={
                str(piece_id): Piece.from_dict(piece_data)
                for piece_id, piece_data in pieces_data.items()
                if isinstance(piece_data, dict)
            },
            teams=tuple(str(team) for team in teams_data),
            active_team_index=int(data.get("active_team_index", 0)),
            turn=int(data.get("turn", 0)),
            is_finished=bool(data.get("is_finished", False)),
            seed=data.get("seed") if data.get("seed") is None else int(data["seed"]),
            event_log=[
                Event.from_dict(event_data)
                for event_data in event_log_data
                if isinstance(event_data, dict)
            ],
        )

    @classmethod
    def replay(
        cls, initial_state: "GameState", actions: list[Action]
    ) -> "GameState":
        state = cls.from_dict(initial_state.to_dict())
        state.event_log = []
        for action in actions:
            state.step(action)
        return state
