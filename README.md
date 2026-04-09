# RoundTable 4.1

AI-powered tabletop RPG (D&D 5e) with real-time multiplayer combat and an AI Dungeon Master.

Players explore hex-based maps, fight monsters, loot corpses, and interact with NPCs — all narrated by an AI DM powered by Google's Gemini. AI party members fight alongside you with pathfinding, spellcasting, and tactical combat.

## Quick Start

**Prerequisites**: Docker Desktop, Java 21 (`brew install openjdk@21`), Python 3.11, Node.js 20+

### Starting

```bash
./scripts/dev-start.sh              # Start everything: Docker, Firebase emulators, backend, frontend
./scripts/dev-start.sh --skip-deps  # Skip pip/npm install (faster restart)
./scripts/dev-start.sh --reset-db   # Wipe database and re-seed from scratch
```

This starts 5 services:
- **PostgreSQL** (Docker, port 5432) — persistent game database
- **Firebase Auth Emulator** (port 9099) — local authentication
- **Firebase Firestore Emulator** (port 8080) — local Firestore
- **Backend** (FastAPI/Uvicorn, port 8000) — game server + API
- **Frontend** (Vite, port 3000) — React UI

On first startup, the backend automatically: creates DB schema, loads the SRD 5e dataset (319 spells, 334 monsters, 599 items), syncs campaign templates, and seeds a test campaign.

### Stopping

```bash
./scripts/dev-stop.sh           # Stop frontend, backend, and Firebase emulators
./scripts/dev-stop.sh --with-db # Also stop the PostgreSQL Docker container
```

### Monitoring

```bash
./scripts/dev-status.sh         # Show which services are running with ports and PIDs
./scripts/dev-logs.sh           # Tail all service logs interleaved
./scripts/dev-logs.sh backend   # Tail only backend logs
./scripts/dev-logs.sh frontend  # Tail only frontend logs
./scripts/dev-logs.sh firebase  # Tail only Firebase emulator logs
```

### Quick Test Game

After startup, a "Dev Test — Goblin Combat" campaign is auto-seeded with the Gemini API key pre-configured from your `backend/.env` (never committed to git).

1. Log in (any Google account via Firebase emulator)
2. Navigate to `http://localhost:3000/campaign_dash/dev-test-campaign-001`
3. Click **"Quick Join"** (yellow banner) — creates a full party, skips the character wizard:
   - **Elara Nightwhisper** — High Elf Wizard (you, human-controlled) with Fire Bolt, Ray of Frost, Magic Missile
   - **Theron Swiftwind** — Wood Elf Ranger (AI) with Longbow + Shortsword
   - **Bruna Stonefist** — Human Fighter (AI) with Greataxe + Shield + Chain Mail
4. Click **"Enter Campaign"** — you're in a room with a hostile Lizardfolk warrior (multiattack: Bite + Heavy Club) and two doors

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
4. Action economy enforced: one action per turn, one movement per turn
5. AI party members auto-execute: pathfind → move → cast spells or attack
6. AI enemies do the same — monsters with multiattack make multiple attacks per turn
7. Conditions affect combat: Stunned/Paralyzed skip turns, Blinded gives disadvantage, etc.
8. Concentration spells break on damage (CON save DC = max(10, damage/2))
9. Combat ends when all hostiles are dead (victory) or party falls (defeat)

### Spell System

35 spells are fully mechanically resolved. Spells not yet supported are hidden from players.

| Type | Spells |
|------|--------|
| **Attack + damage** | Fire Bolt, Ray of Frost, Shocking Grasp, Chill Touch, Eldritch Blast, Guiding Bolt, Inflict Wounds, Acid Arrow |
| **Save + damage** | Sacred Flame, Poison Spray, Vicious Mockery, Hellish Rebuke, Blight, Harm, Finger of Death, Disintegrate |
| **Auto-hit** | Magic Missile |
| **Healing** | Cure Wounds, Healing Word, Heal |
| **Condition (no conc.)** | Blindness/Deafness, Command, Charm Person, Animal Friendship |
| **Condition (conc.)** | Hold Person, Hold Monster, Entangle, Hideous Laughter, Phantasmal Killer, Banishment, Dominate Beast/Person/Monster, Eyebite, Flesh to Stone |

- Spell slots tracked per 5e rules (full/half/warlock caster tables)
- Cantrips scale with character level (Fire Bolt: 1d10 → 2d10 at L5 → 3d10 at L11)
- Concentration tracked: one spell at a time, CON save on damage, breaks on death
- AI party members cast cantrips at range when out of melee

