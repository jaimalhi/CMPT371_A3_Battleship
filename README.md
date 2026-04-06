# CMPT 371 A3 Socket Programming — Battleship

**Course:** CMPT 371 — Data Communications & Networking
**Instructor:** Mirza Zaeem Baig
**Semester:** Spring 2026

## Group Members

| Name | Student ID | Email |
| :---- | :---- | :---- |
| Julian Loewenherz | 301579327 | jbl22@sfu.ca |
| Jaivir Malhi | 301457742 | jma225@sfu.ca |

---

## 1. Project Overview & Description

This project is a two-player networked Battleship game built using Python's socket API over TCP. Two clients connect to a central server, are assigned player slots, and play a full game of Battleship against each other in real time.

The server is fully authoritative — all game rules, turn order, board validation, and win-condition checking are enforced server-side. Clients act as thin interfaces: they send actions and render state only. This design prevents desync and ensures players cannot cheat by modifying local state.

The codebase follows a clean four-layer architecture:

| Layer | Modules | Responsibility |
| :---- | :---- | :---- |
| **Core Game Logic** | `core/` | Pure rules — no sockets, no UI |
| **Protocol** | `network/protocol.py`, `network/message_types.py` | Message format, validation |
| **Networking** | `network/server_controller.py`, `network/client_connection.py` | TCP transport, concurrency |
| **Presentation** | `ui/terminal_ui.py` | Terminal rendering and input |

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
│   └── terminal_ui.py
└── utils/
    └── constants.py
