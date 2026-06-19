---
{
  "id": "file_7yr2mp1x",
  "filetype": "document",
  "filename": "AGENTS",
  "created_at": "2026-06-19T14:03:24.490Z",
  "updated_at": "2026-06-19T14:03:24.490Z",
  "meta": {
    "location": "/",
    "tags": [],
    "categories": [],
    "description": "",
    "source": "markdown"
  }
}
---
# RoundTable 4.1 — Agent Guide

This document is written for AI coding agents. It summarizes the project architecture, conventions, and workflows as they actually exist in the codebase. When in doubt, prefer the files referenced here over general assumptions.

## 1. Project Overview

RoundTable 4.1 is an AI-powered tabletop RPG (D&D 5e) with real-time multiplayer combat and an AI Dungeon Master. Players explore hex-based maps, fight monsters, loot corpses, and interact with NPCs, all narrated by an AI DM powered by Google Gemini. AI party members fight alongside the player with pathfinding, spellcasting, and tactical combat.

- **Frontend**: React 19 + TypeScript + Vite SPA, served on port 3000 in local development.
- **Backend**: Python 3.11 + FastAPI + python-socketio ASGI app, served on port 8000.
- **Database**: PostgreSQL 15 (Docker locally, Cloud SQL in production), port 5432.
- **Auth**: Firebase Authentication (local emulators in development).
- **Primary real-time sync**: Socket.IO WebSocket with JSON Patch (RFC 6902) state deltas.

## 2. Technology Stack

### Backend (`backend/`)