### Condition System

11 conditions are mechanically enforced with advantage/disadvantage, turn skipping, and duration tracking:

Blinded, Charmed, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Poisoned, Prone, Restrained, Stunned, Unconscious

- Conditions tick at start of each turn, expire when duration reaches 0
- Visible on battlemap (colored dots) and entity list (badges) with hover tooltips
- Saving throw proficiency applied correctly (proficient saves add proficiency bonus)
- Petrified entities have damage resistance (half damage)

## Player Commands

| Command | Aliases | What it does |
|---------|---------|-------------|
| `@attack <target>` | `@atk`, `@a` | Attack with equipped weapon |
| `@cast <spell> [at <target>]` | `@c` | Cast a spell (35 available) |
| `@endturn` | `@end`, `@pass`, `@skip` | End your turn |
| `@move <location>` | `@mv`, `@goto` | Move party to connected room |
| `@open <door/chest/corpse>` | `@loot`, `@search` | Open containers, doors |
| `@identify <target>` | `@id`, `@examine` | INT check to reveal true identity |
| `@equip <item>` | `@eq`, `@wield` | Equip from inventory |
| `@unequip <item>` | `@uneq`, `@remove` | Unequip item |
| `@rest [short\|long]` | `@camp` | Recover HP and spell slots |
| `@check <skill> [dc]` | `@roll`, `@skill` | Ability/skill check (all 18 skills) |
| `@dm <question>` | `@gm` | Ask the AI Dungeon Master anything |
| `@help` | `@h` | List all commands |

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI + Socket.IO ASGI app, startup hooks |
| `backend/app/services/state_service.py` | State hydration, persistence, JSON patch broadcasting |
| `backend/app/services/turn_manager.py` | Combat turn loop with advisory locks |
| `backend/app/services/combat_service.py` | Initiative, attack/spell resolution, death handling |
| `backend/app/services/spell_service.py` | Tier A whitelist, SRD normalization, spell slots, concentration |
| `backend/app/services/condition_service.py` | Condition registry, effects, lifecycle, concentration saves |
| `backend/app/services/ai_turn_service.py` | AI pathfinding, target selection, spellcasting, multiattack |
| `backend/app/models.py` | Pydantic models: GameState, Player, Enemy, NPC, Condition |
| `backend/game_engine/engine.py` | D&D 5e rules engine (attack/spell/save resolution) |
| `frontend/src/lib/SocketProvider.tsx` | WebSocket connection, state sync, patch recovery |
| `frontend/src/components/BattlemapPanel.tsx` | SVG hex grid with entity tokens and condition indicators |
| `frontend/src/components/GameInterface.tsx` | Main game UI orchestrator |

## Tests

```bash
cd backend && ./venv/bin/pytest                       # All tests
cd backend && ./venv/bin/pytest -m "not integration"  # Unit tests only (fast, no DB/LLM)
cd frontend && npm run typecheck                      # TypeScript type checking
cd frontend && npm run lint                           # ESLint
```

118 unit tests covering models, combat, spells (35), conditions (11), concentration, multiattack, state service, and turn management.

## CI/CD

GitHub Actions runs automatically on every push to `main`:

- **Frontend**: `npm ci` → TypeScript type check → ESLint (0 errors, ≤100 warnings) → Vite production build
- **Backend**: PostgreSQL service container → `pip install` → `pytest` (118 unit tests)

## Tech Stack

**Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, asyncpg, Socket.IO, LangGraph, LangChain, Gemini API, Firebase Admin SDK, Alembic

**Frontend**: React 19, TypeScript 5.9, Vite 7, Zustand, Socket.IO Client, Tailwind CSS 4, Framer Motion, fast-json-patch

**Database**: PostgreSQL 15 (Docker), 24 tables including full SRD 5e compendium (319 spells, 334 monsters, 599 items)

**Auth**: Firebase Authentication (emulators for local dev)

## Environment Variables

These files are **gitignored** and never committed. The test campaign reads `GEMINI_API_KEY` from the environment at startup and stores it in the local database only.

### Backend (`backend/.env`)
```
DATABASE_URL=postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres
GEMINI_API_KEY=your_google_ai_studio_key
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
GCLOUD_PROJECT=roundtable41-1dc2c
```

### Frontend (`frontend/.env`)
```
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=your_firebase_api_key
VITE_FIREBASE_AUTH_DOMAIN=roundtable41-1dc2c.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=roundtable41-1dc2c
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
VITE_FIREBASE_MEASUREMENT_ID=your_measurement_id
```
