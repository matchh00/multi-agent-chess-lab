from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
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

        is_valid, reason = self.explain_action(action)
        if not is_valid:
            return self._event(action, "rejected", reason)

        piece = self.pieces[action.piece_id]
        occupant = self.get_piece_at(action.target)
        if occupant is not None and occupant.id != piece.id:
            del self.pieces[occupant.id]

        piece.position = action.target
        return self._event(action, "applied")

    def is_action_valid(self, action: Action) -> bool:
        return self.explain_action(action)[0]

    def explain_action(self, action: Action) -> tuple[bool, str]:
        if action.type == "wait":
            return True, "wait is always legal"
        if action.type != "move":
            return False, f"unknown action type: {action.type}"
        if action.piece_id is None or action.target is None:
            return False, "move requires piece_id and target"

        piece = self.pieces.get(action.piece_id)
        if piece is None:
            return False, f"unknown piece id: {action.piece_id}"
        if piece.team != self.active_team:
            return False, "piece does not belong to active team"
        if not self.board.contains(action.target):
            return False, "target is outside the board"
        if action.target == piece.position:
            return False, "piece must move to a different square"

        occupant = self.get_piece_at(action.target)
        if occupant is not None and occupant.id != piece.id and occupant.team == piece.team:
            return False, "target is occupied by a friendly piece"

        return self._is_legal_piece_move(piece, action.target, occupant)

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

    def _is_legal_piece_move(
        self, piece: Piece, target: Position, occupant: Piece | None
    ) -> tuple[bool, str]:
        row_delta = target.row - piece.position.row
        col_delta = target.col - piece.position.col
        abs_row_delta = abs(row_delta)
        abs_col_delta = abs(col_delta)

        if piece.kind == "pawn":
            return self._is_legal_pawn_move(piece, target, occupant)
        if piece.kind == "knight":
            if (abs_row_delta, abs_col_delta) == (2, 1) or (abs_row_delta, abs_col_delta) == (1, 2):
                return True, "legal knight move"
            return False, "knight must move in an L shape"
        if piece.kind == "bishop":
            if abs_row_delta != abs_col_delta:
                return False, "bishop must move diagonally"
            if not self._path_is_clear(piece.position, target):
                return False, "bishop path is blocked"
            return True, "legal bishop move"
        if piece.kind == "rook":
            if row_delta != 0 and col_delta != 0:
                return False, "rook must move horizontally or vertically"
            if not self._path_is_clear(piece.position, target):
                return False, "rook path is blocked"
            return True, "legal rook move"
        if piece.kind == "queen":
            is_straight = row_delta == 0 or col_delta == 0
            is_diagonal = abs_row_delta == abs_col_delta
            if not is_straight and not is_diagonal:
                return False, "queen must move horizontally, vertically, or diagonally"
            if not self._path_is_clear(piece.position, target):
                return False, "queen path is blocked"
            return True, "legal queen move"
        if piece.kind == "king":
            if max(abs_row_delta, abs_col_delta) == 1:
                return True, "legal king move"
            return False, "king must move one square"

        return False, f"unsupported piece type: {piece.kind}"

    def _is_legal_pawn_move(
        self, piece: Piece, target: Position, occupant: Piece | None
    ) -> tuple[bool, str]:
        direction = 1 if piece.team == "white" else -1
        start_row = 1 if piece.team == "white" else self.board.size - 2
        row_delta = target.row - piece.position.row
        col_delta = target.col - piece.position.col

        if col_delta == 0:
            if occupant is not None and occupant.id != piece.id:
                return False, "pawn cannot move forward into an occupied square"
            if row_delta == direction:
                return True, "legal pawn advance"
            if row_delta == 2 * direction and piece.position.row == start_row:
                intermediate = Position(
                    row=piece.position.row + direction,
                    col=piece.position.col,
                )
                if self.get_piece_at(intermediate) is not None:
                    return False, "pawn double-step is blocked"
                return True, "legal pawn double-step"
            return False, "pawn forward move must be one square, or two from its starting rank"

        if abs(col_delta) == 1 and row_delta == direction:
            if occupant is None or occupant.id == piece.id:
                return False, "pawn diagonal move requires an opposing piece to capture"
            if occupant.team == piece.team:
                return False, "pawn cannot capture a friendly piece"
            return True, "legal pawn capture"

        return False, "illegal pawn movement pattern"

    def _path_is_clear(self, start: Position, target: Position) -> bool:
        row_delta = target.row - start.row
        col_delta = target.col - start.col
        step_size = gcd(abs(row_delta), abs(col_delta))
        if step_size == 0:
            return False

        row_step = row_delta // step_size
        col_step = col_delta // step_size

        current_row = start.row + row_step
        current_col = start.col + col_step
        while (current_row, current_col) != (target.row, target.col):
            if self.get_piece_at(Position(row=current_row, col=current_col)) is not None:
                return False
            current_row += row_step
            current_col += col_step
        return True

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