| Concern | Technology |
|--------|------------|
| Language | Python 3.11 |
| Web framework | FastAPI |
| ASGI server | Uvicorn (dev), Gunicorn + Uvicorn worker (production) |
| Real-time | python-socketio (ASGI) |
| AI / LLM | LangGraph, LangChain, `langchain-google-genai`, `google-genai` |
| Auth | Firebase Admin SDK |
| Database | PostgreSQL + SQLAlchemy 2.0 + asyncpg |
| Migrations | Alembic (present) plus ad-hoc `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `db/init_db.py` |
| Config | python-dotenv |
| Testing | pytest + pytest-asyncio |

Dependencies are declared in `backend/requirements.txt`.

### Frontend (`frontend/`)

| Concern | Technology |
|--------|------------|
| Framework | React 19 |
| Language | TypeScript 5.9 |
| Build tool | Vite 7 |
| Styling | Tailwind CSS 4 (`@import "tailwindcss"` in `index.css`) |
| State | Zustand |
| HTTP client | Axios |
| Real-time | socket.io-client |
| Routing | react-router-dom v7 |
| Animation | Framer Motion |
| Icons | lucide-react, react-icons |

Dependencies are declared in `frontend/package.json`.

### Infrastructure

| Concern | Technology |
|--------|------------|
| Local orchestration | Docker Compose (`docker-compose.yml`) |
| Local auth / Firestore | Firebase Emulators (auth 9099, firestore 8080, UI 4000) |
| Production hosting | Firebase Hosting (frontend) + Google Cloud Run (backend) |
| Production database | Google Cloud SQL for PostgreSQL |
| CI/CD | GitHub Actions (`.github/workflows/ci.yml`) |

## 3. Project Structure

```
├── backend/                 # FastAPI / Socket.IO game server
│   ├── main.py              # ASGI app factory; wraps FastAPI with Socket.IO
│   ├── app/
│   │   ├── routers/         # FastAPI HTTP routers (auth, campaigns, characters, game, chat, etc.)
│   │   ├── services/        # Business logic (state, combat, spells, turns, AI, commands, etc.)
│   │   ├── agents/          # LangGraph DM agent, character agent, summarizer
│   │   ├── commands/        # @command registry and implementations
│   │   ├── socket/          # Socket.IO event handlers
│   │   ├── models.py        # Pydantic models: GameState, Player, Enemy, NPC, Condition, etc.
│   │   ├── dtos.py          # API request/response Pydantic models
│   │   ├── config.py        # Settings, CORS allowed origins
│   │   ├── auth_utils.py    # Firebase JWT verification
│   │   └── dependencies.py  # FastAPI DB dependency
│   ├── db/
│   │   ├── schema.py        # SQLAlchemy Core table definitions
│   │   ├── session.py       # AsyncSessionLocal + engine
│   │   └── init_db.py       # Table creation / ad-hoc migrations
│   ├── game_engine/         # D&D 5e rules engine (dice, character sheet, resolvers)
│   ├── json_data/           # Static SRD 5e datasets
│   ├── tests/               # pytest suite (27 files)
│   ├── scripts/             # Utility / debug / verification scripts
│   ├── requirements.txt     # Runtime dependencies
│   └── pytest.ini           # pytest configuration
│
├── frontend/                # Vite + React SPA
│   ├── src/
│   │   ├── components/      # React components (BattlemapPanel, GameInterface, ChatInterface, etc.)
│   │   ├── pages/           # Route pages (CampaignDash, CampaignMain, Login, etc.)
│   │   ├── store/           # Zustand stores (authStore, campaignStore, characterStore, etc.)
│   │   ├── lib/             # Utilities, API clients, SocketProvider, rules
│   │   ├── App.tsx          # Router + AuthGuard
│   │   └── main.tsx         # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── eslint.config.js
│
├── games/                   # Static campaign JSON templates loaded at startup
├── scripts/                 # Dev lifecycle helpers
│   ├── dev-start.sh         # Start Docker Postgres, Firebase emulators, backend, frontend
│   ├── dev-stop.sh          # Stop services
│   ├── dev-status.sh        # Show running services
│   └── dev-logs.sh          # Tail interleaved or per-service logs
├── tests/                   # Root-level Python verification scripts (not pytest)
├── docker-compose.yml       # Postgres + backend + frontend
├── firebase.json            # Firebase hosting + emulator config
├── deploy_cloud.ps1         # Production deploy orchestrator
├── package.json             # Root orchestration wrapper (concurrently)
└── .pre-commit-config.yaml  # Pre-commit hooks
```

## 4. Development Environment Setup

Prerequisites: Docker Desktop, Java 21 (`brew install openjdk@21`), Python 3.11, Node.js 20+.

The canonical way to start local development:

```bash
./scripts/dev-start.sh              # Start everything (Docker, Firebase, backend, frontend)
./scripts/dev-start.sh --skip-deps  # Skip pip/npm install
./scripts/dev-start.sh --reset-db   # Wipe and re-seed database
```

This starts five services:

1. PostgreSQL on `localhost:5432`
2. Firebase Auth Emulator on `localhost:9099`
3. Firebase Firestore Emulator on `localhost:8080`
4. Backend (Uvicorn) on `localhost:8000`
5. Frontend (Vite) on `localhost:3000`

On first startup, the backend auto-creates the schema, loads the SRD 5e dataset (319 spells, 334 monsters, 599 items), syncs campaign templates from `games/`, and seeds a dev test campaign.

Useful dev commands:

```bash
./scripts/dev-status.sh              # Show running services and ports
./scripts/dev-logs.sh                # Tail all logs interleaved
./scripts/dev-logs.sh backend        # Tail backend only
./scripts/dev-logs.sh frontend       # Tail frontend only
./scripts/dev-logs.sh firebase       # Tail Firebase emulator only
./scripts/dev-stop.sh                # Stop frontend/backend/Firebase
./scripts/dev-stop.sh --with-db      # Also stop PostgreSQL
```

Alternative Windows scripts exist: `dev.ps1`, `run_local.ps1`, `run_local.sh`, `kill_all.sh`.

A test campaign is auto-seeded at `http://localhost:3000/campaign_dash/dev-test-campaign-001`. After login, click **Quick Join** to create a full party and enter combat.

## 5. Build, Run & Test Commands

### Backend

```bash
cd backend
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn main:app --reload --port 8000       # Development

# Tests
./venv/bin/pytest                                      # All tests
./venv/bin/pytest -m "not integration"                 # Unit tests only (fast, no live DB/LLM)

# Database management
./venv/bin/python scripts/manage_db.py reset --force   # Drop and recreate all tables
./venv/bin/python scripts/manage_db.py create          # Create tables if missing
```

Production entry point (from `backend/Dockerfile`):

```bash
gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --threads 8 --timeout 0 main:app
```

### Frontend

```bash
cd frontend
npm install
npm run dev                    # Vite dev server on port 3000
npm run build                  # TypeScript compile + production build
npm run typecheck              # tsc --noEmit
npm run lint                   # ESLint
```

### Docker Compose

```bash
docker compose up -d db        # Start PostgreSQL only
docker compose up --build      # Build and start all three services
```

### Root `package.json`

The root `package.json` is a thin orchestration wrapper:

```bash
npm run setup                  # Install backend + frontend dependencies
npm run start                  # Run backend and frontend concurrently
npm run backend                # Run backend via root venv
npm run frontend               # Run frontend dev server
```

