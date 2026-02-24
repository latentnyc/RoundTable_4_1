# RoundTable_4_1 - Survived the Blizzard Code-Marathon 🧊🔥

A TTRPG application with an AI-powered Game Master and 5e rules integration.

## 🏔️ The "Survived the Blizzard Code-Marathon" Changelog

We made it through! After a grueling blizzard code-marathon, we've melted away critical bugs, significantly tightened the architecture, and introduced a ton of improvements. Here is what survived the storm:

### 🗺️ Battlemap & Movement Polish
*   **Spawn Hex Logic**: Refined map rendering to correctly display southern spawn hexes, expanding the map's bounding box automatically to prevent clipping, and flawlessly centering tokens within their designated hex.
*   **Movement Fixes**: Fixed a critical movement bug where closed doors in unrelated rooms would incorrectly block all traversal in `resolution_move`.

### 🛡️ Core Rules & Stats Integrity
*   **Armor Class (AC) Hydration**: Characters no longer default to 10 AC! The engine now dynamically calculates and displays the correct AC in the sidebar based on character stats and equipment.
*   **Class Loadouts**: Implemented D&D 5E base class loadouts. Swapping classes during creation now immediately clears and accurately replaces starting equipment and stats.
*   **Goblin Enhancements**: Identified enemy stats (like those pesky goblins) now correctly appear on mouseover in the entity list panel. Oh, and we added a new Goblin Room to the north!

### 🎒 Immersive Looting & Chests
*   **Rich Loot Metadata**: Drops are no longer just raw item IDs. The backend now fetches rich metadata (names, descriptions, types) from the database to display beautifully in the new `LootModal`.
*   **Interactable Chests**: Chests now function as `Vessel` entities—clicking them opens a dedicated dialogue window instead of auto-looting immediately.

### ⚙️ Deep Architectural Refactoring
*   **Exception Handling**: Conducted a massive refactoring to replace lazy, broad `except Exception` blocks with granular, specific exception types. Errors are no longer swallowed silently!
*   **AI Turn Manager**: Debugged the `TurnManager` to correctly identify AI party members via their `control_mode`, preventing the game from hanging indefinitely during AI turns.
*   **Performance Audits**: Audited the entire codebase for inefficiencies, resolving data loss risks, streamlining UI performance, and completely cleaning up dead code and throwaway test scripts.

### 🎨 UI & Quality of Life
*   **DM Status Indicator**: Repositioned the DM busy indicator to sit cleanly inline with the "Party Chat" header.
*   **Image Generation Control**: Disabled the unpredictable AI redraw triggers upon enemy death to prevent hallucinations of living enemies appearing.

---

## ❄️ Setup & Running

### 🍎 Mac / 🐧 Linux (Recommended)
Our unified script bundles Java, Python venv, and Node dependencies together before the freeze sets in.

```bash
./run_local.sh
```

### 🪟 Windows
Stay warm and use PowerShell:
```powershell
.\run_local.ps1
```

### Manual Setup (Advanced)

**Backend (PostgreSQL)**
Ensure Docker is running for the database:
```bash
docker-compose up -d
cd backend
python -m venv venv
# Use venv\Scripts\activate on Windows
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Firebase Emulators**
```bash
firebase emulators:start --only auth,firestore,hosting,ui
```

---

## 📜 Core Features
*   **5e Compendium**: Integrated 2014 SRD data for spells, monsters, classes, races, and items.
*   **AI Game Master**: Powered by LangGraph and Gemini for immersive storytelling.
*   **Real-time Combat**: WebSocket-driven combat and state updates.
*   **Character Creation**: Full interactive creation suite.

STAY WARM AND HAPPY ADVENTURING! ☕
