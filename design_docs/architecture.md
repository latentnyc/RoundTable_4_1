---
{
  "id": "file_8irfije5",
  "filetype": "document",
  "filename": "architecture",
  "created_at": "2026-06-19T12:37:47.652Z",
  "updated_at": "2026-06-19T12:37:47.652Z",
  "meta": {
    "location": "/",
    "tags": [],
    "categories": [],
    "description": "",
    "source": "markdown"
  }
}
---
# RoundTable_4_1 Architecture & Design Document

> **Reconciled with the codebase 2026-06-21.** Earlier revisions described an aspirational design
> (a "Conductor" layer, a ChromaDB vector knowledge base, RAG rule injection). None of that exists in
> code. This document now reflects what is actually implemented.

## 1. High-Level Architecture Diagram

```mermaid
graph TD
    User["Human Player"] -->|HTTPS / WebSocket| FE["Frontend (React SPA)"]
    FE -->|Socket.IO + REST| Backend["FastAPI + Socket.IO (Uvicorn)"]

    subgraph "Backend"
        Backend -->|"@commands"| CommandService["CommandService / CombatService / TurnManager"]
        Backend -->|chat & narration| DM_Agent["AI DM (LangGraph graph)"]
        CommandService -->|resolve rules| GameEngine["GameEngine (5e resolution)"]
        DM_Agent -->|recall| Memory["MemoryService (Postgres FTS)"]
        GameEngine -->|persist| DB[("PostgreSQL (asyncpg)")]
        Memory --> DB
    end

    subgraph "External Services"
        DM_Agent -->|API| LLM["LLM provider (Gemini / OpenAI-compatible / local)"]
        FE -->|Auth| Firebase["Firebase Auth"]
    end
```

## 2. Tech Stack

### Frontend
*   **Hosting**: **Google Firebase Hosting**.
*   **Framework**: **Vite + React** (SPA).
*   **Language**: **TypeScript**.
*   **Styling**: **Tailwind CSS 4 + Framer Motion**.
*   **Real-time Client**: **Socket.io-client**.
*   **State Management**: **Zustand**.

### Backend / Orchestration Service
*   **Hosting target**: **Google Cloud Run** (deploy scripts in repo: `deploy_cloud.ps1`). Local dev runs via Docker + Firebase emulators.
*   **Language**: **Python 3.11+**.
*   **API Framework**: **FastAPI**.
*   **Real-time Server**: **Python-SocketIO** (ASGI).
*   **Agent Framework**: **LangGraph + LangChain**.
*   **LLM Interface**: provider dispatch — **Gemini** (default), **OpenAI-compatible / OpenRouter**, and **local** (Ollama / LM Studio) via `get_llm_instance`.

### Database & Persistence
*   **Primary DB**: **PostgreSQL** (asyncpg). Schema is applied by `db/init_db.py` from `db/schema.py`.
*   **Memory retrieval**: **Postgres full-text search** (`to_tsvector` / `ts_rank` + GIN) over `memory_episodes`. *No vector DB is wired today;* pgvector is the intended path if/when embeddings are added.
*   **Auth**: **Firebase Authentication** (Google Sign-In / Email).

### Repository
*   **Visibility**: **Private**.
*   **Platform**: **GitHub**.

## 3. Data Schema (GameState Models)

Implementation based on `backend/app/models.py`.

```json
{
  "session_id": "uuid-v4",
  "version": 42,
  "turn_index": 42,
  "active_entity_id": "goblin_archer_1",
  "phase": "combat",
  "dm_settings": {
    "strictness_level": "normal",
    "dice_fudging": true,
    "narrative_focus": "high"
  },
  "location": {
    "name": "The Weeping Caverns",
    "description": "Damp, echoing caverns with luminescent fungi.",
    "walkable_cells": [{ "x": 0, "y": 0 }],
    "party_locations": [{ "position": { "x": 0, "y": 0 } }]
  },
  "party": [
    {
      "id": "player_1",
      "name": "Valerius",
      "role": "Paladin",
      "is_ai": false,
      "hp_current": 25,
      "hp_max": 30,
      "inventory": ["item_longsword", "item_potion_healing"],
      "conditions": [{ "name": "Blessed", "duration": 10 }],
      "position": { "x": 0, "y": 0 }
    }
  ]
}
```

Notes: the grid is 8-way **square** (`{x, y}`, Chebyshev distance) — the old hex `{q, r, s}` was migrated.
Chat is **not** part of `GameState`; messages are persisted separately in the `chat_messages` table.
`combat_log` (a list of `LogEntry`) lives on `GameState` for the mechanical turn record.

## 4. Data Persistence Strategy

All persistence is in **PostgreSQL**; there is no vector store or mounted volume.

*   **Game State**: a JSON skeleton stored in `game_states`, with entities (`characters`, `monsters`, `npcs`) hydrated from their own tables on load and re-attached as IDs on save (see `StateService`).
*   **Memory**: episodic rows in `memory_episodes`, retrieved via Postgres full-text search.

## 5. Agent Prompt Strategy

### A. The Separation of Concerns
1.  **System Prompt (The Soul)**: Core DM personality + behavioral rules (`agents/dm_agent.py`).
2.  **Context Prompt (The Memory & Rules)**:
    *   **Immediate Situation**: Room/party context + recent chat history (`context_builder.py`).
    *   **Rules**: a small static `RULES_BLOCK` injected on every turn (`services/dm_rules.py`) — *not* semantically retrieved.
    *   **Memory**: relevant past episodes pulled via Postgres FTS (`services/memory_service.py`).
3.  **Task Prompt (The Directive)**: Specific goal for generation (chat vs `combat_narration` / `turn_start_narration` modes).

## 6. Roadmap
*   **Character Creation Wizard**: Completed.
*   **Real-time Chat**: Implemented via Socket.IO (custom event bus; see `holistic-review` for the message-model debts).
*   **Cloud Deployment**: Deploy scripts provided (`deploy_cloud.ps1`); not assumed continuously live.
*   For the full forward plan, see `design_docs/roadmap.md` and the Phase 0–5 sequencing in the holistic review.
