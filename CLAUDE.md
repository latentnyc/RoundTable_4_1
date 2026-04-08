# RoundTable 4.1

AI-powered TTRPG (D&D 5e) with real-time multiplayer combat and an AI Dungeon Master.

## Quick Start

```bash
./scripts/dev-start.sh          # Start everything (Docker, Firebase, backend, frontend)
./scripts/dev-stop.sh           # Stop all services
./scripts/dev-status.sh         # Check what's running
./scripts/dev-logs.sh backend   # Tail a specific service's logs
```

**Prerequisites**: Docker Desktop, Java 21 (`brew install openjdk@21`), Python 3.11, Node.js 20+

**Flags**: `--skip-deps` (skip pip/npm install), `--reset-db` (wipe and recreate database)

### Quick Test Game

After startup, a "Dev Test — Goblin Combat" campaign is auto-seeded with the Gemini API key pre-configured.

1. Log in (any Google account via Firebase emulator)
2. Navigate to `http://localhost:3000/campaign_dash/dev-test-campaign-001`
3. Click **"Quick Join"** (yellow banner) — creates a full party, skips the character wizard:
   - **Elara Nightwhisper** — High Elf Wizard (you, human-controlled) with Fire Bolt, Magic Missile, Shield
   - **Theron Swiftwind** — Wood Elf Ranger (AI) with Longbow + Shortsword
   - **Bruna Stonefist** — Human Fighter (AI) with Greataxe + Shield + Chain Mail
4. Click **"Enter Campaign"** — you're in a room with a hostile goblin and two doors

Use `--reset-db` to wipe everything and start fresh: `./scripts/dev-start.sh --reset-db`

## Architecture

```
┌─────────────┐    WebSocket (Socket.IO)    ┌──────────────┐    asyncpg    ┌────────────┐
│  React 19   │◄──────────────────────────►│  FastAPI      │◄────────────►│ PostgreSQL │
│  (Vite)     │    REST (Axios)             │  (Uvicorn)    │              │ (Docker)   │
│  port 3000  │◄──────────────────────────►│  port 8000    │              │ port 5432  │
└─────────────┘                             └──────┬───────┘              └────────────┘
                                                   │
                                            Gemini API (LangGraph)
                                            Firebase Auth (emulators locally)
```

### State Management

**Game state** is a JSON blob stored in `game_states` table. Entities (players, enemies, NPCs) are stored in separate tables (`characters`, `monsters`, `npcs`) and **hydrated** on load.

- `StateService.get_game_state()` — loads JSON skeleton + hydrates entities from their tables
- `StateService.save_game_state()` — saves entity data to their tables, then saves the skeleton (with entity IDs only) back to `game_states`
- `StateService.emit_state_update()` — generates JSON Patch (RFC 6902) between old and new state, sends delta over WebSocket

**Client-side**: `SocketProvider.tsx` receives `game_state_update` (full state) or `game_state_patch` (delta). Uses `fast-json-patch` to apply patches. Zustand stores (`socket.ts`) hold reactive state.

### Combat Loop

1. `CombatService.start_combat()` — rolls initiative, sets turn order
2. `TurnManager.advance_turn()` — acquires advisory lock, advances `turn_index`, saves state
3. For AI turns: `TurnManager._execute_ai_turn_sequence()` loops until a human turn is reached (circuit breaker at 50)
4. AI actions: `AITurnService` does pathfinding (BFS on hex grid) + attack resolution via `GameEngine`

### Real-Time Sync

- Full state sent on `join_campaign` (connect/reconnect)
- Incremental JSON Patches for all subsequent changes
- `StateService._last_broadcasted_state` (class-level dict) caches last-sent state per campaign for diffing

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI + Socket.IO ASGI app, startup hooks |
| `backend/app/services/state_service.py` | State hydration, persistence, patch broadcasting |
| `backend/app/services/turn_manager.py` | Combat turn loop with advisory locks |
| `backend/app/services/combat_service.py` | Initiative, turn order, attack resolution |
| `backend/app/services/ai_service.py` | LLM invocation (Gemini via LangChain) |
| `backend/app/models.py` | Pydantic models: GameState, Player, Enemy, NPC, Coordinates |
| `backend/game_engine/engine.py` | D&D 5e rules engine (attack/spell resolution) |
| `backend/db/schema.py` | SQLAlchemy table definitions (24 tables) |
| `frontend/src/lib/SocketProvider.tsx` | WebSocket connection, state sync, patch application |
| `frontend/src/lib/socket.ts` | Zustand store for game state, messages, debug logs |
| `frontend/src/components/BattlemapPanel.tsx` | SVG hex grid rendering |
| `frontend/src/components/GameInterface.tsx` | Main game UI orchestrator |

## Known Fragile Areas

1. **`StateService._last_broadcasted_state`** — class-level dict, never cleared when clients disconnect. Can produce invalid patches after all players leave and rejoin.

2. **`SocketProvider.tsx:134`** — patch application failure is caught but only logged to console. No recovery or resync. Client state can silently diverge from server.

3. **`TurnManager` lock cycling** — advisory locks prevent race conditions but the lock → advance → save → emit flow is complex. Errors mid-sequence can leave state inconsistent.

4. **Entity hydration** — `_hydrate_party()` has many fallback defaults and type coercions. If sheet_data structure changes, hydration can silently produce wrong values.

5. **`ErrorBoundary`** — component exists at `frontend/src/components/ErrorBoundary.tsx` but is never mounted in `App.tsx`. A React rendering error crashes the entire app.

## Environment Variables

### Backend (`backend/.env`)
- `DATABASE_URL` — PostgreSQL connection string (asyncpg driver)
- `GEMINI_API_KEY` — Google AI Studio API key for Gemini
- `FIRESTORE_EMULATOR_HOST` — `127.0.0.1:8080` for local dev
- `FIREBASE_AUTH_EMULATOR_HOST` — `127.0.0.1:9099` for local dev
- `GCLOUD_PROJECT` — `roundtable41-1dc2c`

### Frontend (`frontend/.env`)
- `VITE_API_URL` — Backend URL (`http://localhost:8000`)
- `VITE_FIREBASE_*` — Firebase config (API key, auth domain, project ID, etc.)

## Tests

```bash
cd backend && ./venv/bin/pytest                    # Run all tests
cd backend && ./venv/bin/pytest -m "not integration"  # Unit tests only
```

- Backend tests in `backend/tests/test_*.py` (pytest, async)
- Verification scripts in `backend/scripts/verification/` (one-off diagnostics, not tests)
- No frontend tests yet

## Tech Stack

**Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, asyncpg, Socket.IO, LangGraph, LangChain, Gemini API, Firebase Admin SDK, Alembic
**Frontend**: React 19, TypeScript 5.9, Vite 7, Zustand, Socket.IO Client, Tailwind CSS 4, Framer Motion, fast-json-patch
**Database**: PostgreSQL 15 (Docker)
**Auth**: Firebase Authentication (emulators for local dev)
