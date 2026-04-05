"""
network/protocol.py

Defines how Battleship messages are serialized and deserialized over the network.

This protocol uses newline-delimited JSON:
- each message is a JSON object
- each message ends with a newline character: '\n'

This makes message framing simple for TCP sockets while keeping messages easy to
debug and inspect.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from network.message_types import MessageTypes


class Protocol:
    """
    Utility class for encoding, decoding, and validating network messages.
    """

    @staticmethod
    def encode_message(message: Dict[str, Any]) -> bytes:
        """
        Convert a message dictionary into newline-delimited JSON bytes.

        Args:
            message: The message payload to send.

        Returns:
            Encoded bytes ready for socket transmission.

        Raises:
            ValueError: If the message is invalid or cannot be serialized to JSON.
        """
        Protocol.validate_message(message)

        try:
            serialized = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Failed to encode message as JSON: {exc}") from exc

        return (serialized + "\n").encode("utf-8")

    @staticmethod
    def decode_message(data: bytes) -> Dict[str, Any]:
        """
        Decode one newline-stripped JSON message from bytes into a dictionary.

        Args:
            data: Raw bytes for a single message, without the trailing newline.

        Returns:
            Decoded message dictionary.

        Raises:
            ValueError: If the data is not valid UTF-8, not valid JSON, or not
                        a JSON object.
        """
        try:
            text = data.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError(f"Failed to decode UTF-8 message: {exc}") from exc

        if not text:
            raise ValueError("Cannot decode an empty message.")

        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON message: {exc}") from exc

        Protocol.validate_message(obj)
        return obj

    @staticmethod
    def make_message(message_type: str, **payload: Any) -> Dict[str, Any]:
        """
        Build a protocol message dictionary.

        Args:
            message_type: The protocol message type string.
            **payload: Additional key/value pairs to include.

        Returns:
            A message dictionary with a required 'type' field.
        """
        if "type" in payload:
            raise ValueError("Payload must not include 'type'; use message_type instead.")

        if not MessageTypes.is_valid(message_type):
            raise ValueError(f"Unknown message type: {message_type}")

        message = {"type": message_type, **payload}
        return message

    @staticmethod
    def make_error(error_message: str, **extra: Any) -> Dict[str, Any]:
        """
        Build a standard error message dictionary.

        Args:
            error_message: Human-readable error description.
            **extra: Optional extra fields.

        Returns:
            Standardized error message payload.
        """
        if "type" in extra:
            raise ValueError("Extra payload must not include 'type'.")

        message = {
            "type": MessageTypes.ERROR,
            "error": error_message,
            **extra,
        }
        return message

    @staticmethod
    def validate_message(message: Dict[str, Any]) -> None:
        """
        Perform basic structural validation on a decoded message.

        Rules enforced:
        - message must be a dict
        - message must contain a string 'type' field
        - message type must be known

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary.")

        if "type" not in message:
            raise ValueError("Message is missing required field: 'type'.")

        message_type = message["type"]
        if not isinstance(message_type, str):
            raise ValueError("Message field 'type' must be a string.")

        if not MessageTypes.is_valid(message_type):
            raise ValueError(f"Unknown message type: {message_type}")