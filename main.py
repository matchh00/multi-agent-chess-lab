from __future__ import annotations

import json
import os

from agents import PassiveAgent
from game import GameState
from models import Action, AgentDecision, Observation, Piece, Position, TeamObservationReport


def pretty(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def piece_symbol(piece: Piece | None) -> str:
    if piece is None:
        return ".."
    team_prefix = "W" if piece.team == "white" else "B"
    kind_letter = {
        "pawn": "P",
        "knight": "N",
        "bishop": "B",
        "rook": "R",
        "queen": "Q",
        "king": "K",
    }[piece.kind]
    return f"{team_prefix}{kind_letter}"


def square_name(position: Position) -> str:
    return f"{chr(ord('a') + position.col)}{position.row + 1}"


def render_board(state: GameState) -> str:
    cols = "a b c d e f g h"
    lines = [f"    {cols}", "  +-------------------------+"]
    for row in range(state.board.size - 1, -1, -1):
        cells: list[str] = []
        for col in range(state.board.size):
            piece = state.get_piece_at(Position(row=row, col=col))
            cells.append(piece_symbol(piece))
        lines.append(f"{row + 1} | {' '.join(cells)} |")
    lines.append("  +-------------------------+")
    return "\n".join(lines)


def render_visible_squares(observation: Observation) -> str:
    positions = sorted(
        observation.occupied_positions,
        key=lambda position: (position["row"], position["col"]),
    )
    return pretty(positions)


def report_summary(report: TeamObservationReport) -> dict[str, object]:
    return {
        "active_team": report.active_team,
        "piece_report_count": len(report.piece_reports),
        "visible_square_union_count": len(report.visible_square_union),
        "candidate_move_count": len(report.team_candidate_moves),
    }


def select_team_action(decisions: list[AgentDecision]) -> tuple[AgentDecision | None, str]:
    """Selection policy kept isolated so it can be swapped later."""
    if not decisions:
        return None, "No valid decisions available."
    for decision in decisions:
        if decision.proposed_action.type == "move":
            return decision, "Selected first legal move (preferred over wait)."
    return decisions[0], "Selected first valid decision (simple policy)."


def choose_team_action(
    state: GameState, team: str
) -> tuple[Action, list[AgentDecision], dict[str, object]]:
    piece_ids = sorted(
        [piece.id for piece in state.pieces.values() if piece.team == team]
    )
    decisions: list[AgentDecision] = []
    valid_decisions: list[AgentDecision] = []
    called_piece_ids: list[str] = []
    decision_piece_ids: list[str] = []
    filtered_out_piece_ids: list[str] = []
    decision_debug: list[dict[str, object]] = []
    team_report = state.team_report_for(team)

    for piece_id in piece_ids:
        called_piece_ids.append(piece_id)
        agent = PassiveAgent(team=team)
        observation = state.observation_for_piece(piece_id)
        decision = agent.act(observation)
        decisions.append(decision)
        if decision.proposed_action.piece_id is not None:
            decision_piece_ids.append(decision.proposed_action.piece_id)

        is_valid, reason = state.explain_action(decision.proposed_action)
        piece = state.pieces[piece_id]
        target = decision.proposed_action.target
        legal_moves = observation.legal_moves_by_piece.get(piece_id, [])
        decision_debug.append(
            {
                "piece_id": piece_id,
                "piece_kind": piece.kind,
                "from": square_name(piece.position),
                "legal_move_count": len(legal_moves),
                "legal_moves": [move.to_dict() for move in legal_moves],
                "proposed_action": decision.proposed_action.to_dict(),
                "target_square": square_name(target) if target is not None else None,
                "is_valid": is_valid,
                "reason": reason,
            }
        )

    valid_piece_ids: list[str] = []
    for piece_id, decision in zip(piece_ids, decisions):
        if state.is_action_valid(decision.proposed_action):
            valid_decisions.append(decision)
            valid_piece_ids.append(piece_id)
            continue
        filtered_out_piece_ids.append(piece_id)

    selected_decision, selection_reason = select_team_action(valid_decisions)
    selected_action = (
        selected_decision.proposed_action if selected_decision is not None else Action.wait()
    )
    selected_piece_id = selected_action.piece_id

    return selected_action, decisions, {
        "active_team_piece_ids": piece_ids,
        "sample_piece_report": (
            team_report.piece_reports[0].to_dict() if team_report.piece_reports else None
        ),
        "team_report_summary": report_summary(team_report),
        "team_report": team_report.to_dict(),
        "called_piece_ids": called_piece_ids,
        "decision_piece_ids": decision_piece_ids,
        "valid_piece_ids": valid_piece_ids,
        "filtered_out_piece_ids": filtered_out_piece_ids,
        "selected_piece_id": selected_piece_id,
        "selection_reason": selection_reason,
        "decision_debug": decision_debug,
        "team_legal_move_total": sum(item["legal_move_count"] for item in decision_debug),
    }


def add_standard_chess_pieces(state: GameState) -> None:
    back_rank = ("rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook")

    for col, kind in enumerate(back_rank):
        state.add_piece(
            Piece(
                id=f"w_{kind}_{col + 1}",
                team="white",
                position=Position(row=0, col=col),
            )
        )
        state.add_piece(
            Piece(
                id=f"b_{kind}_{col + 1}",
                team="black",
                position=Position(row=7, col=col),
            )
        )

    for col in range(state.board.size):
        state.add_piece(
            Piece(
                id=f"w_pawn_{col + 1}",
                team="white",
                position=Position(row=1, col=col),
            )
        )
        state.add_piece(
            Piece(
                id=f"b_pawn_{col + 1}",
                team="black",
                position=Position(row=6, col=col),
            )
        )


def main() -> None:
    # 1) Initialize game state.
    state = GameState()

    # 2) Add a full standard chess setup.
    add_standard_chess_pieces(state)

    # 3) Run three turns, printing a readable trace each turn.
    total_turns = 3
    verbose_reports = os.environ.get("CHESS_REPORT_VERBOSE", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    for turn_number in range(1, total_turns + 1):
        active_team = state.active_team

        print(f"\n=== Turn {turn_number} ({active_team}) ===")
        print("Board (Before Step):")
        print(render_board(state))

        chosen_action, decisions, debug = choose_team_action(state, active_team)
        team_observation = state.observation_for(active_team)

        print("\nVisible Occupied Squares:")
        print(render_visible_squares(team_observation))
        print("\nTeam Report Summary:")
        print(pretty(debug["team_report_summary"]))
        print("\nDebug (Piece-Agent Flow):")
        print(f"active-team piece ids: {debug['active_team_piece_ids']}")
        print(f"agent calls for piece ids: {debug['called_piece_ids']}")
        print(f"decisions returned for piece ids: {debug['decision_piece_ids']}")
        print(f"valid for selection: {debug['valid_piece_ids']}")
        print(
            "filtered out before team selection: "
            f"{debug['filtered_out_piece_ids']}"
        )
        print(
            f"selected decision piece id: {debug['selected_piece_id']} "
            f"({debug['selection_reason']})"
        )
        print(f"team legal move total: {debug['team_legal_move_total']}")
        if verbose_reports:
            print("\nSample Piece Report:")
            print(pretty(debug["sample_piece_report"]))
            print("\nFull Team Report:")
            print(pretty(debug["team_report"]))
        print("\nPiece Agent Decisions:")
        print(pretty([decision.to_dict() for decision in decisions]))
        print("\nDecision Legality:")
        print(pretty(debug["decision_debug"]))
        print("\nStatus Before Step:")
        print(
            pretty(
                {
                    "active_team": active_team,
                    "is_in_check": state.is_in_check(active_team),
                    "is_checkmate": state.is_checkmate(active_team),
                    "is_stalemate": state.is_stalemate(active_team),
                }
            )
        )
        print("\nChosen Team Action:")
        print(pretty(chosen_action.to_dict()))
        chosen_validity, chosen_reason = state.explain_action(chosen_action)
        print(
            f"Chosen action legal before apply: {chosen_validity} "
            f"({chosen_reason})"
        )

        event = state.step(chosen_action)
        print("\nStep Event:")
        print(pretty(event.to_dict()))

        print("\nBoard (After Step):")
        print(render_board(state))
        print("\nStatus After Step:")
        print(
            pretty(
                {
                    "next_active_team": state.active_team,
                    "is_finished": state.is_finished,
                    "winner": state.winner,
                    "termination_reason": state.termination_reason,
                    "is_in_check": state.is_in_check(state.active_team),
                    "is_checkmate": state.is_checkmate(state.active_team),
                    "is_stalemate": state.is_stalemate(state.active_team),
                }
            )
        )
        if state.is_finished:
            break

    # 4) Print final summary after all turns.
    print("\n=== Final State ===")
    print(pretty(state.to_dict()))

    print("\n=== Event Log ===")
    print(pretty([event.to_dict() for event in state.event_log]))


if __name__ == "__main__":
    main()
