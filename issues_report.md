# Codebase Architecture & Implementation Issues Report

Based on a comprehensive review of the `RoundTable_4_1` codebase, here is a ranked outline of the most critical architectural, design, and implementation issues.

## 1. Monolithic Game State & Synchronization (High Severity)
**Description:** 
The backend utilizes a monolithic `GameState` Pydantic model (`app/models.py`) containing the entire campaign's state (all characters, enemies, NPCs, locations, vessels, combat logs, etc.). 
On the frontend (`SocketProvider.tsx`), this large object is synced via `fast-json-patch` over WebSockets. Because the payload is heavy, a hybrid approach was attempted where "heavy" fields (like `sheet_data` and `inventory`) are stripped from the WebSocket payload and fetched via a separate REST endpoint, then manually merged back into the frontend store.

**Impact:**
- **Race Conditions:** Merging REST data `fetch` responses back into a continuously patching WebSocket `gameState` can lead to overwritten data, UI jitter, or silent sync failures.
- **Scalability:** As the world grows (more NPCs, locations, long combat logs), the JSON patches become expensive to compute and apply.
- **Client Side Lag:** Deep cloning and patching large states in Zustand triggers excessive React re-renders.

**Recommendation:** 
Migrate to an Entity-Component System (ECS) or Normalized State shape where entities are independent rows/objects, and the socket only broadcasts targeted events (e.g., `ENTITY_MOVED`, `HP_CHANGED`) rather than full state patches.

---

## 2. Tight Coupling in `CombatService` (High Severity)
**Description:**
`backend/app/services/combat_service.py` is an oversized class (568 lines) that handles everything from initiative rolling, range validation, opportunity attacks, to entity death and loot generation. While a `GameEngine` and `Resolvers` exist (`backend/game_engine/engine.py`), `CombatService` breaks encapsulation by manually mutating entity HP (`target_char.hp_current = new_hp`), generating corpses (`Vessel`), and manually controlling the `game_state.phase`.

**Impact:**
- **Game Design Brittleness:** Modifying rules for damage, resistance, or death requires touching `CombatService` rather than the decoupled `GameEngine`.
- **Testing Difficulty:** Mocking out the database and socket layers to test combat rules is difficult when the rules are buried inside the async service layer.

**Recommendation:**
Refactor `CombatService` into a pure coordinator. It should pass intents to `GameEngine.resolve_action()`, receive a structured result containing state diffs (like `hp_delta: -5, status_applied: 'dead'`), and then save those diffs.

---

## 3. Frontend In-Browser Pathfinding (Medium Severity)
**Description:**
In `BattlemapPanel.tsx`, the frontend calculates reachable hexes using a Breadth-First Search (BFS) algorithm inside a `useMemo` hook that runs whenever the `gameState` or `selectedTokenId` changes.

**Impact:**
- **Performance:** BFS on a large hex grid block the main thread. If a user clicks around quickly or the map grows, the UI will freeze.
- **Desync:** Pathfinding rules logic (e.g., whether you can walk through an ally or jump over an obstacle) must be duplicated on the frontend and backend.

**Recommendation:**
Offload pathfinding and movement validation to the backend. The frontend should only send "I want to move here", and the backend should return the validated path or a rejection, OR the backend sends a list of valid hexes for the currently active character at the start of their turn.

---

## 4. AI Prompt Generation and Context Bloat (Medium Severity)
**Description:**
`backend/app/services/ai_service.py` handles LangGraph interaction. To prevent token limits, there's logic that summarizes messages once over 30 messages are reached. However, if the summarization call fails or is delayed, the context window can theoretically unbounded. Furthermore, prompts are stitched using string interpolation and manual flag passing.

**Impact:**
- **Reliability:** Unbounded contexts cause 400 errors from the LLM provider, crashing the AI permanently for a campaign until manually cleared.
- **Maintainability:** Hardcoded string behaviors (`if flags and "ACTED_NOT_MOVED" in flags: ...`) make updating DM behaviors fragile.

**Recommendation:**
Move to structured extraction instead of text injection. Ensure summarization is done asynchronously via background worker (e.g., Celery or RQ) to prevent long request timeouts during chat emission.

---

## 5. Secret Key Fallback Anti-Pattern (Low Severity)
**Description:**
In `AIService.get_campaign_config`, the app falls back to an environment `GEMINI_API_KEY` if the campaign's custom key isn't set. 

**Impact:**
- If users don't provide their own keys, the host's default key bears the cost and rate limit constraint of *all* campaigns on the server, easily hitting quota limits.

**Recommendation:**
Enforce that users must input their own keys per campaign, or implement strict token rate limiting on the fallback key.
