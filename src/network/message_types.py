"""
network/message_types.py

Defines the protocol message type constants used between the Battleship client
and server.

Keeping all message type names in one place avoids hardcoded string literals
throughout the networking code and helps prevent typos.
"""

from __future__ import annotations


class MessageTypes:
    """
    Namespace for all supported network message types.

    These are grouped by purpose:
    - connection / session
    - setup
    - gameplay
    - state sync
    - errors / status
    """

    _ALL_TYPES_CACHE: set[str] | None = None

    # Connection / session lifecycle
    JOIN = "join"
    ASSIGN_PLAYER = "assign_player"
    READY = "ready"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"
    OPPONENT_CONNECTION = "opponent_connection"

    # Setup / ship placement
    PLACE_SHIP = "place_ship"
    PLACE_SHIP_RESULT = "place_ship_result"
    SETUP_COMPLETE = "setup_complete"
    WAITING_FOR_OPPONENT_SETUP = "waiting_for_opponent_setup"

    # Game lifecycle
    START_GAME = "start_game"
    GAME_OVER = "game_over"
    FORFEIT = "forfeit"

    # Turn / attack flow
    ATTACK = "attack"
    ATTACK_RESULT = "attack_result"
    TURN_UPDATE = "turn_update"

    # Board / state sync
    STATE_SNAPSHOT = "state_snapshot"
    BOARD_UPDATE = "board_update"

    # General responses / status
    INFO = "info"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    @classmethod
    def all_types(cls) -> set[str]:
        """
        Return the set of all declared message type string values.
        Useful for validation, debugging, or protocol checks.
        """
        if cls._ALL_TYPES_CACHE is None:
            cls._ALL_TYPES_CACHE = {
                value
                for name, value in vars(cls).items()
                if name.isupper() and isinstance(value, str)
            }
        return cls._ALL_TYPES_CACHE.copy()

    @classmethod
    def is_valid(cls, message_type: str | None) -> bool:
        """
        Return True if the given value is a known protocol message type.
        """
        return isinstance(message_type, str) and message_type in cls.all_types()