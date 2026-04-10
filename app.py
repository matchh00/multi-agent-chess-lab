"""Streamlit UI for multi-agent chess lab — game logic lives in `game/` and `main.py`."""

from __future__ import annotations

import json

import streamlit as st

from game import GameState
from main import add_standard_chess_pieces, choose_team_action, piece_symbol, square_name
from models import Action, Position


def _format_action(action: Action) -> str:
    if action.type == "wait":
        return "wait"
    if action.type == "move" and action.target is not None:
        dest = square_name(action.target)
        return f"move {action.piece_id} → {dest}"
    return json.dumps(action.to_dict(), sort_keys=True)


def _new_game() -> GameState:
    state = GameState()
    add_standard_chess_pieces(state)
    return state


def _ensure_session() -> None:
    if "game" not in st.session_state:
        st.session_state.game = _new_game()
    if "last_action" not in st.session_state:
        st.session_state.last_action = None
    if "last_debug" not in st.session_state:
        st.session_state.last_debug = None


def _reset() -> None:
    st.session_state.game = _new_game()
    st.session_state.last_action = None
    st.session_state.last_debug = None


def _next_turn() -> None:
    state: GameState = st.session_state.game
    if state.is_finished:
        return
    active = state.active_team
    chosen_action, _, debug = choose_team_action(state, active)
    st.session_state.last_action = chosen_action
    st.session_state.last_debug = debug
    state.step(chosen_action)


def _render_board(state: GameState) -> None:
    """Draw an 8×8 grid with piece symbols (WR, BP, ..)."""
    size = state.board.size
    light = "#f0d9b5"
    dark = "#b58863"

    header_cols = st.columns([0.45] + [1.0] * size)
    header_cols[0].write("")
    for col in range(size):
        header_cols[col + 1].markdown(
            f"<div style='text-align:center;font-weight:600'>{chr(ord('a') + col)}</div>",
            unsafe_allow_html=True,
        )

    for row in range(size - 1, -1, -1):
        cols = st.columns([0.45] + [1.0] * size)
        cols[0].markdown(
            f"<div style='text-align:right;padding-top:10px;font-weight:600'>{row + 1}</div>",
            unsafe_allow_html=True,
        )
        for col in range(size):
            piece = state.get_piece_at(Position(row=row, col=col))
            label = piece_symbol(piece)
            bg = light if (row + col) % 2 == 0 else dark
            cols[col + 1].markdown(
                f"<div style='text-align:center;padding:10px 4px;border-radius:4px;"
                f"background:{bg};font-family:ui-monospace,Menlo,monospace;font-size:1.1rem;"
                f"font-weight:600;color:#111'>{label}</div>",
                unsafe_allow_html=True,
            )


def main() -> None:
    st.set_page_config(page_title="Multi-agent Chess Lab", layout="centered")
    _ensure_session()

    st.title("Multi-agent Chess Lab")
    st.caption("Passive agents propose moves; one team action is selected and applied per step.")

    col_left, col_right = st.columns(2)
    with col_left:
        if st.button("Reset Game", type="secondary"):
            _reset()
    with col_right:
        next_clicked = st.button("Next Turn", type="primary")

    if next_clicked:
        _next_turn()

    state: GameState = st.session_state.game
    last: Action | None = st.session_state.last_action
    last_debug: dict[str, object] | None = st.session_state.last_debug

    st.divider()
    st.subheader("Status")
    st.write(f"**Active team:** {state.active_team}")
    st.write(f"**Turn counter:** {state.turn} (increments after each step)")
    st.write(f"**Finished:** {state.is_finished}")
    if state.winner is not None:
        st.write(f"**Winner:** {state.winner}")
    if state.termination_reason is not None:
        st.write(f"**End reason:** {state.termination_reason}")
    st.write(f"**Check on active team:** {state.is_in_check(state.active_team)}")
    st.write(f"**Checkmate on active team:** {state.is_checkmate(state.active_team)}")
    st.write(f"**Stalemate on active team:** {state.is_stalemate(state.active_team)}")
    if last is not None:
        st.write(f"**Chosen action:** {_format_action(last)}")
    else:
        st.write("**Chosen action:** — (no step yet)")
    if last_debug is not None:
        st.write(f"**Acting team legal move total:** {last_debug.get('team_legal_move_total', 0)}")

    st.divider()
    st.subheader("Board")
    _render_board(state)

    st.divider()
    st.subheader("Current Legal Move Counts")
    move_counts = {
        piece_id: len(moves)
        for piece_id, moves in state.legal_moves_for_team(state.active_team).items()
    }
    st.json(move_counts)

    st.divider()
    st.subheader("Current Square Control")
    st.json(
        {
            "attack_count_by_square": state.observation_for(state.active_team).attack_count_by_square,
            "defense_count_by_square": state.observation_for(state.active_team).defense_count_by_square,
        }
    )


if __name__ == "__main__":
    main()
