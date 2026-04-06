# Battleship

A networked, two-player Battleship game built with a clean four-layer architecture. The server is fully authoritative, game logic is decoupled from networking, and the UI layer is swappable - making it easy to add a GUI client on top of the existing backend.

---

## Table of Contents

- [Architecture](#architecture)
- [Game Rules](#game-rules)
- [Game State](#game-state)
- [Protocol](#protocol)
- [Networking](#networking)
- [Error Handling](#error-handling)
- [Getting Started](#getting-started)
- [Future Extensions](#future-extensions)

---

## Architecture

### File Structure
```
src/
├── server.py
├── client.py
├── core/
│   ├── game_state.py
│   ├── board.py
│   ├── ship.py
│   └── player_state.py
├── network/
│   ├── protocol.py
│   ├── server_controller.py
│   ├── client_connection.py
│   └── message_types.py
├── ui/
│   ├── terminal_ui.py
│   └── gui_ui.py
└── utils/
    └── constants.py
README.md
```

### Layers

| Layer | Responsibility |
|---|---|
| **Core Game Logic** | Pure rules, no sockets or UI |
| **Protocol** | Message format and validation |
| **Networking** | TCP connections, concurrency |
| **Presentation** | Terminal / GUI |

### Principles

- The **server is authoritative** — all rules are enforced server-side to prevent desync and cheating.
- The **client is a thin interface** — it sends actions and renders state only.
- Game logic and UI are fully independent of each other and of networking.

### Server Model

- One server instance hosts exactly one game.
- Maximum of 2 players per server.
- Third connection attempt is rejected with an error.

**Connecting:**
```bash
python client.py <port>
```
Default port: `5050`

**Player assignment:**
- First client → Player 1
- Second client → Player 2

---

## Game Rules

### Board

- 8 × 8 grid
- Coordinates: `(row, col)`

### Ships

```python
SHIP_SIZES = {
    "Carrier": 4,
    "Battleship": 3,
    "Cruiser": 3,
    "Destroyer1": 2,
    "Destroyer2": 2,
}
```

- Ships cannot overlap.
- Ships may touch.
- Ships must stay within bounds.

### Placement

Players place ships manually, then send:

```json
{"type": "ready"}
```

The game starts once both players are ready.

### Turns

- One shot per turn.
- **Hit** → player continues their turn.
- **Miss** → turn switches to the opponent.
- The server enforces all turn order.

### Attacking

```json
{"type": "attack", "row": 3, "col": 5}
```

The server validates: correct phase, correct player turn, valid coordinates, not already attacked.

Possible outcomes: `hit`, `miss`, `sunk`, `invalid`

### Winning

- All of one player's ships are sunk → that player loses.
- Turn limit reached (if enabled) → draw by default.

### Turn Limit (Optional)

| Field | Description |
|---|---|
| `turn_limit_enabled` | Enable/disable the feature |
| `turn_limit` | Maximum number of turns |
| `turn_count` | Current turn count |

A "turn" counts as one full attack sequence ending in a miss.

---

## Game State

### Phases

```
WAITING_FOR_PLAYERS → PLACEMENT → IN_PROGRESS → PAUSED → GAME_OVER
```

### Core Objects

**Ship** — `size`, `positions`, `hits`

**Board** — ships, attacked cells, placement validation, attack resolution

**PlayerState** — username, board, connection status, ready state, player ID

**GameState** — players, current turn, phase, winner, turn settings, paused state

### Connection Handling

| Event | Behavior |
|---|---|
| Join | Assigns player slot if available |
| Reconnect | Matches by username, restores session |
| Disconnect | Player marked disconnected; game enters `PAUSED` |
| Game full | Connection rejected with error |

**Join / reconnect message:**
```json
{"type": "join", "username": "alice"}
```

---

## Protocol

All messages are **newline-delimited JSON**.

### Client → Server

| Message | Purpose |
|---|---|
| `join` | Join or reconnect to game |
| `place_ship` | Place a ship manually |
| `ready` | Signal placement complete |
| `attack` | Fire at a coordinate |
| `get_state` | Request full state update |
| `quit` | Leave the game |

### Server → Client

| Message | Purpose |
|---|---|
| `join_ok` / `reconnect_ok` | Confirm join or reconnect |
| `error` | Describe a failure |
| `player_joined` | Notify other player joined |
| `place_result` | Confirm ship placement |
| `ready_ok` | Confirm ready signal |
| `game_start` | Both players ready |
| `your_turn` / `wait_turn` | Turn control |
| `attack_result` | Result of an attack |
| `game_over` | Game ended with outcome |
| `game_paused` / `game_resumed` | Pause state changes |
| `state` | Full state snapshot |

### State Visibility

Each client sees:
- Their own full board (all ships)
- Opponent's board — **revealed hits/misses only**
- Turn info and game status

Each client does **not** see:
- Opponent ship positions (unless hit)

---

## Networking

### Transport

- **TCP sockets** — reliable, ordered delivery

### Concurrency

- 1 main thread accepts connections
- 1 thread per client

This is sufficient for a 2-player game and keeps the implementation simple and readable.

### Project Structure

```
core/       # Pure game logic (no sockets, no UI)
network/    # Sockets, message handling, protocol
ui/         # Terminal & GUI interface
```

---

## Error Handling

The server responds with explicit error messages:

```json
{"type": "error", "message": "Not your turn"}
```

Handled cases include: game full, duplicate username, invalid placement, out-of-bounds coordinates, wrong turn, already attacked, game paused.

---

## Getting Started

**Start the server:**
```bash
python server.py
```

**Connect a client:**
```bash
python client.py <port>
```

Both players connect, place ships, and send `{"type": "ready"}` to begin.

---

## Future Extensions

- GUI client (reuses existing backend without changes)
- Multiple game sessions per server
- Spectator mode
- Token-based reconnect (instead of username matching)
- Improved turn-limit scoring