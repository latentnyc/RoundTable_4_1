# RoundTable 4.1

AI-powered tabletop RPG (D&D 5e) with real-time multiplayer combat and an AI Dungeon Master.

Players explore hex-based maps, fight monsters, loot corpses, and interact with NPCs — all narrated by an AI DM powered by Google's Gemini. AI party members fight alongside you with pathfinding and tactical combat.

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
Frontend (React 19 / Vite)          Backend (FastAPI / Uvicorn)         Database
port 3000                           port 8000                           port 5432
 +-----------------+  WebSocket     +------------------+   asyncpg     +-----------+
 | React + Zustand |<-------------->| FastAPI + SIO    |<------------>| PostgreSQL|
 | SVG Battlemap   |  REST (Axios)  | LangGraph/Gemini |              | (Docker)  |
 | Socket.IO Client|<-------------->| Firebase Auth    |              |           |
 +-----------------+                +------------------+              +-----------+
```

### How State Works

Game state is a JSON blob in the `game_states` table. Entities (players, enemies, NPCs) live in their own tables and are **hydrated** into the state on load.

- **Full state** sent on connect/reconnect via `game_state_update` event
- **Incremental patches** (JSON Patch RFC 6902) sent for all subsequent changes via `game_state_patch`
- Client applies patches with `fast-json-patch`; on failure, auto-requests full resync
- State version auto-increments on save for gap detection

### Combat Loop

1. `@attack` or hostile encounter triggers initiative rolls (1d20 + DEX)
2. Turn order established, active entity highlighted
3. On your turn: move (click hex) + act (`@attack`, `@cast`) + end turn
4. AI party members auto-execute: pathfind → move → attack nearest hostile
5. AI enemies do the same targeting your party
6. Combat ends when all hostiles are dead (victory) or party falls (defeat)

## Player Commands

| Command | Aliases | What it does |
|---------|---------|-------------|
| `@attack <target>` | `@atk`, `@a` | Attack with equipped weapon |
| `@cast <spell> [at <target>]` | `@c` | Cast a spell |
| `@endturn` | `@end`, `@pass`, `@skip` | End your turn |
| `@move <location>` | `@mv`, `@goto` | Move party to connected room |
| `@open <door/chest/corpse>` | `@loot`, `@search` | Open containers, doors |
| `@identify <target>` | `@id`, `@examine` | INT check to reveal true identity |
| `@equip <item>` | `@eq`, `@wield` | Equip from inventory |
| `@unequip <item>` | `@uneq`, `@remove` | Unequip item |
| `@dm <question>` | `@gm` | Ask the AI Dungeon Master anything |
| `@help` | `@h` | List all commands |

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI + Socket.IO ASGI app, startup hooks |
| `backend/app/services/state_service.py` | State hydration, persistence, JSON patch broadcasting |
| `backend/app/services/turn_manager.py` | Combat turn loop with advisory locks |
| `backend/app/services/combat_service.py` | Initiative, attack/spell resolution, death handling |
| `backend/app/services/ai_service.py` | LLM invocation (Gemini via LangChain) |
| `backend/app/models.py` | Pydantic models: GameState, Player, Enemy, NPC |
| `backend/game_engine/engine.py` | D&D 5e rules engine (attack/spell resolution) |
| `frontend/src/lib/SocketProvider.tsx` | WebSocket connection, state sync, patch recovery |
| `frontend/src/components/BattlemapPanel.tsx` | SVG hex grid with entity tokens |
| `frontend/src/components/GameInterface.tsx` | Main game UI orchestrator |

## Tests

```bash
cd backend && ./venv/bin/pytest                       # All tests
cd backend && ./venv/bin/pytest -m "not integration"  # Unit tests only (fast, no DB/LLM)
cd frontend && npm run typecheck                      # TypeScript type checking
cd frontend && npm run lint                           # ESLint
```

45 unit tests covering models, combat service, state service, and turn management.

## Tech Stack

**Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, asyncpg, Socket.IO, LangGraph, LangChain, Gemini API, Firebase Admin SDK, Alembic

**Frontend**: React 19, TypeScript 5.9, Vite 7, Zustand, Socket.IO Client, Tailwind CSS 4, Framer Motion, fast-json-patch

**Database**: PostgreSQL 15 (Docker), 24 tables including full SRD 5e compendium (319 spells, monsters, items, classes, races)

**Auth**: Firebase Authentication (emulators for local dev)

## Environment Variables

### Backend (`backend/.env`)
- `DATABASE_URL` — PostgreSQL connection string
- `GEMINI_API_KEY` — Google AI Studio API key
- `FIRESTORE_EMULATOR_HOST` — `127.0.0.1:8080` for local dev
- `FIREBASE_AUTH_EMULATOR_HOST` — `127.0.0.1:9099` for local dev

### Frontend (`frontend/.env`)
- `VITE_API_URL` — Backend URL (`http://localhost:8000`)
- `VITE_FIREBASE_*` — Firebase config (API key, auth domain, project ID, etc.)
