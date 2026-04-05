"""
core/board.py

Represents a single Battleship board. This class is responsible for ship
placement, validating coordinates, recording attacks, and reporting board state.

The Board does not handle networking or UI. It only manages game rules for one
player's grid.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from utils.constants import BOARD_SIZE, SHIP_SIZES
from core.ship import Ship

Coord = Tuple[int, int]


class Board:
    """
    A Board stores:
    - ships placed on this player's grid
    - all coordinates that have been attacked
    - quick lookup from coordinate -> ship

    Coordinate system:
    - (row, col)
    - 0-indexed
    - valid range: 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE
    """

    def __init__(self, size: int = BOARD_SIZE) -> None:
        self.size: int = size
        self.ships: List[Ship] = []
        self.attacks: Set[Coord] = set()
        self._ship_cells: Dict[Coord, Ship] = {}

    def in_bounds(self, coord: Coord) -> bool:
        """Return True if the coordinate is inside the board."""
        row, col = coord
        return 0 <= row < self.size and 0 <= col < self.size

    def get_ship_at(self, coord: Coord) -> Optional[Ship]:
        """Return the ship occupying coord, or None if empty."""
        return self._ship_cells.get(coord)

    def has_ship_named(self, ship_name: str) -> bool:
        """Return True if a ship with this name has already been placed."""
        return any(ship.name == ship_name for ship in self.ships)

    def can_place_ship(self, ship: Ship) -> bool:
        """
        Return True if the ship can be placed on this board.

        Rules enforced:
        - ship name must exist in SHIP_SIZES
        - ship size must match SHIP_SIZES
        - duplicate ship names are not allowed
        - every occupied cell must be inside bounds
        - ships cannot overlap
        - touching is allowed
        """
        if ship.name not in SHIP_SIZES:
            return False

        if ship.size != SHIP_SIZES[ship.name]:
            return False

        if self.has_ship_named(ship.name):
            return False

        for coord in ship.coordinates:
            if not self.in_bounds(coord):
                return False
            if coord in self._ship_cells:
                return False

        return True

    def place_ship(self, ship: Ship) -> None:
        """
        Place a ship on the board.

        Raises:
            ValueError: if the ship placement is invalid.
        """
        if ship.name not in SHIP_SIZES:
            raise ValueError(f"Unknown ship name: {ship.name}.")

        expected_size = SHIP_SIZES[ship.name]
        if ship.size != expected_size:
            raise ValueError(
                f"Ship {ship.name} has size {ship.size}, expected {expected_size}."
            )

        if self.has_ship_named(ship.name):
            raise ValueError(f"Ship {ship.name} has already been placed.")

        if not self.can_place_ship(ship):
            raise ValueError(f"Invalid ship placement for {ship.name}.")

        self.ships.append(ship)
        for coord in ship.coordinates:
            self._ship_cells[coord] = ship

    def all_ships_placed(self) -> bool:
        """Return True if all required ships have been placed."""
        return len(self.ships) == len(SHIP_SIZES)

    def already_attacked(self, coord: Coord) -> bool:
        """Return True if this coordinate has already been targeted."""
        return coord in self.attacks

    def receive_attack(self, coord: Coord) -> dict:
        """
        Apply an attack to this board and return the result.

        Returns a dictionary with:
        - valid: whether the move was accepted
        - repeated: whether this was a duplicate attack
        - hit: whether a ship was hit
        - sunk: whether that hit sank a ship
        - ship_name: the affected ship name if relevant
        - game_over: whether all ships are now sunk
        - message: a human-readable result message

        Example:
            {
                "valid": True,
                "repeated": False,
                "hit": True,
                "sunk": False,
                "ship_name": "Destroyer1",
                "game_over": False,
                "message": "Hit Destroyer1.",
            }
        """
        if not self.in_bounds(coord):
            return {
                "valid": False,
                "repeated": False,
                "hit": False,
                "sunk": False,
                "ship_name": None,
                "game_over": False,
                "message": "Attack out of bounds.",
            }

        if coord in self.attacks:
            return {
                "valid": False,
                "repeated": True,
                "hit": False,
                "sunk": False,
                "ship_name": None,
                "game_over": False,
                "message": "Coordinate already attacked.",
            }

        self.attacks.add(coord)

        ship = self.get_ship_at(coord)
        if ship is None:
            return {
                "valid": True,
                "repeated": False,
                "hit": False,
                "sunk": False,
                "ship_name": None,
                "game_over": False,
                "message": "Miss.",
            }

        ship.register_hit(coord)
        sunk = ship.is_sunk()

        return {
            "valid": True,
            "repeated": False,
            "hit": True,
            "sunk": sunk,
            "ship_name": ship.name,
            "game_over": self.all_ships_sunk(),
            "message": f"{'Sunk' if sunk else 'Hit'} {ship.name}.",
        }

    def all_ships_sunk(self) -> bool:
        """Return True if every ship on this board has been sunk."""
        return len(self.ships) > 0 and all(ship.is_sunk() for ship in self.ships)

    def owner_view(self) -> List[List[str]]:
        """
        Return a 2D grid for the owning player.

        Symbols:
        - '.' empty untouched
        - 'S' ship not yet hit
        - 'X' hit ship cell
        - 'O' missed attack
        """
        grid = [["." for _ in range(self.size)] for _ in range(self.size)]

        for coord in self._ship_cells:
            row, col = coord
            grid[row][col] = "S"

        for row, col in self.attacks:
            ship = self.get_ship_at((row, col))
            grid[row][col] = "X" if ship is not None else "O"

        return grid

    def opponent_view(self) -> List[List[str]]:
        """
        Return a 2D grid for the opponent.

        Symbols:
        - '.' unknown / not attacked yet
        - 'X' hit ship cell
        - 'O' missed attack

        Ships that have not been hit are hidden.
        """
        grid = [["." for _ in range(self.size)] for _ in range(self.size)]

        for row, col in self.attacks:
            ship = self.get_ship_at((row, col))
            grid[row][col] = "X" if ship is not None else "O"

        return grid