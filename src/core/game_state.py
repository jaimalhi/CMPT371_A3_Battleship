"""
core/game_state.py

Owns the full Battleship match state for two players.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from core.player_state import PlayerState
from core.ship import Ship
from utils.constants import SHIP_SIZES

Coord = Tuple[int, int]


@dataclass
class AttackResult:
    valid: bool
    message: str
    attacker_id: Optional[int] = None
    defender_id: Optional[int] = None
    coord: Optional[Coord] = None
    hit: bool = False
    sunk: bool = False
    ship_name: Optional[str] = None
    repeated: bool = False
    game_over: bool = False
    winner_id: Optional[int] = None


class GameState:
    def __init__(self) -> None:
        self.players: Dict[int, PlayerState] = {
            1: PlayerState(player_id=1),
            2: PlayerState(player_id=2),
        }

        self.current_turn: int = 1
        self.turn_count: int = 1
        self.started: bool = False
        self.game_over: bool = False
        self.winner_id: Optional[int] = None

    def get_player(self, player_id: int) -> PlayerState:
        if player_id not in self.players:
            raise ValueError(f"Unknown player_id: {player_id}")
        return self.players[player_id]

    def get_opponent_id(self, player_id: int) -> int:
        return 2 if player_id == 1 else 1

    def get_opponent(self, player_id: int) -> PlayerState:
        return self.get_player(self.get_opponent_id(player_id))

    def is_setup_complete(self) -> bool:
        return all(player.all_ships_placed() for player in self.players.values())

    def can_start(self) -> bool:
        return not self.started and self.is_setup_complete()

    def start_game(self) -> None:
        if not self.is_setup_complete():
            raise ValueError("Cannot start game before setup is complete.")

        self.started = True
        self.current_turn = 1
        self.turn_count = 1

    def place_ship(
        self,
        player_id: int,
        ship_name: str,
        start: Coord,
        horizontal: bool,
    ) -> None:
        """
        Place a ship using its name from SHIP_SIZES.
        """
        if self.started:
            raise ValueError("Cannot place ships after the game has started.")

        if ship_name not in SHIP_SIZES:
            raise ValueError(f"Invalid ship name: {ship_name}")

        player = self.get_player(player_id)

        if player.has_ship(ship_name):
            raise ValueError(f"Ship {ship_name} already placed.")

        size = SHIP_SIZES[ship_name]

        ship = Ship.from_start(
            size=size,
            start=start,
            horizontal=horizontal,
            name=ship_name,
        )

        player.board.place_ship(ship)
        player.mark_ship_placed(ship_name)

    def player_ready(self, player_id: int) -> bool:
        return self.get_player(player_id).all_ships_placed()

    def is_players_turn(self, player_id: int) -> bool:
        return self.started and not self.game_over and self.current_turn == player_id

    def _is_valid_coord(self, coord: object) -> bool:
        return (
            isinstance(coord, tuple)
            and len(coord) == 2
            and isinstance(coord[0], int)
            and isinstance(coord[1], int)
        )

    def process_attack(self, attacker_id: int, coord: Coord) -> AttackResult:
        if self.game_over:
            return AttackResult(valid=False, message="Game is already over.")

        if not self.started:
            return AttackResult(valid=False, message="Game has not started.")

        if attacker_id not in self.players:
            return AttackResult(valid=False, message="Unknown player.")

        if not self._is_valid_coord(coord):
            return AttackResult(valid=False, message="Invalid coordinate.")

        if self.current_turn != attacker_id:
            return AttackResult(valid=False, message="Not your turn.")

        defender_id = self.get_opponent_id(attacker_id)
        defender = self.get_player(defender_id)

        board_result = defender.board.receive_attack(coord)

        if not board_result["valid"]:
            return AttackResult(
                valid=False,
                message=board_result["message"],
                attacker_id=attacker_id,
                defender_id=defender_id,
                coord=coord,
                repeated=board_result.get("repeated", False),
            )

        result = AttackResult(
            valid=True,
            message=board_result["message"],
            attacker_id=attacker_id,
            defender_id=defender_id,
            coord=coord,
            hit=board_result["hit"],
            sunk=board_result["sunk"],
            ship_name=board_result["ship_name"],
            repeated=board_result["repeated"],
            game_over=board_result["game_over"],
        )

        if board_result["game_over"]:
            self.game_over = True
            self.winner_id = attacker_id
            result.winner_id = attacker_id
            return result

        self.current_turn = defender_id
        self.turn_count += 1
        return result

    def forfeit(self, loser_id: int) -> AttackResult:
        if loser_id not in self.players:
            raise ValueError("Unknown player.")

        winner_id = self.get_opponent_id(loser_id)
        self.game_over = True
        self.winner_id = winner_id

        return AttackResult(
            valid=True,
            message=f"Player {loser_id} forfeited.",
            attacker_id=winner_id,
            defender_id=loser_id,
            game_over=True,
            winner_id=winner_id,
        )

    def get_public_state_for(self, player_id: int) -> dict:
        player = self.get_player(player_id)
        opponent = self.get_opponent(player_id)

        return {
            "you": player_id,
            "current_turn": self.current_turn,
            "turn_count": self.turn_count,
            "started": self.started,
            "game_over": self.game_over,
            "winner_id": self.winner_id,
            "your_board": player.board.owner_view(),
            "opponent_board": opponent.board.opponent_view(),
            "your_ready": player.all_ships_placed(),
            "opponent_ready": opponent.all_ships_placed(),
        }