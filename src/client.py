"""
client.py

Top-level Battleship client application.

This module:
- connects to the Battleship server
- joins the match
- receives and interprets server messages
- collects user input through TerminalUI
- sends setup and attack actions back to the server

This file owns the high-level client flow, but delegates transport to
ClientConnection and presentation/input to TerminalUI.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from network.client_connection import ClientConnection
from network.message_types import MessageTypes
from network.protocol import Protocol
from ui.terminal_ui import TerminalUI
from utils.constants import SERVER_HOST, SERVER_PORT


class BattleshipClient:
    """
    High-level Battleship terminal client.

    Responsibilities:
    - maintain local knowledge such as assigned player ID
    - interpret server messages
    - ask the UI for user actions when appropriate
    - send protocol messages to the server
    """

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT) -> None:
        self.host = host
        self.port = port

        self.connection = ClientConnection(host, port)
        self.ui = TerminalUI()

        self.player_id: Optional[int] = None
        self.running: bool = False

    # ====================== Lifecycle ======================
    def run(self) -> None:
        """
        Start the client application and process messages until exit.
        """
        self.ui.show_info(f"Connecting to server at {self.host}:{self.port}...")

        try:
            self.connection.connect()
        except ConnectionError as exc:
            self.ui.show_error(str(exc))
            return

        self.running = True
        self.ui.show_info("Connected.")

        try:
            self._send_join()

            while self.running:
                message = self.connection.receive_message()
                self._handle_message(message)

        except ConnectionError as exc:
            self.ui.show_error(str(exc))
        except KeyboardInterrupt:
            self.ui.show_info("Interrupted by user.")
        finally:
            self.connection.close()
            self.ui.show_info("Disconnected.")

    def stop(self) -> None:
        """Stop the client loop."""
        self.running = False

    # ====================== Outbound helpers ======================
    def _send_join(self) -> None:
        """Send the initial JOIN message to the server."""
        self.connection.send_message(
            Protocol.make_message(MessageTypes.JOIN)
        )

    def _send_place_ship(self, ship_name: str, row: int, col: int, horizontal: bool) -> None:
        """Send a PLACE_SHIP request."""
        self.connection.send_message(
            Protocol.make_message(
                MessageTypes.PLACE_SHIP,
                ship_name=ship_name,
                row=row,
                col=col,
                horizontal=horizontal,
            )
        )

    def _send_attack(self, row: int, col: int) -> None:
        """Send an ATTACK request."""
        self.connection.send_message(
            Protocol.make_message(
                MessageTypes.ATTACK,
                row=row,
                col=col,
            )
        )

    # ====================== Inbound message handling ======================
    def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handle one message received from the server.
        """
        message_type = message.get("type")

        if message_type == MessageTypes.ASSIGN_PLAYER:
            self._handle_assign_player(message)
            return

        if message_type == MessageTypes.STATE_SNAPSHOT:
            self._handle_state_snapshot(message)
            return

        if message_type == MessageTypes.PLACE_SHIP_RESULT:
            self._handle_place_ship_result(message)
            return

        if message_type == MessageTypes.SETUP_COMPLETE:
            self._handle_setup_complete(message)
            return

        if message_type == MessageTypes.WAITING_FOR_OPPONENT_SETUP:
            self.ui.show_info("All your ships are placed. Waiting for your opponent to finish setup.")
            return

        if message_type == MessageTypes.START_GAME:
            self._handle_start_game(message)
            return

        if message_type == MessageTypes.ATTACK_RESULT:
            self._handle_attack_result(message)
            return

        if message_type == MessageTypes.TURN_UPDATE:
            self._handle_turn_update(message)
            return

        if message_type == MessageTypes.OPPONENT_CONNECTION:
            self._handle_opponent_connection(message)
            return

        if message_type == MessageTypes.GAME_OVER:
            self._handle_game_over(message)
            return

        if message_type == MessageTypes.INFO:
            self.ui.show_info(message.get("message", "Info"))
            return

        if message_type == MessageTypes.ERROR or message_type == "error":
            self.ui.show_error(message.get("error", "Unknown error"))
            return

        if message_type == MessageTypes.PONG:
            return

        self.ui.show_error(f"Received unknown message from server: {message}")

    # ====================== Specific message handlers ======================
    def _handle_assign_player(self, message: Dict[str, Any]) -> None:
        """
        Handle initial seat assignment or reconnection assignment.
        """
        self.player_id = message["player_id"]
        reconnected = message.get("reconnected", False)

        if reconnected:
            self.ui.show_info(f"Reconnected as Player {self.player_id}.")
        else:
            self.ui.show_info(f"You are Player {self.player_id}.")

    def _handle_state_snapshot(self, message: Dict[str, Any]) -> None:
        """
        Handle a full state snapshot from the server.
        """
        state = message.get("state", {})
        self.ui.render_state(state)

        if not state:
            return

        if not state.get("started", False):
            self._maybe_prompt_ship_placement(state)
        elif not state.get("game_over", False) and state.get("current_turn") == self.player_id:
            self._maybe_prompt_attack(state)

    def _handle_place_ship_result(self, message: Dict[str, Any]) -> None:
        """
        Handle the result of a ship placement attempt.
        """
        ok = message.get("ok", False)
        if not ok:
            self.ui.show_error(message.get("error", "Ship placement failed."))
            self._request_next_ship_placement()
            return

        ship_name = message.get("ship_name", "Unknown ship")
        placed_ship_count = message.get("placed_ship_count")
        total_ships = message.get("total_ships")

        self.ui.show_info(
            f"Placed {ship_name} "
            f"({placed_ship_count}/{total_ships} ships placed)."
        )

        board = message.get("your_board")
        if board is not None:
            self.ui.render_single_board("Your Board", board)

        self._request_next_ship_placement()

    def _handle_setup_complete(self, message: Dict[str, Any]) -> None:
        """
        Handle notification that this player completed setup.
        """
        self.ui.show_info("Setup complete.")

    def _handle_start_game(self, message: Dict[str, Any]) -> None:
        """
        Handle game start notification.
        """
        self.ui.show_info("The game has started.")
        state = message.get("state", {})
        self.ui.render_state(state)

        if state.get("current_turn") == self.player_id:
            self.ui.show_info("It is your turn.")
            self._maybe_prompt_attack(state)
        else:
            self.ui.show_info("Waiting for opponent's move.")

    def _handle_attack_result(self, message: Dict[str, Any]) -> None:
        """
        Handle the outcome of an attack.
        """
        ok = message.get("ok", False)
        if not ok:
            self.ui.show_error(message.get("error", "Attack failed."))
            return

        attacker_id = message.get("attacker_id")
        row = message.get("row")
        col = message.get("col")
        hit = message.get("hit", False)
        sunk = message.get("sunk", False)
        ship_name = message.get("ship_name")
        game_over = message.get("game_over", False)

        if attacker_id == self.player_id:
            if sunk and ship_name:
                self.ui.show_info(f"Your attack at ({row}, {col}) sunk the opponent's {ship_name}.")
            elif hit:
                self.ui.show_info(f"Your attack at ({row}, {col}) was a hit.")
            else:
                self.ui.show_info(f"Your attack at ({row}, {col}) was a miss.")
        else:
            if sunk and ship_name:
                self.ui.show_info(f"Opponent attacked ({row}, {col}) and sunk your {ship_name}.")
            elif hit:
                self.ui.show_info(f"Opponent attacked ({row}, {col}) and hit one of your ships.")
            else:
                self.ui.show_info(f"Opponent attacked ({row}, {col}) and missed.")

        state = message.get("state", {})
        self.ui.render_state(state)

        if game_over:
            return

    def _handle_turn_update(self, message: Dict[str, Any]) -> None:
        """
        Handle turn progression update.
        """
        current_turn = message.get("current_turn")
        turn_count = message.get("turn_count")

        if current_turn == self.player_id:
            self.ui.show_info(f"Turn {turn_count}: it is your turn.")
            self._request_attack()
        else:
            self.ui.show_info(f"Turn {turn_count}: waiting for opponent.")

    def _handle_opponent_connection(self, message: Dict[str, Any]) -> None:
        """
        Handle opponent disconnect/reconnect notifications.
        """
        connected = message.get("connected", False)
        reconnected = message.get("reconnected", False)

        if connected and reconnected:
            self.ui.show_info("Your opponent reconnected. The game can continue.")
        elif connected:
            self.ui.show_info("Your opponent connected.")
        else:
            self.ui.show_info("Your opponent disconnected. The game is paused.")

    def _handle_game_over(self, message: Dict[str, Any]) -> None:
        """
        Handle game over notification.
        """
        winner_id = message.get("winner_id")
        state = message.get("state", {})

        self.ui.render_state(state)

        if winner_id == self.player_id:
            self.ui.show_info("Game over. You win!")
        else:
            self.ui.show_info("Game over. You lose.")

        self.stop()

    # ====================== Prompt helpers ======================
    def _maybe_prompt_ship_placement(self, state: Dict[str, Any]) -> None:
        """
        During setup, ask for the next ship placement if needed.
        """
        if state.get("your_ready", False):
            return

        self._request_next_ship_placement()

    def _request_next_ship_placement(self) -> None:
        """
        Ask the UI for the next ship placement request and send it.
        """
        placement = self.ui.prompt_ship_placement()
        if placement is None:
            self.ui.show_info("Exiting.")
            self.stop()
            return

        ship_name, row, col, horizontal = placement
        self._send_place_ship(ship_name, row, col, horizontal)

    def _maybe_prompt_attack(self, state: Dict[str, Any]) -> None:
        """
        If it is the player's turn, prompt for an attack.
        """
        if state.get("game_over", False):
            return

        if state.get("current_turn") != self.player_id:
            return

        self._request_attack()

    def _request_attack(self) -> None:
        """
        Ask the UI for attack coordinates and send them.
        """
        attack = self.ui.prompt_attack()
        if attack is None:
            self.ui.show_info("Exiting.")
            self.stop()
            return

        row, col = attack
        self._send_attack(row, col)


def main() -> None:
    """
    Entry point for running the Battleship client directly.
    """
    client = BattleshipClient()

    try:
        client.run()
    except KeyboardInterrupt:
        print("\nClient closed.")


if __name__ == "__main__":
    main()