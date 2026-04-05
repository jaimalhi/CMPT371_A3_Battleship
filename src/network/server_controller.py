"""
network/server_controller.py

Coordinates Battleship server-side game flow. This controller sits between the
network transport layer and the core game state. It validates incoming messages,
updates the GameState, tracks which connection owns which player seat, and
returns outbound messages for the server to send.

This file does not directly read/write sockets. The top-level server is expected
to pass decoded messages in and send the returned responses/events out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from utils.constants import SHIP_SIZES
from core.game_state import AttackResult, GameState
from network.message_types import MessageTypes
from network.protocol import Protocol


Coord = Tuple[int, int]


@dataclass
class OutboundEvent:
    """
    Represents one outbound message the server should send.

    Attributes:
        target:
            The connection ID to send to. If None, broadcast to all active
            players.
        message:
            The already-encoded protocol payload as a dictionary.
    """
    target: Optional[str]
    message: Dict[str, Any]


@dataclass
class SeatInfo:
    """
    Tracks which connection currently occupies a player seat.
    """
    player_id: int
    connection_id: Optional[str] = None
    connected: bool = False


@dataclass
class ServerController:
    """
    Owns the server-side Battleship match/session state.

    Responsibilities:
    - assign player seats
    - support reconnects to the same seat
    - pause progression while a player is disconnected
    - process incoming protocol messages
    - return outbound events for the transport layer to send
    """
    game: GameState = field(default_factory=GameState)
    seats: Dict[int, SeatInfo] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.seats:
            self.seats = {
                1: SeatInfo(player_id=1),
                2: SeatInfo(player_id=2),
            }

    # ==================== Seat / connection helpers ====================
    def get_player_id_for_connection(self, connection_id: str) -> Optional[int]:
        """Return the player ID currently bound to this connection, if any."""
        for player_id, seat in self.seats.items():
            if seat.connection_id == connection_id:
                return player_id
        return None

    def get_connection_for_player(self, player_id: int) -> Optional[str]:
        """Return the active connection ID for the given player, if any."""
        seat = self.seats[player_id]
        return seat.connection_id if seat.connected else None

    def all_players_connected(self) -> bool:
        """Return True if both player seats are currently occupied and connected."""
        return all(seat.connected for seat in self.seats.values())

    def has_open_seat(self) -> bool:
        """Return True if at least one player seat is unassigned."""
        return any(seat.connection_id is None for seat in self.seats.values())

    def _assign_new_seat(self, connection_id: str) -> Optional[int]:
        """
        Assign the first unclaimed seat to this connection.

        Returns:
            The assigned player_id, or None if no seat is available.
        """
        for player_id in (1, 2):
            seat = self.seats[player_id]
            if seat.connection_id is None:
                seat.connection_id = connection_id
                seat.connected = True
                self.game.get_player(player_id).mark_connected()
                return player_id
        return None

    def _reconnect_existing_seat(self, connection_id: str) -> Optional[int]:
        """
        Reattach to a previously disconnected seat if one exists.

        Returns:
            The reconnected player_id, or None if no reconnectable seat exists.
        """
        for player_id, seat in self.seats.items():
            if seat.connection_id is not None and not seat.connected:
                seat.connection_id = connection_id
                seat.connected = True
                self.game.get_player(player_id).mark_connected()
                return player_id
        return None

    @staticmethod
    def _parse_horizontal(value: Any) -> bool:
        """
        Parse a protocol-provided horizontal flag safely.

        Accepts:
        - bool: True / False
        - int: 1 / 0
        - str: "true"/"false", "1"/"0", "yes"/"no", "y"/"n"

        Raises:
            ValueError: if the value cannot be interpreted as a boolean.
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            if value == 1:
                return True
            if value == 0:
                return False

        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False

        raise ValueError("Invalid horizontal value.")

    # ==================== Public session lifecycle API ====================
    def connect(self, connection_id: str) -> List[OutboundEvent]:
        """
        Handle a newly connected client.

        Rules:
        - first two clients take seats 1 and 2
        - if a player had disconnected, a new connection may reclaim that seat
        - if both seats are occupied and connected, reject the join
        """
        events: List[OutboundEvent] = []

        if self.get_player_id_for_connection(connection_id) is not None:
            events.append(
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error("Connection is already registered."),
                )
            )
            return events

        player_id = self._reconnect_existing_seat(connection_id)
        reconnected = player_id is not None

        if player_id is None:
            player_id = self._assign_new_seat(connection_id)

        if player_id is None:
            events.append(
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error("Game already has two active players."),
                )
            )
            return events

        events.append(
            OutboundEvent(
                target=connection_id,
                message=Protocol.make_message(
                    MessageTypes.ASSIGN_PLAYER,
                    player_id=player_id,
                    reconnected=reconnected,
                ),
            )
        )

        events.append(
            OutboundEvent(
                target=connection_id,
                message=Protocol.make_message(
                    MessageTypes.STATE_SNAPSHOT,
                    state=self.game.get_public_state_for(player_id),
                ),
            )
        )

        opponent_id = self.game.get_opponent_id(player_id)
        opponent_connection = self.get_connection_for_player(opponent_id)
        if opponent_connection is not None:
            events.append(
                OutboundEvent(
                    target=opponent_connection,
                    message=Protocol.make_message(
                        MessageTypes.OPPONENT_CONNECTION,
                        player_id=player_id,
                        connected=True,
                        reconnected=reconnected,
                    ),
                )
            )

        return events

    def disconnect(self, connection_id: str) -> List[OutboundEvent]:
        """
        Mark a player as disconnected and notify the opponent.

        The game state is preserved. Reconnecting should resume the same seat.
        """
        events: List[OutboundEvent] = []

        player_id = self.get_player_id_for_connection(connection_id)
        if player_id is None:
            return events

        seat = self.seats[player_id]
        seat.connected = False
        self.game.get_player(player_id).mark_disconnected()

        opponent_id = self.game.get_opponent_id(player_id)
        opponent_connection = self.get_connection_for_player(opponent_id)
        if opponent_connection is not None:
            events.append(
                OutboundEvent(
                    target=opponent_connection,
                    message=Protocol.make_message(
                        MessageTypes.OPPONENT_CONNECTION,
                        player_id=player_id,
                        connected=False,
                        reconnected=False,
                    ),
                )
            )

        return events

    # ==================== Message handling ====================
    def handle_message(
        self,
        connection_id: str,
        message: Dict[str, Any],
    ) -> List[OutboundEvent]:
        message_type = message.get("type")

        if not isinstance(message_type, str) or not MessageTypes.is_valid(message_type):
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error("Unknown message type."),
                )
            ]

        player_id = self.get_player_id_for_connection(connection_id)

        if message_type == MessageTypes.JOIN:
            return self.connect(connection_id)

        if player_id is None:
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error("Connection is not assigned to a player."),
                )
            ]

        if not self.seats[player_id].connected:
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error("Player is currently disconnected."),
                )
            ]

        if message_type == MessageTypes.PLACE_SHIP:
            if self.game.started:
                return [
                    OutboundEvent(
                        target=connection_id,
                        message=Protocol.make_error(
                            "Cannot place ships after game has started."
                        ),
                    )
                ]
            return self._handle_place_ship(connection_id, player_id, message)

        if message_type == MessageTypes.ATTACK:
            if not self.game.started:
                return [
                    OutboundEvent(
                        target=connection_id,
                        message=Protocol.make_error("Game has not started yet."),
                    )
                ]
            return self._handle_attack(connection_id, player_id, message)

        if message_type == MessageTypes.STATE_SNAPSHOT:
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_message(
                        MessageTypes.STATE_SNAPSHOT,
                        state=self.game.get_public_state_for(player_id),
                    ),
                )
            ]

        if message_type == MessageTypes.PING:
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_message(MessageTypes.PONG),
                )
            ]

        if message_type == MessageTypes.FORFEIT:
            return self._handle_forfeit(player_id)

        return [
            OutboundEvent(
                target=connection_id,
                message=Protocol.make_error("Unsupported message type for this server."),
            )
        ]

    # ==================== Internal handlers ====================
    def _handle_place_ship(
        self,
        connection_id: str,
        player_id: int,
        message: Dict[str, Any],
    ) -> List[OutboundEvent]:
        """Process a PLACE_SHIP request."""
        events: List[OutboundEvent] = []

        try:
            ship_name = str(message["ship_name"]).strip()
            row = int(message["row"])
            col = int(message["col"])
            horizontal = self._parse_horizontal(message["horizontal"])
        except (KeyError, TypeError, ValueError):
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error("Invalid PLACE_SHIP payload."),
                )
            ]

        if ship_name not in SHIP_SIZES:
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_message(
                        MessageTypes.PLACE_SHIP_RESULT,
                        ok=False,
                        error=f"Invalid ship name: {ship_name}",
                    ),
                )
            ]

        try:
            self.game.place_ship(
                player_id=player_id,
                ship_name=ship_name,
                start=(row, col),
                horizontal=horizontal,
            )
        except ValueError as exc:
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_message(
                        MessageTypes.PLACE_SHIP_RESULT,
                        ok=False,
                        error=str(exc),
                    ),
                )
            ]

        player = self.game.get_player(player_id)
        placed_ship_count = player.ships_placed_count()
        total_ships = player.total_required_ships()

        events.append(
            OutboundEvent(
                target=connection_id,
                message=Protocol.make_message(
                    MessageTypes.PLACE_SHIP_RESULT,
                    ok=True,
                    ship_name=ship_name,
                    row=row,
                    col=col,
                    horizontal=horizontal,
                    placed_ship_count=placed_ship_count,
                    total_ships=total_ships,
                    your_board=player.board.owner_view(),
                ),
            )
        )

        if player.all_ships_placed():
            events.append(
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_message(
                        MessageTypes.SETUP_COMPLETE,
                        player_id=player_id,
                    ),
                )
            )

        opponent_id = self.game.get_opponent_id(player_id)
        opponent_connection = self.get_connection_for_player(opponent_id)

        if self.game.can_start():
            self.game.start_game()

            for pid in (1, 2):
                target_connection = self.get_connection_for_player(pid)
                if target_connection is not None:
                    events.append(
                        OutboundEvent(
                            target=target_connection,
                            message=Protocol.make_message(
                                MessageTypes.START_GAME,
                                state=self.game.get_public_state_for(pid),
                            ),
                        )
                    )
        elif player.all_ships_placed() and opponent_connection is not None:
            events.append(
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_message(
                        MessageTypes.WAITING_FOR_OPPONENT_SETUP,
                    ),
                )
            )

            events.append(
                OutboundEvent(
                    target=opponent_connection,
                    message=Protocol.make_message(
                        MessageTypes.INFO,
                        message="Opponent completed ship placement.",
                    ),
                )
            )

        return events

    def _handle_attack(
        self,
        connection_id: str,
        player_id: int,
        message: Dict[str, Any],
    ) -> List[OutboundEvent]:
        """Process an ATTACK request."""
        events: List[OutboundEvent] = []

        if not self.all_players_connected():
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error(
                        "Game is paused until both players are connected."
                    ),
                )
            ]

        try:
            row = int(message["row"])
            col = int(message["col"])
        except (KeyError, TypeError, ValueError):
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_error("Invalid ATTACK payload."),
                )
            ]

        result: AttackResult = self.game.process_attack(player_id, (row, col))

        if not result.valid:
            return [
                OutboundEvent(
                    target=connection_id,
                    message=Protocol.make_message(
                        MessageTypes.ATTACK_RESULT,
                        ok=False,
                        error=result.message,
                        row=row,
                        col=col,
                    ),
                )
            ]

        attacker_connection = self.get_connection_for_player(result.attacker_id)
        defender_connection = self.get_connection_for_player(result.defender_id)

        if attacker_connection is not None:
            events.append(
                OutboundEvent(
                    target=attacker_connection,
                    message=Protocol.make_message(
                        MessageTypes.ATTACK_RESULT,
                        ok=True,
                        attacker_id=result.attacker_id,
                        defender_id=result.defender_id,
                        row=row,
                        col=col,
                        hit=result.hit,
                        sunk=result.sunk,
                        ship_name=result.ship_name,
                        repeated=result.repeated,
                        game_over=result.game_over,
                        state=self.game.get_public_state_for(result.attacker_id),
                    ),
                )
            )

        if defender_connection is not None:
            events.append(
                OutboundEvent(
                    target=defender_connection,
                    message=Protocol.make_message(
                        MessageTypes.ATTACK_RESULT,
                        ok=True,
                        attacker_id=result.attacker_id,
                        defender_id=result.defender_id,
                        row=row,
                        col=col,
                        hit=result.hit,
                        sunk=result.sunk,
                        ship_name=result.ship_name,
                        repeated=result.repeated,
                        game_over=result.game_over,
                        state=self.game.get_public_state_for(result.defender_id),
                    ),
                )
            )

        if result.game_over:
            for pid in (1, 2):
                target_connection = self.get_connection_for_player(pid)
                if target_connection is not None:
                    events.append(
                        OutboundEvent(
                            target=target_connection,
                            message=Protocol.make_message(
                                MessageTypes.GAME_OVER,
                                winner_id=result.winner_id,
                                state=self.game.get_public_state_for(pid),
                            ),
                        )
                    )
            return events

        for pid in (1, 2):
            target_connection = self.get_connection_for_player(pid)
            if target_connection is not None:
                events.append(
                    OutboundEvent(
                        target=target_connection,
                        message=Protocol.make_message(
                            MessageTypes.TURN_UPDATE,
                            current_turn=self.game.current_turn,
                            turn_count=self.game.turn_count,
                        ),
                    )
                )

        return events

    def _handle_forfeit(self, loser_id: int) -> List[OutboundEvent]:
        """Process a player forfeit."""
        self.game.forfeit(loser_id)

        events: List[OutboundEvent] = []
        for pid in (1, 2):
            target_connection = self.get_connection_for_player(pid)
            if target_connection is not None:
                events.append(
                    OutboundEvent(
                        target=target_connection,
                        message=Protocol.make_message(
                            MessageTypes.GAME_OVER,
                            winner_id=self.game.winner_id,
                            forfeited_player=loser_id,
                            state=self.game.get_public_state_for(pid),
                        ),
                    )
                )
        return events