from __future__ import annotations

import json

from agents import PassiveAgent
from game import GameState
from models import Action, AgentDecision, Observation, Piece, Position


def pretty(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def piece_symbol(piece: Piece | None) -> str:
    if piece is None:
        return ".."
    team_prefix = "W" if piece.team == "white" else "B"
    piece_hint = piece.id.split("_", maxsplit=1)[1] if "_" in piece.id else piece.id
    kind_letter = piece_hint[0].upper() if piece_hint else "?"
    return f"{team_prefix}{kind_letter}"


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


def select_team_action(decisions: list[AgentDecision]) -> tuple[AgentDecision | None, str]:
    """Selection policy kept isolated so it can be swapped later."""
    if not decisions:
        return None, "No valid decisions available."
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

    for piece_id in piece_ids:
        called_piece_ids.append(piece_id)
        agent = PassiveAgent(team=team)
        observation = state.observation_for_piece(piece_id)
        decision = agent.act(observation)
        decisions.append(decision)
        if decision.proposed_action.piece_id is not None:
            decision_piece_ids.append(decision.proposed_action.piece_id)

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
        "called_piece_ids": called_piece_ids,
        "decision_piece_ids": decision_piece_ids,
        "valid_piece_ids": valid_piece_ids,
        "filtered_out_piece_ids": filtered_out_piece_ids,
        "selected_piece_id": selected_piece_id,
        "selection_reason": selection_reason,
    }


def main() -> None:
    # 1) Initialize game state.
    state = GameState()

    # 2) Add a few pieces.
    state.add_piece(Piece(id="w_pawn_1", team="white", position=Position(row=1, col=0)))
    state.add_piece(Piece(id="w_knight_1", team="white", position=Position(row=0, col=1)))
    state.add_piece(Piece(id="b_pawn_1", team="black", position=Position(row=6, col=0)))

    # 3) Run five turns, printing a readable trace each turn.
    total_turns = 5
    for turn_number in range(1, total_turns + 1):
        active_team = state.active_team

        print(f"\n=== Turn {turn_number} ({active_team}) ===")
        print("Board (Before Step):")
        print(render_board(state))

        chosen_action, decisions, debug = choose_team_action(state, active_team)
        team_observation = state.observation_for(active_team)

        print("\nVisible Occupied Squares:")
        print(render_visible_squares(team_observation))
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
        print("\nPiece Agent Decisions:")
        print(pretty([decision.to_dict() for decision in decisions]))
        print("\nChosen Team Action:")
        print(pretty(chosen_action.to_dict()))

        state.step(chosen_action)

        print("\nBoard (After Step):")
        print(render_board(state))

    # 4) Print final summary after all turns.
    print("\n=== Final State ===")
    print(pretty(state.to_dict()))

    print("\n=== Event Log ===")
    print(pretty([event.to_dict() for event in state.event_log]))


if __name__ == "__main__":
    main()
