from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from models import Action, Event, LegalMove, Observation, Piece, Position
from .board import Board


@dataclass
class GameState:
    board: Board = field(default_factory=Board)
    pieces: dict[str, Piece] = field(default_factory=dict)
    teams: tuple[str, ...] = ("white", "black")
    active_team_index: int = 0
    turn: int = 0
    is_finished: bool = False
    winner: str | None = None
    termination_reason: str | None = None
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
            piece_id: Piece(piece.id, piece.team, piece.position, piece.kind_name)
            for piece_id, piece in self.pieces.items()
            if piece.team == team
        }
        visible_positions = self._visible_positions(own_pieces.values())
        legal_moves_by_piece = (
            self.legal_moves_for_team(team) if team == self.active_team and not self.is_finished else {}
        )
        attack_counts = self.attack_count_by_square(team)
        defense_counts = self.defense_count_by_square(team)

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
            legal_moves_by_piece=legal_moves_by_piece,
            attack_count_by_square=self._serialize_square_counts(attack_counts),
            defense_count_by_square=self._serialize_square_counts(defense_counts),
            is_in_check=self.is_in_check(team),
            is_checkmate=self.is_checkmate(team),
            is_stalemate=self.is_stalemate(team),
        )

    def observation_for_piece(self, piece_id: str) -> Observation:
        piece = self.pieces.get(piece_id)
        if piece is None:
            raise ValueError(f"unknown piece id: {piece_id}")

        own_piece = Piece(piece.id, piece.team, piece.position, piece.kind_name)
        visible_positions = self._visible_positions([own_piece])
        legal_moves = (
            {piece_id: self.legal_moves_for_piece(piece_id)}
            if piece.team == self.active_team and not self.is_finished
            else {}
        )
        attack_counts = self.attack_count_by_square(piece.team)
        defense_counts = self.defense_count_by_square(piece.team)
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
            legal_moves_by_piece=legal_moves,
            attack_count_by_square=self._serialize_square_counts(attack_counts),
            defense_count_by_square=self._serialize_square_counts(defense_counts),
            is_in_check=self.is_in_check(piece.team),
            is_checkmate=self.is_checkmate(piece.team),
            is_stalemate=self.is_stalemate(piece.team),
        )

    def step(self, action: Action | None = None) -> Event:
        """Apply one explicit action and advance exactly one turn."""
        action = action or Action.wait()
        if self.is_finished:
            event = self._event(action, "ignored", "game is finished")
            self.event_log.append(event)
            return event

        self._refresh_terminal_status(self.active_team)
        if self.is_finished:
            event = self._event(action, "ignored", self.termination_reason)
            self.event_log.append(event)
            return event

        event = self._apply_action(action)
        self.event_log.append(event)
        self.turn += 1
        self.active_team_index = (self.active_team_index + 1) % len(self.teams)
        self._refresh_terminal_status(self.active_team)
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
        if piece.kind == "pawn" and action.target.row in (0, self.board.size - 1):
            piece.kind_name = "queen"
        return self._event(action, "applied")

    def is_action_valid(self, action: Action) -> bool:
        return self.explain_action(action)[0]

    def explain_action(self, action: Action) -> tuple[bool, str]:
        if action.type == "wait":
            if self.legal_moves_for_team(self.active_team):
                return False, "wait is only allowed when no legal chess moves remain"
            return True, "wait is only legal when the side to move has no legal moves"
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

        legal_targets = {
            (move.target.row, move.target.col): move
            for move in self.legal_moves_for_piece(piece.id)
        }
        legal_move = legal_targets.get((action.target.row, action.target.col))
        if legal_move is None:
            return False, "move is not legal for that piece in the current position"
        if legal_move.capture and occupant is None:
            return False, "capture target is no longer occupied"
        return True, "legal move"

    def legal_moves_for_team(self, team: str) -> dict[str, list[LegalMove]]:
        return {
            piece.id: self.legal_moves_for_piece(piece.id)
            for piece in sorted(self.pieces.values(), key=lambda current_piece: current_piece.id)
            if piece.team == team
        }

    def legal_moves_for_piece(self, piece_id: str) -> list[LegalMove]:
        piece = self.pieces.get(piece_id)
        if piece is None:
            return []
        if piece.team != self.active_team:
            return []

        pseudo_targets = self._pseudo_legal_targets(piece)
        legal_targets: list[tuple[Position, str | None]] = []
        for target, promotion_kind in pseudo_targets:
            simulated_pieces = self._simulate_move(piece.id, target, promotion_kind)
            if not self._is_in_check_on_board(piece.team, simulated_pieces):
                legal_targets.append((target, promotion_kind))

        enemy_counts = self.attack_count_by_square(self._opponent_of(piece.team))
        friendly_counts = self.defense_count_by_square(piece.team)
        moves: list[LegalMove] = []
        for target, promotion_kind in sorted(legal_targets, key=lambda item: (item[0].row, item[0].col)):
            occupant = self.get_piece_at(target)
            capture = occupant is not None and occupant.team != piece.team
            moves.append(
                LegalMove(
                    target=target,
                    occupied=occupant is not None,
                    capture=capture,
                    enemy_attack_count=enemy_counts.get((target.row, target.col), 0),
                    friendly_defense_count=friendly_counts.get((target.row, target.col), 0),
                    promotion_kind=promotion_kind,
                )
            )
        return moves

    def attacked_squares_by_team(self, team: str) -> set[tuple[int, int]]:
        return set(self.attack_count_by_square(team))

    def defended_squares_by_team(self, team: str) -> set[tuple[int, int]]:
        return set(self.defense_count_by_square(team))

    def attack_count_by_square(self, team: str) -> dict[tuple[int, int], int]:
        return self._square_control_counts(team)

    def defense_count_by_square(self, team: str) -> dict[tuple[int, int], int]:
        return self._square_control_counts(team)

    def is_in_check(self, team: str) -> bool:
        return self._is_in_check_on_board(team, self.pieces)

    def has_any_legal_moves(self, team: str) -> bool:
        current_active_team = self.active_team
        if team == current_active_team:
            return any(self.legal_moves_for_piece(piece.id) for piece in self.pieces.values() if piece.team == team)

        simulated_state = GameState.from_dict(self.to_dict())
        simulated_state.active_team_index = simulated_state.teams.index(team)
        return any(
            simulated_state.legal_moves_for_piece(piece.id)
            for piece in simulated_state.pieces.values()
            if piece.team == team
        )

    def is_checkmate(self, team: str) -> bool:
        return self.is_in_check(team) and not self.has_any_legal_moves(team)

    def is_stalemate(self, team: str) -> bool:
        return not self.is_in_check(team) and not self.has_any_legal_moves(team)

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

    def _pseudo_legal_targets(self, piece: Piece) -> list[tuple[Position, str | None]]:
        kind = piece.kind
        if kind == "pawn":
            return self._pawn_targets(piece)
        if kind == "knight":
            return self._jump_targets(piece, ((2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)))
        if kind == "bishop":
            return self._sliding_targets(piece, ((1, 1), (1, -1), (-1, 1), (-1, -1)))
        if kind == "rook":
            return self._sliding_targets(piece, ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if kind == "queen":
            return self._sliding_targets(piece, ((1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)))
        if kind == "king":
            # TODO: castling is intentionally not implemented yet.
            return self._jump_targets(piece, ((1, 1), (1, 0), (1, -1), (0, 1), (0, -1), (-1, 1), (-1, 0), (-1, -1)))
        return []

    def _pawn_targets(self, piece: Piece) -> list[tuple[Position, str | None]]:
        moves: list[tuple[Position, str | None]] = []
        direction = 1 if piece.team == "white" else -1
        start_row = 1 if piece.team == "white" else self.board.size - 2
        promotion_row = self.board.size - 1 if piece.team == "white" else 0

        one_step = Position(row=piece.position.row + direction, col=piece.position.col)
        if self.board.contains(one_step) and self.get_piece_at(one_step) is None:
            moves.append((one_step, "queen" if one_step.row == promotion_row else None))
            two_step = Position(row=piece.position.row + (2 * direction), col=piece.position.col)
            if piece.position.row == start_row and self.board.contains(two_step) and self.get_piece_at(two_step) is None:
                moves.append((two_step, None))

        for col_delta in (-1, 1):
            target = Position(row=piece.position.row + direction, col=piece.position.col + col_delta)
            if not self.board.contains(target):
                continue
            occupant = self.get_piece_at(target)
            if occupant is None or occupant.team == piece.team:
                continue
            moves.append((target, "queen" if target.row == promotion_row else None))

        # TODO: en passant is intentionally not implemented yet.
        return moves

    def _jump_targets(
        self, piece: Piece, offsets: tuple[tuple[int, int], ...]
    ) -> list[tuple[Position, str | None]]:
        moves: list[tuple[Position, str | None]] = []
        for row_delta, col_delta in offsets:
            target = Position(row=piece.position.row + row_delta, col=piece.position.col + col_delta)
            if not self.board.contains(target):
                continue
            occupant = self.get_piece_at(target)
            if occupant is not None and occupant.team == piece.team:
                continue
            moves.append((target, None))
        return moves

    def _sliding_targets(
        self, piece: Piece, directions: tuple[tuple[int, int], ...]
    ) -> list[tuple[Position, str | None]]:
        moves: list[tuple[Position, str | None]] = []
        for row_step, col_step in directions:
            current_row = piece.position.row + row_step
            current_col = piece.position.col + col_step
            while self.board.contains(Position(row=current_row, col=current_col)):
                target = Position(row=current_row, col=current_col)
                occupant = self.get_piece_at(target)
                if occupant is None:
                    moves.append((target, None))
                else:
                    if occupant.team != piece.team:
                        moves.append((target, None))
                    break
                current_row += row_step
                current_col += col_step
        return moves

    def _square_control_counts(self, team: str) -> dict[tuple[int, int], int]:
        counts: dict[tuple[int, int], int] = {}
        for piece in self.pieces.values():
            if piece.team != team:
                continue
            for position in self._attacked_positions_for_piece(piece):
                square = (position.row, position.col)
                counts[square] = counts.get(square, 0) + 1
        return counts

    def _attacked_positions_for_piece(self, piece: Piece) -> list[Position]:
        kind = piece.kind
        if kind == "pawn":
            direction = 1 if piece.team == "white" else -1
            attacks: list[Position] = []
            for col_delta in (-1, 1):
                target = Position(row=piece.position.row + direction, col=piece.position.col + col_delta)
                if self.board.contains(target):
                    attacks.append(target)
            return attacks
        if kind == "knight":
            return self._attack_jump_positions(piece, ((2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)))
        if kind == "bishop":
            return self._attack_sliding_positions(piece, ((1, 1), (1, -1), (-1, 1), (-1, -1)))
        if kind == "rook":
            return self._attack_sliding_positions(piece, ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if kind == "queen":
            return self._attack_sliding_positions(piece, ((1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)))
        if kind == "king":
            # TODO: castling is intentionally not implemented yet.
            return self._attack_jump_positions(piece, ((1, 1), (1, 0), (1, -1), (0, 1), (0, -1), (-1, 1), (-1, 0), (-1, -1)))
        return []

    def _attack_jump_positions(
        self, piece: Piece, offsets: tuple[tuple[int, int], ...]
    ) -> list[Position]:
        positions: list[Position] = []
        for row_delta, col_delta in offsets:
            target = Position(row=piece.position.row + row_delta, col=piece.position.col + col_delta)
            if target.is_on_board(self.board.size):
                positions.append(target)
        return positions

    def _attack_sliding_positions(
        self, piece: Piece, directions: tuple[tuple[int, int], ...]
    ) -> list[Position]:
        positions: list[Position] = []
        for row_step, col_step in directions:
            current_row = piece.position.row + row_step
            current_col = piece.position.col + col_step
            while self.board.contains(Position(row=current_row, col=current_col)):
                target = Position(row=current_row, col=current_col)
                positions.append(target)
                if self.get_piece_at(target) is not None:
                    break
                current_row += row_step
                current_col += col_step
        return positions

    def _is_in_check_on_board(self, team: str, pieces: dict[str, Piece]) -> bool:
        king = next((piece for piece in pieces.values() if piece.team == team and piece.kind == "king"), None)
        if king is None:
            return True

        enemy_team = self._opponent_of(team)
        for piece in pieces.values():
            if piece.team != enemy_team:
                continue
            for position in self._attacked_positions_for_piece_on_board(piece, pieces):
                if position == king.position:
                    return True
        return False

    def _attacked_positions_for_piece_on_board(
        self, piece: Piece, pieces: dict[str, Piece]
    ) -> list[Position]:
        if piece.kind == "pawn":
            direction = 1 if piece.team == "white" else -1
            positions: list[Position] = []
            for col_delta in (-1, 1):
                target = Position(row=piece.position.row + direction, col=piece.position.col + col_delta)
                if target.is_on_board(self.board.size):
                    positions.append(target)
            return positions
        if piece.kind == "knight":
            return self._jump_positions_on_board(piece, pieces, ((2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)), ignore_occupancy=True)
        if piece.kind == "bishop":
            return self._sliding_positions_on_board(piece, pieces, ((1, 1), (1, -1), (-1, 1), (-1, -1)))
        if piece.kind == "rook":
            return self._sliding_positions_on_board(piece, pieces, ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if piece.kind == "queen":
            return self._sliding_positions_on_board(piece, pieces, ((1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)))
        if piece.kind == "king":
            return self._jump_positions_on_board(piece, pieces, ((1, 1), (1, 0), (1, -1), (0, 1), (0, -1), (-1, 1), (-1, 0), (-1, -1)), ignore_occupancy=True)
        return []

    def _jump_positions_on_board(
        self,
        piece: Piece,
        pieces: dict[str, Piece],
        offsets: tuple[tuple[int, int], ...],
        ignore_occupancy: bool = False,
    ) -> list[Position]:
        positions: list[Position] = []
        for row_delta, col_delta in offsets:
            target = Position(row=piece.position.row + row_delta, col=piece.position.col + col_delta)
            if not target.is_on_board(self.board.size):
                continue
            occupant = self._get_piece_at_from_map(pieces, target)
            if ignore_occupancy or occupant is None or occupant.team != piece.team:
                positions.append(target)
        return positions

    def _sliding_positions_on_board(
        self, piece: Piece, pieces: dict[str, Piece], directions: tuple[tuple[int, int], ...]
    ) -> list[Position]:
        positions: list[Position] = []
        for row_step, col_step in directions:
            current_row = piece.position.row + row_step
            current_col = piece.position.col + col_step
            while Position(row=current_row, col=current_col).is_on_board(self.board.size):
                target = Position(row=current_row, col=current_col)
                positions.append(target)
                if self._get_piece_at_from_map(pieces, target) is not None:
                    break
                current_row += row_step
                current_col += col_step
        return positions

    def _simulate_move(
        self, piece_id: str, target: Position, promotion_kind: str | None
    ) -> dict[str, Piece]:
        pieces = {
            current_piece_id: Piece(
                id=current_piece.id,
                team=current_piece.team,
                position=Position(row=current_piece.position.row, col=current_piece.position.col),
                kind_name=current_piece.kind_name,
            )
            for current_piece_id, current_piece in self.pieces.items()
        }
        mover = pieces[piece_id]
        captured_piece = self._get_piece_at_from_map(pieces, target)
        if captured_piece is not None and captured_piece.id != mover.id:
            del pieces[captured_piece.id]
        mover.position = target
        if promotion_kind is not None:
            mover.kind_name = promotion_kind
        return pieces

    def _get_piece_at_from_map(
        self, pieces: dict[str, Piece], position: Position
    ) -> Piece | None:
        for piece in pieces.values():
            if piece.position == position:
                return piece
        return None

    def _refresh_terminal_status(self, team: str) -> None:
        if self.is_checkmate(team):
            self.is_finished = True
            self.winner = self._opponent_of(team)
            self.termination_reason = f"{team} is checkmated"
            return
        if self.is_stalemate(team):
            self.is_finished = True
            self.winner = None
            self.termination_reason = f"{team} is stalemated"
            return
        self.is_finished = False
        self.winner = None
        self.termination_reason = None

    def _serialize_square_counts(
        self, counts: dict[tuple[int, int], int]
    ) -> dict[str, int]:
        return {
            f"{chr(ord('a') + col)}{row + 1}": count
            for (row, col), count in sorted(counts.items())
        }

    def _opponent_of(self, team: str) -> str:
        for candidate in self.teams:
            if candidate != team:
                return candidate
        raise ValueError(f"no opposing team configured for {team}")

    def to_dict(self) -> dict[str, object]:
        return {
            "board": {"size": self.board.size},
            "pieces": {
                piece_id: piece.to_dict()
                for piece_id, piece in sorted(self.pieces.items())
            },
            "teams": list(self.teams),
            "active_team_index": self.active_team_index,
            "turn": self.turn,
            "is_finished": self.is_finished,
            "winner": self.winner,
            "termination_reason": self.termination_reason,
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
            winner=str(data["winner"]) if data.get("winner") is not None else None,
            termination_reason=(
                str(data["termination_reason"])
                if data.get("termination_reason") is not None
                else None
            ),
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
