"""
core/player_state.py

Stores the game-related state for a single player in a Battleship match.

A PlayerState owns that player's board and tracks which ships they have already
placed during setup. This class does not handle networking, sockets, or UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, List

from core.board import Board
from utils.constants import SHIP_SIZES


@dataclass
class PlayerState:
    """
    Represents one player's state in the match.

    Attributes:
        player_id: Stable player identifier (1 or 2).
        board: This player's personal board.
        placed_ship_names: Set of ship names already placed during setup.
        connected: Whether this player is currently connected.
    """
    player_id: int
    board: Board = field(default_factory=Board)
    placed_ship_names: Set[str] = field(default_factory=set)
    connected: bool = True

    def has_ship(self, ship_name: str) -> bool:
        """
        Return True if the player has already placed the named ship.
        """
        return ship_name in self.placed_ship_names

    def ships_placed_count(self) -> int:
        """
        Return how many ships this player has placed so far.
        """
        return len(self.placed_ship_names)

    def total_required_ships(self) -> int:
        """
        Return the total number of ships the player must place.
        """
        return len(SHIP_SIZES)

    def all_ships_placed(self) -> bool:
        """
        Return True if the player has placed every required ship.
        """
        return len(self.placed_ship_names) == len(SHIP_SIZES)

    def missing_ships(self) -> List[str]:
        """
        Return a list of ship names that have not yet been placed.
        """
        return [
            ship_name
            for ship_name in SHIP_SIZES
            if ship_name not in self.placed_ship_names
        ]

    def mark_ship_placed(self, ship_name: str) -> None:
        """
        Mark the named ship as placed.
        """
        if ship_name not in SHIP_SIZES:
            raise ValueError(f"Invalid ship name: {ship_name}")
        self.placed_ship_names.add(ship_name)

    def mark_disconnected(self) -> None:
        """
        Mark the player as currently disconnected.
        """
        self.connected = False

    def mark_connected(self) -> None:
        """
        Mark the player as currently connected.
        """
        self.connected = True

    def reset_for_new_game(self) -> None:
        """
        Reset player state for a fresh match.

        This keeps the same player_id, but clears board/setup state.
        """
        self.board = Board()
        self.placed_ship_names.clear()
        self.connected = True