# RoundTable 4.1 - Friday the 13th Edition 👻

A TTRPG application with AI-powered Game Master and 5e rules integration.

## 👻 The "Spooky Commit" Changelog

This release brings a massive architectural overhaul and spirited improvements:

### 🕸️ Web of Interface
*   **Entity List Panel**: A new side panel (`EntityListPanel.tsx`) to track combatants, HP, and status effects in real-time.
*   **Chat Improvements**: Enhanced `ChatInterface` and `LogViewer` with better color-coding for System, DM, and Character messages.

### 👻 Spooky Architecture
*   **Service Refactor**: The backend has been exorcised of monolithic logic!
    *   `ChatService`: Handles all chat logic.
    *   `CommandService`: Processes slash commands (`@attack`, `@check`).
    *   `NarratorService`: Manages AI narration generation.
    *   `TurnManager`: Controls the flow of combat turns.
*   **SocketIO Reliability**: Enhanced `SocketIOCallbackHandler` to prevent crashes during tool execution.

### 💀 Skeleton Crew (Testing)
*   **New Verification Suite**: added `backend/tests/` containing:
    *   `verify_db_schema_actual.py`: Ensures database tables haunt the right columns.
    *   `verify_logs_api.py`: Checks that logs are properly recorded from the beyond.
    *   `verify_postgres_schema.py`: Validates Cloud SQL compatibility.

### ⚰️ Buried Bugs
*   **Root Clutter Cleared**: Moved/Deleted debug scripts from the root directory.
*   **Combat Race Conditions**: Fixed issues where AI would attack with outdated game state.
*   **Message Sync**: Fixed frontend deduplication hiding rapid-fire messages.

---

## 🔮 Setup & Running

### 🍎 Mac / 🐧 Linux (Recommended)
We have a new unified script that handles Java, Python venv, and Node dependencies automatically.

```bash
./run_local.sh
```

### 🪟 Windows
Legacy support is available via PowerShell:
```powershell
.\run_local.ps1
```

### Manual Setup (Advanced)

**Backend**
```bash
cd backend
python -m venv venv
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

## 📜 Features
*   **5e Compendium**: Integrated 2014 SRD data for spells, monsters, classes, races, and items.
*   **AI Game Master**: Powered by LangGraph and Gemini.
*   **Real-time Combat**: WebSocket-driven combat updates.

HAPPY FRIDAY THE 13TH! 🔪
