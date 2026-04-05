"""
network/client_connection.py

Provides the client-side network connection wrapper for Battleship.
"""

from __future__ import annotations

import socket
from typing import Any, Dict, Optional

from network.protocol import Protocol


class ClientConnection:
    """
    Client-side TCP connection wrapper for Battleship.

    Messages are sent and received using newline-delimited JSON via Protocol.
    """

    def __init__(self, host: str, port: int, timeout: Optional[float] = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

        self._socket: Optional[socket.socket] = None
        self._reader = None
        self._writer = None

    def connect(self) -> None:
        """
        Open a TCP connection to the server.
        """
        if self.is_connected():
            raise ConnectionError("Client is already connected.")

        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            if self.timeout is not None:
                sock.settimeout(self.timeout)

            self._socket = sock
            self._reader = sock.makefile("rb")
            self._writer = sock.makefile("wb")

        except OSError as exc:
            self.close()
            raise ConnectionError(
                f"Failed to connect to server at {self.host}:{self.port}: {exc}"
            ) from exc

    def is_connected(self) -> bool:
        """
        Return True if the client currently has an active connection.
        """
        return self._socket is not None and self._reader is not None and self._writer is not None

    def send_message(self, message: Dict[str, Any]) -> None:
        """
        Send one protocol message to the server.
        """
        if not self.is_connected():
            raise ConnectionError("Cannot send message: client is not connected.")

        try:
            encoded = Protocol.encode_message(message)
            self._writer.write(encoded)
            self._writer.flush()
        except OSError as exc:
            self.close()
            raise ConnectionError(f"Failed to send message: {exc}") from exc

    def receive_message(self) -> Dict[str, Any]:
        """
        Receive one protocol message from the server.
        """
        if not self.is_connected():
            raise ConnectionError("Cannot receive message: client is not connected.")

        try:
            line = self._reader.readline()
        except OSError as exc:
            self.close()
            raise ConnectionError(f"Failed to receive message: {exc}") from exc

        if not line:
            self.close()
            raise ConnectionError("Server closed the connection.")

        return Protocol.decode_message(line)

    def request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message and wait for a response.
        """
        self.send_message(message)
        return self.receive_message()

    def close(self) -> None:
        """
        Close the client connection safely.
        """
        if self._reader:
            try:
                self._reader.close()
            except OSError:
                pass
            self._reader = None

        if self._writer:
            try:
                self._writer.close()
            except OSError:
                pass
            self._writer = None

        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def __enter__(self) -> "ClientConnection":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()