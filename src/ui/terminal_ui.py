"""
ui/terminal_ui.py

Terminal-based user interface for Battleship.

This module is responsible for:
- displaying info and error messages
- rendering boards in a readable terminal format
- collecting ship placement input
- collecting attack input

It does not contain networking logic or core game rules.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from utils.constants import BOARD_SIZE, SHIP_SIZES


Coord = Tuple[int, int]
ShipPlacement = Tuple[str, int, int, bool]


class TerminalUI:

    def show_info(self, message: str) -> None:
        print(f"[INFO] {message}")

    def show_error(self, message: str) -> None:
        print(f"[ERROR] {message}")

    # ====================== Board rendering ======================
    def render_state(self, state: dict) -> None:
        if not state:
            self.show_info("No state available.")
            return

        print()
        print("=" * 60)
        print("BATTLESHIP")
        print("=" * 60)

        started = state.get("started", False)
        game_over = state.get("game_over", False)
        current_turn = state.get("current_turn")
        turn_count = state.get("turn_count")
        you = state.get("you")

        if started:
            print(f"Turn: {turn_count}")
            if not game_over:
                print("Status: Your turn" if current_turn == you else "Status: Opponent's turn")
            else:
                winner_id = state.get("winner_id")
                print("Status: You won" if winner_id == you else "Status: You lost")
        else:
            print("Status: Setup phase")
            print(f"You ready: {'Yes' if state.get('your_ready') else 'No'}")
            print(f"Opponent ready: {'Yes' if state.get('opponent_ready') else 'No'}")

        print()

        if state.get("your_board") is not None:
            self.render_single_board("Your Board", state["your_board"])

        if state.get("opponent_board") is not None:
            print()
            self.render_single_board("Opponent Board", state["opponent_board"])

        print("=" * 60)
        print()

    def render_single_board(self, title: str, board: List[List[str]]) -> None:
        print(title)
        print(self._format_board(board))

    def _format_board(self, board: List[List[str]]) -> str:
        if not board:
            return "(empty board)"

        lines: List[str] = []

        header = "   " + " ".join(f"{col:2}" for col in range(len(board[0])))
        lines.append(header)

        for row_index, row in enumerate(board):
            row_str = " ".join(f"{cell:2}" for cell in row)
            lines.append(f"{row_index:2} {row_str}")

        return "\n".join(lines)

    # ====================== Input prompts ======================
    def prompt_ship_placement(self, remaining_ships: Optional[List[str]] = None) -> Optional[ShipPlacement]:
        self._show_remaining_ship_options(remaining_ships)

        while True:
            raw = input(
                "Place ship as: <ship_name> <row> <col> <h/v> (or type 'quit'): "
            ).strip()

            if raw.lower() == "quit":
                return None

            parts = raw.split()
            if len(parts) != 4:
                self.show_error("Expected 4 values: <ship_name> <row> <col> <h/v>.")
                continue

            ship_name_raw, row_raw, col_raw, direction_raw = parts
            ship_name = self._normalize_ship_name(ship_name_raw)

            if ship_name is None:
                self.show_error(f"Unknown ship name: {ship_name_raw}")
                continue

            if remaining_ships is not None and ship_name not in remaining_ships:
                self.show_error(f"{ship_name} has already been placed.")
                continue

            try:
                row = int(row_raw)
                col = int(col_raw)
            except ValueError:
                self.show_error("Row and column must be integers.")
                continue

            if not self._is_valid_coord(row, col):
                self.show_error(f"Coordinates must be within 0 and {BOARD_SIZE - 1}.")
                continue

            if direction_raw.lower() not in {"h", "v"}:
                self.show_error("Direction must be 'h' or 'v'.")
                continue

            return ship_name, row, col, direction_raw.lower() == "h"


    def prompt_attack(self) -> Optional[Coord]:
        while True:
            raw = input("Attack as: <row> <col> (or type 'quit'): ").strip()

            if raw.lower() == "quit":
                return None

            parts = raw.split()
            if len(parts) != 2:
                self.show_error("Expected 2 values: <row> <col>.")
                continue

            try:
                row, col = map(int, parts)
            except ValueError:
                self.show_error("Row and column must be integers.")
                continue

            if not self._is_valid_coord(row, col):
                self.show_error(f"Coordinates must be within 0 and {BOARD_SIZE - 1}.")
                continue

            return row, col

    # ====================== Helpers ======================
    def _show_remaining_ship_options(self, remaining_ships: Optional[List[str]] = None) -> None:
        self.show_info("Available ships:")

        if remaining_ships is None:
            ships = SHIP_SIZES.items()
        else:
            ships = [(name, SHIP_SIZES[name]) for name in remaining_ships]

        for name, size in ships:
            print(f"  - {name} (length {size})")

    def _normalize_ship_name(self, raw_name: str) -> Optional[str]:
        lowered = raw_name.strip().lower()
        for name in SHIP_SIZES:
            if name.lower() == lowered:
                return name
        return None

    def _is_valid_coord(self, row: int, col: int) -> bool:
        return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE