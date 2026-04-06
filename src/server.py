"""
server.py

Top-level Battleship server process.

This module:
- opens a TCP server socket
- accepts client connections
- reads newline-delimited JSON messages from clients
- passes messages to ServerController
- sends outbound responses/events back to the appropriate clients
- preserves match state across disconnect/reconnects

This file owns transport/socket concerns. Core game rules live in the core/
package, and session/message handling lives in network/server_controller.py.
"""

from __future__ import annotations

import socket
import threading
import uuid
from typing import Dict, List, Optional, Tuple

from network.protocol import Protocol
from network.server_controller import OutboundEvent, ServerController
from utils.constants import SERVER_HOST, SERVER_PORT


ClientAddr = Tuple[str, int]


class BattleshipServer:
    """
    TCP server for a 2-player Battleship match.

    Design:
    - one shared ServerController instance
    - one thread per connected client
    - connection IDs are generated server-side
    - match state persists even if a player disconnects
    """

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT) -> None:
        self.host = host
        self.port = port

        self.controller = ServerController()

        self._server_socket: Optional[socket.socket] = None
        self._client_sockets: Dict[str, socket.socket] = {}
        self._lock = threading.RLock()
        self._running = False

    # ====================== Lifecycle ======================
    def start(self) -> None:
        """
        Start the server and begin accepting clients.
        """
        if self._running:
            raise RuntimeError("Server is already running.")

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen()
        self._server_socket.settimeout(1.0)  # <- important

        self._running = True
        print(f"Battleship server listening on {self.host}:{self.port}")

        try:
            while self._running:
                try:
                    client_socket, client_addr = self._server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if not self._running:
                        break
                    raise

                connection_id = self._generate_connection_id()
                with self._lock:
                    self._client_sockets[connection_id] = client_socket

                print(f"Accepted connection from {client_addr} as {connection_id}")

                thread = threading.Thread(
                    target=self._handle_client,
                    args=(connection_id, client_socket, client_addr),
                    daemon=True,
                )
                thread.start()

        finally:
            self.stop()

    def stop(self) -> None:
        """
        Stop the server and close all sockets.

        Safe to call multiple times.
        """
        if not self._running and self._server_socket is None:
            return

        self._running = False

        with self._lock:
            for _, sock in list(self._client_sockets.items()):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass
            self._client_sockets.clear()

        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        print("Server stopped.")

    # ====================== Internal connection handling ======================
    def _generate_connection_id(self) -> str:
        """Return a unique server-side connection ID."""
        return str(uuid.uuid4())

    def _handle_client(
        self,
        connection_id: str,
        client_socket: socket.socket,
        client_addr: ClientAddr,
    ) -> None:
        """
        Handle one connected client until disconnect.
        """
        reader = None

        try:
            reader = client_socket.makefile("rb")

            while self._running:
                line = reader.readline()
                if not line:
                    break

                try:
                    message = Protocol.decode_message(line)
                    Protocol.validate_message(message)
                except ValueError as exc:
                    self._send_to_connection(
                        connection_id,
                        Protocol.make_error(f"Malformed message: {exc}"),
                    )
                    continue

                print(f"Received from {client_addr} ({connection_id}): {message}")

                with self._lock:
                    events = self.controller.handle_message(connection_id, message)

                self._dispatch_events(events)

        except OSError as exc:
            print(f"Connection error with {client_addr} ({connection_id}): {exc}")

        finally:
            if reader is not None:
                try:
                    reader.close()
                except OSError:
                    pass

            self._cleanup_connection(connection_id, client_addr)

    def _cleanup_connection(self, connection_id: str, client_addr: object) -> None:
        """
        Clean up after a client disconnects and notify the controller.
        """
        print(f"Closing connection for {client_addr} ({connection_id})")

        with self._lock:
            disconnect_events = self.controller.disconnect(connection_id)

            sock = self._client_sockets.pop(connection_id, None)
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass

        self._dispatch_events(disconnect_events)

    # ====================== Outbound messaging ======================
    def _dispatch_events(self, events: List[OutboundEvent]) -> None:
        """
        Send each outbound event returned by the controller.
        """
        for event in events:
            if event.target is None:
                self._broadcast(event.message)
            else:
                self._send_to_connection(event.target, event.message)

    def _send_to_connection(self, connection_id: str, message: dict) -> None:
        """
        Send one protocol message to a specific connected client.
        """
        encoded = Protocol.encode_message(message)

        with self._lock:
            sock = self._client_sockets.get(connection_id)

        if sock is None:
            return

        try:
            sock.sendall(encoded)
        except OSError as exc:
            print(f"Failed to send to {connection_id}: {exc}")
            self._cleanup_connection(connection_id, client_addr="unknown")

    def _broadcast(self, message: dict) -> None:
        """
        Send one message to all currently connected clients.
        """
        encoded = Protocol.encode_message(message)

        with self._lock:
            items = list(self._client_sockets.items())

        for connection_id, sock in items:
            try:
                sock.sendall(encoded)
            except OSError as exc:
                print(f"Failed to broadcast to {connection_id}: {exc}")
                self._cleanup_connection(connection_id, client_addr="unknown")


def main() -> None:
    """
    Entry point for running the Battleship server directly.
    """
    server = BattleshipServer()

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()


if __name__ == "__main__":
    main()