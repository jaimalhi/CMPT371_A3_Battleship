"""
ui/gui.py

Tkinter-based graphical user interface for Battleship.

This module mirrors the TerminalUI interface so it can be swapped in
as a drop-in replacement inside client.py.
"""

from __future__ import annotations

import queue
import tkinter as tk
from typing import Dict, List, Optional, Tuple

from utils.constants import BOARD_SIZE, SHIP_SIZES

Coord = Tuple[int, int]
ShipPlacement = Tuple[str, int, int, bool]

COLORS: Dict[str, str] = {
    ".": "#1a1a2e",
    "S": "#0f4c75",
    "H": "#e23e57",
    "M": "#53687e",
    "X": "#b80000",
}
DEFAULT_CELL_BG = COLORS["."]


class GuiUI:
    """Tkinter GUI for the Battleship client."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Battleship")
        self.root.configure(bg="#0f0f23")
        self.root.resizable(True, True)
        self.root.minsize(500, 600)

        self._your_cells: List[List[tk.Label]] = []
        self._opponent_cells: List[List[tk.Label]] = []

        self._input_queue: queue.Queue[Optional[Tuple]] = queue.Queue()

        self._accepting_placement = False
        self._accepting_attack = False
        self._remaining_ships: List[str] = []

        self._build_ui()

    # ====================== Layout construction ======================

    def _build_ui(self) -> None:
        self._build_status_bar()
        self._build_boards_area()
        self._build_placement_panel()
        self._build_message_log()

    def _build_status_bar(self) -> None:
        status_frame = tk.Frame(self.root, bg="#0f0f23", pady=8)
        status_frame.pack(fill=tk.X)

        self.status_label = tk.Label(
            status_frame,
            text="Welcome to Battleship",
            font=("Courier", 14, "bold"),
            fg="#e0e0e0",
            bg="#0f0f23",
            anchor="center",
        )
        self.status_label.pack()

    def _build_boards_area(self) -> None:
        boards_frame = tk.Frame(self.root, bg="#0f0f23", padx=20, pady=5)
        boards_frame.pack()

        # --- Opponent board (top) ---
        opponent_frame = tk.Frame(boards_frame, bg="#0f0f23")
        opponent_frame.pack(pady=(0, 10))

        tk.Label(
            opponent_frame,
            text="Opponent Board",
            font=("Courier", 12, "bold"),
            fg="#ef5350",
            bg="#0f0f23",
        ).pack(pady=(0, 5))

        opponent_grid = tk.Frame(opponent_frame, bg="#0f0f23")
        opponent_grid.pack()
        self._opponent_cells = self._build_grid(opponent_grid, clickable=True)

        # --- Separator ---
        tk.Frame(boards_frame, bg="#333333", height=2).pack(fill=tk.X, pady=5)

        # --- Your board (bottom) ---
        your_frame = tk.Frame(boards_frame, bg="#0f0f23")
        your_frame.pack(pady=(10, 0))

        tk.Label(
            your_frame,
            text="Your Board",
            font=("Courier", 12, "bold"),
            fg="#4fc3f7",
            bg="#0f0f23",
        ).pack(pady=(0, 5))

        your_grid = tk.Frame(your_frame, bg="#0f0f23")
        your_grid.pack()
        self._your_cells = self._build_grid(your_grid, clickable=True)

    def _build_grid(
        self, parent: tk.Frame, clickable: bool = False,
    ) -> List[List[tk.Label]]:
        """Build an 8x8 grid of labels and return the 2D cell list."""
        header_bg = "#0f0f23"
        header_fg = "#888888"

        tk.Label(
            parent, text="", width=3,
            bg=header_bg, fg=header_fg, font=("Courier", 10),
        ).grid(row=0, column=0)

        for c in range(BOARD_SIZE):
            tk.Label(
                parent, text=str(c), width=3,
                bg=header_bg, fg=header_fg, font=("Courier", 10),
            ).grid(row=0, column=c + 1)

        cells: List[List[tk.Label]] = []
        for r in range(BOARD_SIZE):
            tk.Label(
                parent, text=str(r), width=3,
                bg=header_bg, fg=header_fg, font=("Courier", 10),
            ).grid(row=r + 1, column=0)

            row_cells: List[tk.Label] = []
            for c in range(BOARD_SIZE):
                cell = tk.Label(
                    parent,
                    text="",
                    width=3,
                    height=1,
                    bg=DEFAULT_CELL_BG,
                    fg="#ffffff",
                    font=("Courier", 12, "bold"),
                    relief="ridge",
                    borderwidth=1,
                )
                cell.grid(row=r + 1, column=c + 1, padx=1, pady=1)
                if clickable:
                    cell.bind("<Button-1>", self._make_cell_callback(r, c))
                row_cells.append(cell)
            cells.append(row_cells)

        return cells

    def _build_placement_panel(self) -> None:
        """Ship selection panel shown during setup phase."""
        self.placement_frame = tk.Frame(self.root, bg="#0f0f23", pady=10)
        self.placement_frame.pack(fill=tk.X)

        row_frame = tk.Frame(self.placement_frame, bg="#0f0f23")
        row_frame.pack()

        tk.Label(
            row_frame, text="Ship:", font=("Courier", 11),
            fg="#e0e0e0", bg="#0f0f23",
        ).pack(side=tk.LEFT, padx=5)

        self.ship_var = tk.StringVar(self.root)
        ship_names = list(SHIP_SIZES.keys())
        self.ship_var.set(ship_names[0])
        self.ship_menu = tk.OptionMenu(row_frame, self.ship_var, *ship_names)
        self.ship_menu.configure(
            font=("Courier", 10), bg="#16213e", fg="#1a1a2e",
            activebackground="#1a1a40", activeforeground="#111111",
            highlightthickness=0,
        )
        self.ship_menu.pack(side=tk.LEFT, padx=5)

        tk.Label(
            row_frame, text="Direction:", font=("Courier", 11),
            fg="#e0e0e0", bg="#0f0f23",
        ).pack(side=tk.LEFT, padx=(20, 5))

        self.direction_var = tk.StringVar(value="h")
        tk.Radiobutton(
            row_frame, text="Horizontal", variable=self.direction_var,
            value="h", font=("Courier", 10),
            fg="#e0e0e0", bg="#0f0f23", selectcolor="#16213e",
            activebackground="#0f0f23", activeforeground="#ffffff",
        ).pack(side=tk.LEFT, padx=2)

        tk.Radiobutton(
            row_frame, text="Vertical", variable=self.direction_var,
            value="v", font=("Courier", 10),
            fg="#e0e0e0", bg="#0f0f23", selectcolor="#16213e",
            activebackground="#0f0f23", activeforeground="#ffffff",
        ).pack(side=tk.LEFT, padx=2)

        size_label_text = "  |  ".join(
            f"{name}: {size}" for name, size in SHIP_SIZES.items()
        )
        tk.Label(
            self.placement_frame, text=size_label_text,
            font=("Courier", 9), fg="#888888", bg="#0f0f23",
        ).pack(pady=(5, 0))

    def _build_message_log(self) -> None:
        """Scrollable text log that shows all info/error messages."""
        log_frame = tk.Frame(self.root, bg="#0f0f23", padx=20, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            log_frame, text="Message Log",
            font=("Courier", 10, "bold"), fg="#888888", bg="#0f0f23",
        ).pack(anchor="w")

        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.message_log = tk.Text(
            log_frame,
            height=6,
            font=("Courier", 10),
            fg="#cccccc",
            bg="#12122a",
            insertbackground="#cccccc",
            relief="flat",
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=scrollbar.set,
        )
        self.message_log.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.message_log.yview)

        self.message_log.tag_configure("info", foreground="#cccccc")
        self.message_log.tag_configure("error", foreground="#ff5252")

    def _append_log(self, text: str, tag: str = "info") -> None:
        """Append a line to the message log and auto-scroll to bottom."""
        self.message_log.configure(state=tk.NORMAL)
        self.message_log.insert(tk.END, text + "\n", tag)
        self.message_log.see(tk.END)
        self.message_log.configure(state=tk.DISABLED)

    # ====================== Click handling ======================

    def _make_cell_callback(self, row: int, col: int):
        """Return a click handler bound to a specific (row, col)."""
        def _on_click(_event: tk.Event) -> None:
            if self._accepting_placement:
                ship_name = self.ship_var.get()
                horizontal = self.direction_var.get() == "h"
                self._accepting_placement = False
                self._input_queue.put((ship_name, row, col, horizontal))

            elif self._accepting_attack:
                self._accepting_attack = False
                self._input_queue.put((row, col))

        return _on_click

    # ====================== Public UI interface ======================
    # These 6 methods match TerminalUI and are called from the
    # background network thread.  All Tkinter widget updates are
    # scheduled on the main thread via root.after() so the GUI
    # never freezes and Tkinter's thread-safety rules are respected.

    def show_info(self, message: str) -> None:
        self.root.after(0, self._do_show_info, message)

    def show_error(self, message: str) -> None:
        self.root.after(0, self._do_show_error, message)

    def render_state(self, state: dict) -> None:
        self.root.after(0, self._do_render_state, state)

    def render_single_board(self, title: str, board: List[List[str]]) -> None:
        self.root.after(0, self._do_render_single_board, title, board)

    def prompt_ship_placement(
        self, remaining_ships: Optional[List[str]] = None,
    ) -> Optional[ShipPlacement]:
        ships = remaining_ships or list(SHIP_SIZES.keys())
        self.root.after(0, self._do_begin_placement, ships)
        return self._input_queue.get()

    def prompt_attack(self) -> Optional[Coord]:
        self.root.after(0, self._do_begin_attack)
        return self._input_queue.get()

    # ====================== Main-thread UI updates ======================
    # These _do_* methods run on the Tkinter main thread only.

    def _do_show_info(self, message: str) -> None:
        self.status_label.configure(text=message, fg="#e0e0e0")
        self._append_log(message, "info")

    def _do_show_error(self, message: str) -> None:
        self.status_label.configure(text=f"ERROR: {message}", fg="#ff5252")
        self._append_log(f"ERROR: {message}", "error")

    def _do_render_state(self, state: dict) -> None:
        if not state:
            return

        started = state.get("started", False)
        game_over = state.get("game_over", False)
        current_turn = state.get("current_turn")
        turn_count = state.get("turn_count")
        you = state.get("you")

        if started:
            if game_over:
                winner_id = state.get("winner_id")
                if winner_id == you:
                    self.status_label.configure(text="GAME OVER — You won!", fg="#66bb6a")
                else:
                    self.status_label.configure(text="GAME OVER — You lost.", fg="#ef5350")
            else:
                if current_turn == you:
                    self.status_label.configure(
                        text=f"Turn {turn_count} — Your turn  (click opponent board)",
                        fg="#4fc3f7",
                    )
                else:
                    self.status_label.configure(
                        text=f"Turn {turn_count} — Opponent's turn",
                        fg="#e0e0e0",
                    )
        else:
            your_ready = state.get("your_ready", False)
            opp_ready = state.get("opponent_ready", False)
            self.status_label.configure(
                text=f"Setup phase  |  You: {'Ready' if your_ready else 'Placing'}  |  Opponent: {'Ready' if opp_ready else 'Placing'}",
                fg="#e0e0e0",
            )

        if state.get("your_board") is not None:
            self._update_grid(self._your_cells, state["your_board"])

        if state.get("opponent_board") is not None:
            self._update_grid(self._opponent_cells, state["opponent_board"])

    def _do_render_single_board(self, title: str, board: List[List[str]]) -> None:
        if "opponent" in title.lower():
            self._update_grid(self._opponent_cells, board)
        else:
            self._update_grid(self._your_cells, board)

    def _do_begin_placement(self, ship_names: List[str]) -> None:
        self._remaining_ships = ship_names
        self._update_ship_menu(ship_names)
        self.placement_frame.pack(fill=tk.X)
        self.status_label.configure(
            text="Place your ships — select ship & direction, then click your board.",
            fg="#e0e0e0",
        )
        self._accepting_placement = True

    def _do_begin_attack(self) -> None:
        self.placement_frame.pack_forget()
        self.status_label.configure(
            text="Your turn — click a cell on the opponent board.",
            fg="#4fc3f7",
        )
        self._accepting_attack = True

    # ====================== Internal helpers ======================

    def _update_grid(
        self, cells: List[List[tk.Label]], board: List[List[str]],
    ) -> None:
        for r, row_data in enumerate(board):
            for c, value in enumerate(row_data):
                bg = COLORS.get(value, DEFAULT_CELL_BG)
                display = "" if value == "." else value
                cells[r][c].configure(bg=bg, text=display)

    def _update_ship_menu(self, ship_names: List[str]) -> None:
        menu = self.ship_menu["menu"]
        menu.delete(0, "end")
        for name in ship_names:
            menu.add_command(
                label=name,
                command=lambda n=name: self.ship_var.set(n),
            )
        if ship_names:
            self.ship_var.set(ship_names[0])


# Quick visual test when running this file directly
if __name__ == "__main__":
    gui = GuiUI()
    gui.root.mainloop()
