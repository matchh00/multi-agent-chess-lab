from __future__ import annotations

import json

from agents import PassiveAgent
from game import GameState
from models import Observation, Piece, Position


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


def main() -> None:
    # 1) Initialize game state.
    state = GameState()

    # 2) Add a few pieces.
    state.add_piece(Piece(id="w_pawn_1", team="white", position=Position(row=1, col=0)))
    state.add_piece(Piece(id="w_knight_1", team="white", position=Position(row=0, col=1)))
    state.add_piece(Piece(id="b_pawn_1", team="black", position=Position(row=6, col=0)))

    # Use a simple stub agent for the currently active team.
    agent = PassiveAgent(team=state.active_team)

    # 3) Build observation and run one decision/step.
    observation = state.observation_for(agent.team)
    decision = agent.act(observation)

    print("=== Board (Before Step) ===")
    print(render_board(state))

    state.step(decision.proposed_action)

    # 4) Print all requested outputs.
    print("=== Observation ===")
    print(pretty(observation.to_dict()))

    print(f"\n=== Visible Occupied Squares ({agent.team}) ===")
    print(render_visible_squares(observation))

    print("\n=== Agent Decision ===")
    print(pretty(decision.to_dict()))

    print("\n=== Resulting State ===")
    print(pretty(state.to_dict()))

    print("\n=== Event Log ===")
    print(pretty([event.to_dict() for event in state.event_log]))

    print("\n=== Board (After Step) ===")
    print(render_board(state))


if __name__ == "__main__":
    main()