## 6. Code Style & Conventions

### Python (Backend)

- Target Python 3.11.
- Use async/await throughout; the DB layer is async SQLAlchemy + asyncpg.
- Prefer Pydantic v2 models for request/response validation (`app/models.py`, `app/dtos.py`).
- FastAPI routers require Firebase Bearer tokens by default via `app/auth_utils.verify_token`.
- Business logic lives in `app/services/`, not in routers.
- Socket.IO handlers live in `app/socket/` and are organized by domain.
- Commands entered by players (`@attack`, `@cast`, etc.) are implemented in `app/commands/` and registered through `CommandService.register_commands()`.
- Use `app/logging_config.logger` for production logging; do not use bare `print()` in `backend/app/` (enforced by pre-commit).
- Alembic is present but the project also relies on `db/init_db.py` for ad-hoc column additions.

### TypeScript / React (Frontend)

- Target React 19 and TypeScript 5.9 strict mode.
- Functional components with hooks.
- State management: Zustand. Prefer selecting individual actions to avoid selector churn (see `SocketProvider.tsx`).
- API calls go through `lib/api.ts`; the Axios instance adds the Firebase token via `setTokenGetter` in `main.tsx`.
- Real-time state lives in `SocketProvider.tsx` and is sunk into `useSocketStore`.
- Tailwind CSS v4 is configured via `@import "tailwindcss"` in `frontend/src/index.css` and the Vite plugin.
- Do not add new `console.log` in `frontend/src/` (enforced by pre-commit, with specific exclusions).
- ESLint config is flat-config (`eslint.config.js`) using `@eslint/js`, `typescript-eslint`, `react-hooks`, and `react-refresh`.

### General

- Environment variables and secrets are gitignored (`.env`, `.env*`, `backend/.env`, `frontend/.env`). Never commit them.
- Pre-commit hooks (`.pre-commit-config.yaml`) enforce trailing whitespace, EOF newline, YAML checks, and forbid `console.log` / `print()` in app code.

## 7. Testing Strategy

### Backend Tests

- Location: `backend/tests/`
- Framework: pytest with `pytest-asyncio` (`asyncio_mode = auto` in `backend/pytest.ini`).
- Run fast unit tests with: `pytest -m "not integration"`
- Integration tests are marked with `@pytest.mark.integration` and require a live database or external services.
- Fixtures live in `backend/tests/conftest.py`.
- Coverage includes models, combat, spells, conditions, state service, turn manager, socket auth, pathfinding, and multiattack.

### Frontend Tests

- There are no frontend tests in the repository yet. CI runs TypeScript type checking, ESLint, and a production build.

### Root Verification Scripts

- `tests/verify_attack_npc.py`
- `tests/verify_db_schema.py`
- `tests/verify_npc_persistence.py`
- `tests/verify_persistence_all.py`

These are standalone diagnostic scripts, not part of the pytest suite.

## 8. Security Considerations

- **Authentication**: Firebase JWT Bearer tokens required for nearly all backend routes. `backend/app/auth_utils.py` verifies tokens.
- **Authorization**: The first user to log in is auto-promoted to admin. `app/permissions.py` provides an admin check dependency.
- **CORS**: Allowed origins default to Firebase hosting URLs plus `localhost:3000` / `localhost:5173`. Override via `ALLOWED_ORIGINS` env var.
- **Secrets**: API keys (Gemini, Firebase) are stored in `.env` files and are gitignored. The backend stores the campaign Gemini API key in the database.
- **Firestore rules** (`firestore.rules`) default to `allow read, write: if false;` — everything is locked down.
- **No raw SQL** in routers unless necessary; use parameterized SQLAlchemy queries.
- **Dev endpoints**: `backend/app/routers/dev.py` exposes convenience endpoints (e.g., quick-join) that should not be enabled in production as-is.
- **Container**: Backend Dockerfile copies `games/` and backend code, exposes `PORT`, and runs as a non-interactive Gunicorn/Uvicorn worker.

## 9. Deployment

Production deployment is orchestrated by `deploy_cloud.ps1`:

1. Optionally reset the Cloud SQL database.
2. Build the frontend (`npm run build` in `frontend/`).
3. Build the backend container with Google Cloud Build and tag `gcr.io/roundtable41-1dc2c/roundtable-backend:latest`.
4. Deploy the backend to Google Cloud Run with the Cloud SQL instance attached.
5. Deploy the frontend to Firebase Hosting.

