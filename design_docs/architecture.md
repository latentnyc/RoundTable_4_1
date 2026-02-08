# RoundTable_4_1 Architecture & Design Document

## 1. High-Level Architecture Diagram

```mermaid
graph TD
    User[Human Player] -->|WebSocket| FE[Frontend (Next.js)]
    FE -->|WebSocket Events| WS[Orchestration Service (FastAPI + Socket.io)]
    
    subgraph "Backend / Orchestration"
        WS -->|Route Action| Conductor[Conductor Logic]
        Conductor -->|Check Rules| DM_Agent[AI Dungeon Master]
        Conductor -->|Party Banter| Party_Agents[AI Party Members (x3)]
        
        DM_Agent -->|Tool Calls (Update State)| GameEngine[Modular Game Engine]
        DM_Agent -->|Query World| VectorDB[Vector Knowledge Base]
        
        Party_Agents -->|React to event| Conductor
    end
    
    subgraph "Data Persistence"
        GameEngine -->|Persist State| DB[(Supabase / Postgres)]
        VectorDB -->|Lore/Rules| VectorStore[(Vector Store)]
    end
    
    subgraph "External LLM"
        DM_Agent -->|Prompt + Context| LLM[LLM Provider]
        Party_Agents -->|Prompt + Persona| LLM
    end
```

## 2. Tech Stack Recommendation

### Frontend
*   **Framework**: **Next.js 14 (App Router)** - For robust routing, server-side rendering where needed, and React ecosystem.
*   **Styling**: **Tailwind CSS + Framer Motion** - For "premium" feel and micro-animations.
*   **Real-time Client**: **Socket.io-client** - Robust WebSocket handling.
*   **State Management**: **Zustand** - Simple, fast state management for the complex game state.
*   **Visuals**: **Typing Indicators** - Sidebar avatars will glow/animate when an entity is "thinking" or typing.

### Backend / Orchestration Service
*   **Language**: **Python 3.11+**
*   **API Framework**: **FastAPI**
*   **Real-time Server**: **Python-SocketIO**
*   **Agent Framework**: **LangGraph**
*   **LLM Interface**: **LiteLLM**
    *   **Default**: **Gemini 1.5/2.0 Flash** (Fast by default).
    *   **Option**: Integrated switch for **Local LLM** (Ollama/LM Studio) for privacy/offline.

### Database & Auth
*   **Primary DB**: **Supabase (PostgreSQL)**.
*   **Auth**: **Google OAuth** (via Supabase Auth) + Email/Password fallback.
*   **Vector DB**: **Supabase (pgvector)**.

## 3. Data Schema Draft (GameState)

```json
{
  "session_id": "uuid-v4",
  "turn_index": 42,
  "active_entity_id": "goblin_archer_1",
  "phase": "combat", 
  "ruleset": "5e_SRD", // Modular system selection
  "dm_settings": {
    "strictness_level": "relaxed",
    "dice_fudging": true,
    "narrative_focus": "high" 
  },
  "location": {
    "name": "The Weeping Caverns",
    "description": "Damp, echoing capabilities with luminescent fungi."
  },
  "party": [
    {
      "id": "player_1",
      "name": "Valerius",
      "role": "Paladin",
      "is_ai": false,
      "hp": { "current": 25, "max": 30 },
      "inventory": ["Longsword", "Potion of Healing"],
      "status_effects": ["blessed"],
      "position": { "q": 0, "r": 0, "s": 0 }
    },
    {
      "id": "ai_party_1",
      "name": "Thorne",
      "role": "Rogue",
      "is_ai": true,
      "hp": { "current": 18, "max": 20 },
      "inventory": ["Dagger", "Thieves Tools"],
      "position": { "q": 1, "r": -1, "s": 0 }
    }
  ],
  "enemies": [
    {
      "id": "goblin_archer_1",
      "name": "Goblin Sniper",
      "is_ai": true,
      "hp": { "current": 5, "max": 7 },
      "position": { "q": 10, "r": -10, "s": 0 }
    }
  ],
  "combat_log": [
    {
      "tick": 41,
      "actor_id": "player_1",
      "action": "Attack",
      "target_id": "goblin_archer_1",
      "result": "Hit! 6 Damage.",
      "timestamp": "2023-10-27T10:00:00Z"
    }
  ]
}
```

## 4. Agent Prompt Strategy

### A. The Separation of Concerns
1.  **System Prompt (The Soul)**: Immutable core personality.
2.  **Context Prompt (The Memory & Rules)**: 
    *   **Immediate Situation**: Room desc, last 5 messages.
    *   **Rule Injection**: Relevant rules for the current context (e.g., if casting a spell, inject spellcasting rules). *Crucial for preventing hallucinations.*
3.  **Task Prompt (The Directive)**: Specific goal for generation.

### B. The Conductor Pattern (Orchestration)
*   **Input**: Human sends message "I open the chest."
*   **Conductor Logic**: 
    1.  Block all Party AI.
    2.  Route to DM Agent.
    3.  DM Agent tool-calls `check_trap(chest_id)`.
    4.  DM Agent output: "The chest clicks. Roll a DEX save."
    5.  Conductor unblocks Party AI to react.

## 5. New Features
*   **Character Creation**: A dedicated wizard flow to build the player character (Stats, Class, Backstory) before entering the game session.
*   **Google OAuth**: Sign-in via Supabase for persistent user accounts.