```

---

## 2. System Limitations & Edge Cases

### Concurrency — Two Clients, One Game

**Solution:** The server spawns one thread per connected client using Python's `threading` module. A single shared `ServerController` instance manages all game state under a reentrant lock (`threading.RLock`), ensuring thread-safe access. This is sufficient and intentional for a fixed 2-player game.

**Limitation:** The server hosts exactly one game session. A third connection attempt is rejected with an error message. An enterprise application would support multiple simultaneous sessions with a thread pool or `asyncio`.

### TCP Stream Buffering

**Solution:** TCP delivers a continuous byte stream, not discrete messages. We implement application-layer message framing using newline-delimited JSON: every message is serialized as a single JSON object and terminated with `\n`. The receiver reads line-by-line, ensuring messages are always parsed atomically even if multiple arrive in the same TCP segment.

### Disconnect & Reconnect Handling

**Solution:** If a player disconnects mid-game, the server marks them as disconnected and the game enters a `PAUSED` state. The remaining player is notified. When the disconnected player reconnects and sends a `join` message with the same username, the server matches them by username and restores their session. The game resumes from where it left off.

**Limitation:** Reconnect relies on username matching, not a secure token. A malicious user who knows an opponent's username could theoretically impersonate them.

### Input Validation & Security

**Solution:** The `TerminalUI` class validates all user input before sending it: coordinates are checked to be integers within bounds (0–7), ship names are normalized against the known ship list, and direction must be `h` or `v`. The server independently validates every incoming message — checking game phase, player turn, coordinate bounds, and whether a cell has already been attacked — and responds with explicit error messages for any invalid action.

**Limitation:** Server-side validation assumes well-formed JSON integers in received messages. A client that manually crafts and sends malformed payloads could trigger error responses but cannot corrupt game state.

---

## 3. Video Demo

Our 2-minute video demonstration covering connection establishment, ship placement, real-time gameplay, disconnect/reconnect handling, and game termination can be viewed here:

[**▶️ Watch Project Demo on YouTube**](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

---

## 4. Prerequisites

To run this project, you need:

- **Python 3.10** or higher
- No external `pip` packages required — only standard library modules are used: `socket`, `threading`, `json`, `uuid`, `sys`, `dataclasses`
- (Optional) VS Code or any terminal emulator

---

## 5. Step-by-Step Run Guide

All commands should be run from the `src/` directory. You will need **three separate terminal windows**: one for the server and one for each client.

### Step 1 — Start the Server

```bash
python server.py
```

Expected output:
```
Battleship server listening on 127.0.0.1:5050
```

The server is now listening on port `5050` for incoming connections.

### Step 2 — Connect Player 1

Open a new terminal window and run:

```bash
python client.py
```

Expected output:
```
[INFO] Connecting to server at 127.0.0.1:5050...
[INFO] Connected.
[INFO] You are Player 1.
```

Player 1 will immediately be prompted to place their ships.

### Step 3 — Connect Player 2

Open a third terminal window and run:

```bash
python client.py
```

Expected output:
```
[INFO] Connecting to server at 127.0.0.1:5050...
[INFO] Connected.
[INFO] You are Player 2.
```

Player 2 will also be prompted to place their ships.

### Step 4 — Ship Placement (Both Players)

Each player places 5 ships one at a time. When prompted, enter the ship name, starting row, starting column, and orientation:

```
Place ship as: <ship_name> <row> <col> <h/v> (or type 'quit'):
```

**Example:**
```
Place ship as: Carrier 0 0 h
Place ship as: Battleship 2 3 v
Place ship as: Cruiser 4 0 h
Place ship as: Destroyer1 6 5 v
Place ship as: Destroyer2 7 0 h
```

**Available ships:**

| Ship | Length |
| :---- | :---- |
| Carrier | 4 |
| Battleship | 3 |
| Cruiser | 3 |
| Destroyer1 | 2 |
| Destroyer2 | 2 |

**Board coordinates:** rows and columns are `0`–`7` on an 8×8 grid. Orientation `h` places the ship horizontally (across columns); `v` places it vertically (down rows). Ships cannot overlap or go out of bounds.

Once both players have placed all 5 ships, the game starts automatically.

### Step 5 — Gameplay

When it is your turn, you will be prompted:

```
Attack as: <row> <col> (or type 'quit'):
```

**Example:**
```
Attack as: 3 5
```

**Rules:**
- A **hit** lets you attack again immediately on the same turn.
- A **miss** ends your turn and passes play to your opponent.
- Sinking a ship is announced to both players.
- The game ends when all of one player's ships are sunk.

**Board symbols:**

| Symbol | Meaning |
| :---- | :---- |
| `.` | Unknown / untouched |
| `S` | Your ship (own board only) |
| `X` | Hit |
| `O` | Miss |

### Step 6 — Game Over

When all ships of one player are sunk, both players see the final board state and a win/loss message. The client then disconnects automatically.

---

## 6. Technical Protocol Details (JSON over TCP)

We designed a custom application-layer protocol using newline-delimited JSON over TCP. Every message is a UTF-8 JSON object terminated by `\n`. This makes framing trivial for stream sockets and keeps messages human-readable.

### Message Format

```json
{"type": "<message_type>", ...payload fields}
```

### Client → Server Messages

| Type | Purpose | Key Fields |
| :---- | :---- | :---- |
| `join` | Join or reconnect to the game | — |
| `place_ship` | Place a ship during setup | `ship_name`, `row`, `col`, `horizontal` |
| `attack` | Fire at a coordinate | `row`, `col` |

### Server → Client Messages

| Type | Purpose | Key Fields |
| :---- | :---- | :---- |
| `assign_player` | Confirm seat and player ID | `player_id`, `reconnected` |
| `place_ship_result` | Result of a placement attempt | `ok`, `ship_name`, `placed_ship_count`, `total_ships`, `your_board` |
| `setup_complete` | All ships placed by this player | — |
| `waiting_for_opponent_setup` | Waiting for other player to finish | — |
| `start_game` | Both players ready, game begins | `state` |
| `attack_result` | Outcome of an attack | `ok`, `hit`, `sunk`, `ship_name`, `attacker_id`, `row`, `col`, `state` |
| `turn_update` | Turn has changed | `current_turn`, `turn_count` |
| `opponent_connection` | Opponent connected or disconnected | `connected`, `reconnected` |
| `game_over` | Game ended | `winner_id`, `state` |
| `state_snapshot` | Full state sync | `state` |
| `error` | Describes a failure | `error` |

### Example Exchange

**Placement:**
```json
// Client sends:
{"type":"place_ship","ship_name":"Carrier","row":0,"col":0,"horizontal":true}

// Server responds:
{"type":"place_ship_result","ok":true,"ship_name":"Carrier","placed_ship_count":1,"total_ships":5}
```

**Attack:**
```json
// Client sends:
{"type":"attack","row":3,"col":5}

// Server responds:
{"type":"attack_result","ok":true,"hit":true,"sunk":false,"ship_name":"Cruiser","attacker_id":1,"row":3,"col":5,"game_over":false,"state":{...}}
```

**Error:**
```json
{"type":"error","error":"Not your turn"}
```

### State Visibility

Each client receives a filtered state snapshot. They can see their own full board (ships, hits, misses) and the opponent's board with only hits and misses revealed — opponent ship positions remain hidden until hit.

---

## 7. Academic Integrity & References

**Code Origin:**
- Gen AI was used to assist in generating the initial file structure and code comments.
- The core game logic, protocol design, state management, and networking were written by the group.

**GenAI Usage:**
- ChatGPT was used to assist in generating the file structure and code comments.
- ChatGPT was used to assist in generating the terminal UI.
- Claude was used to assist in `README.md` writing and polishing.
- Claude was used in creating the tkinter frontend GUI. 

**References:**
- [Socket Programming in Python (Guide) — Real Python](https://realpython.com/python-sockets/)
- [Real Python: Intro to Python Threading](https://realpython.com/intro-to-python-threading/)

- [Tkinter Beginner Course - Python GUI Development (https://www.youtube.com/watch?v=ibf5cx221hk)]