Run with defaults:

```powershell
./deploy_cloud.ps1 -ProjectID roundtable41-1dc2c
```

Production env vars are set on the Cloud Run service:

- `DATABASE_URL` — Unix-socket connection string through `/cloudsql/...`
- `GEMINI_API_KEY` — loaded from `backend/.env`
- `ALLOWED_ORIGINS` — Firebase hosting URLs
- `FIREBASE_PROJECT_ID` — `roundtable41-1dc2c`

## 10. Key Architectural Patterns

- **Command pattern**: Player text commands (`@attack`, `@cast`, `@move`, etc.) are dispatched through `CommandService`.
- **State Service**: `backend/app/services/state_service.py` hydrates `GameState` from `game_states.state_data` plus entity tables, persists changes, and emits JSON Patch deltas over Socket.IO.
- **Turn Manager**: `backend/app/services/turn_manager.py` advances initiative with PostgreSQL advisory locks; auto-runs AI turns until a human turn is reached.
- **Game Engine**: `backend/game_engine/engine.py` resolves D&D 5e attacks, saves, spells, and conditions.
- **AI Turn Service**: `backend/app/services/ai_turn_service.py` handles pathfinding (BFS on hex grid), target selection, spellcasting, and multiattack for AI-controlled entities.
- **Client sync**: Full state is sent on `game_state_update`; incremental patches are sent on `game_state_patch`. The client applies patches with `fast-json-patch` and falls back to reconnection / full-state request after consecutive failures.
- **Campaign templates**: JSON files in `games/` are parsed at startup by `app/services/campaign_loader.py` and instantiated into campaign-scoped DB records.

## 11. Known Fragile Areas

These are documented in `CLAUDE.md` and `issues_report.md`. Agents should be careful when touching them:

1. **`StateService._last_broadcasted_state`** — class-level dict never cleared on disconnect; can produce invalid patches after all players leave and rejoin.
2. **`SocketProvider.tsx` patch failure handling** — failures are caught and logged; after 3 consecutive failures the socket reconnects, but silent divergence is possible before that.
3. **`TurnManager` lock cycling** — advisory locks prevent races, but errors mid-sequence can leave state inconsistent.
4. **Entity hydration** — `_hydrate_party()` has many fallback defaults and type coercions; changes to `sheet_data` structure can silently produce wrong values.
5. **`ErrorBoundary`** — exists but was previously not mounted in `App.tsx` (now mounted as of current `App.tsx`). Still verify on any routing changes.
6. **Tight coupling in `CombatService`** — noted in `issues_report.md` as a source of complexity.
7. **AI context bloat** — DM agent context can grow large; be mindful when adding new per-message data.

## 12. Environment Variables

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

Both `.env` files are gitignored.

## 13. CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`:

- **Frontend**: `npm ci` → `tsc --noEmit` → `eslint . --max-warnings 100` → `vite build`.
- **Backend**: Python 3.11 setup → `pip install -r requirements.txt` → install pytest → `pytest -m "not integration" --tb=short -q` with a Postgres 15 service container.

## 14. Useful Commands Cheat Sheet

```bash
# Full local stack
./scripts/dev-start.sh
./scripts/dev-stop.sh

# Backend only
cd backend && ./venv/bin/uvicorn main:app --reload --port 8000

# Frontend only
cd frontend && npm run dev

# Tests
cd backend && ./venv/bin/pytest -m "not integration"
cd frontend && npm run typecheck && npm run lint

# DB reset
cd backend && ./venv/bin/python scripts/manage_db.py reset --force

# Docker Compose
docker compose up -d db
docker compose up --build

# Production deploy (PowerShell)
./deploy_cloud.ps1 -ProjectID roundtable41-1dc2c
```

## 15. Where to Start Reading

- Backend entry point: `backend/main.py`
- Core models: `backend/app/models.py`
- State sync: `backend/app/services/state_service.py` and `frontend/src/lib/SocketProvider.tsx`
- Combat loop: `backend/app/services/combat_service.py` and `backend/app/services/turn_manager.py`
- AI turns: `backend/app/services/ai_turn_service.py`
- Rules engine: `backend/game_engine/engine.py`
- Frontend entry: `frontend/src/main.tsx` → `frontend/src/App.tsx`
- Main game UI: `frontend/src/components/GameInterface.tsx`
- Hex battlemap: `frontend/src/components/BattlemapPanel.tsx`
