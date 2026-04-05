"""
core/ship.py

Defines the Ship class used by the Battleship game.

A ship stores:
- its size
- the coordinates it occupies
- which of those coordinates have been hit

This class is intentionally independent from networking and UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, Tuple

Coord = Tuple[int, int]


@dataclass
class Ship:
    """
    Represents a single ship placed on the board.

    Attributes:
        size: Length of the ship.
        coordinates: All board cells occupied by this ship.
        hits: Occupied cells that have been hit.
        name: Optional display name for debugging/UI. Defaults to size-based name.
    """

    size: int
    coordinates: Set[Coord] = field(default_factory=set)
    hits: Set[Coord] = field(default_factory=set)
    name: str = ""

    def __post_init__(self) -> None:
        """Validate ship data after construction."""
        if self.size <= 0:
            raise ValueError("Ship size must be positive.")

        if not self.name:
            self.name = f"Ship(size={self.size})"

        if len(self.coordinates) != self.size:
            raise ValueError(
                f"Ship of size {self.size} must occupy exactly {self.size} coordinates."
            )

    @classmethod
    def from_start(
        cls,
        size: int,
        start: Coord,
        horizontal: bool,
        name: str | None = None,
    ) -> "Ship":
        """
        Build a ship from a starting coordinate, size, and orientation.

        Args:
            size: Length of the ship.
            start: Starting coordinate as (row, col).
            horizontal: True for horizontal placement, False for vertical.
            name: Optional human-readable ship name.

        Returns:
            A Ship instance with all occupied coordinates populated.
        """
        row, col = start
        coordinates: Set[Coord] = set()

        for offset in range(size):
            if horizontal:
                coordinates.add((row, col + offset))
            else:
                coordinates.add((row + offset, col))

        return cls(
            size=size,
            coordinates=coordinates,
            name=name or f"Ship(size={size})",
        )

    def register_hit(self, coord: Coord) -> bool:
        """
        Record a hit on this ship if the coordinate belongs to it.

        Args:
            coord: Attack coordinate as (row, col).

        Returns:
            True if the ship occupies that coordinate, otherwise False.
        """
        if coord in self.coordinates:
            self.hits.add(coord)
            return True
        return False

    def is_sunk(self) -> bool:
        """
        Return True if every occupied coordinate has been hit.
        """
        return self.coordinates == self.hits

    def occupies(self, coord: Coord) -> bool:
        """
        Return True if the ship occupies the given coordinate.
        """
        return coord in self.coordinates