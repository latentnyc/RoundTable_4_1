# RoundTable_4_1 - Waiting for the Blizzard Release ❄️🌨️

A TTRPG application with an AI-powered Game Master and 5e rules integration.

## 🌨️ The "Waiting for the Blizzard" Changelog

This release brings a blizzard of architectural overhauls, sub-zero bugs fixed, immersive new UI flows, and freezing-cool improvements:

### 🦸 Character Creation Flow (NEW!)
*   **Create Character Interface**: A massive new robust flow (`CreateCharacter.tsx`) for generating player characters, featuring race/class selection, stat point-buy systems, and auto-populated racial bonuses.
*   **Rules & Loadouts**: Deeply integrated 5e `characterRules.ts` and `classLoadouts.ts` to instantly calculate derived AC, HP thresholds, and starting equipment based on SRD rules.
*   **Compendium Search**: Native ability to search and add Feats, Spells, and Equipment natively during the creation workflow.

### 🏰 Fortified Architecture (Command Processing)
*   **Command Registry System**: The monolithic `CommandService` has been decomposed into a modular registry structure (`backend/app/commands/`), allowing clear separation for `combat`, `exploration`, `interaction`, and `system` commands.
*   **Service Refactor**: A massive overhaul to the `GameService` ensures `GameState`, `Player`, and `Enemy` objects are accurately tracked, saved, and loaded with proper `session_id`s.
*   **Turn Manager Fixes**: Addressed crashes when enemies are defeated, ensuring smooth turn progression even in the coldest encounters.

### 🎒 Winter Supplies (UI Improvements)
*   **Loot Modal**: A new `LootModal.tsx` handles item dropping and generation natively via `inventory.py` sockets after successful encounters.
*   **Command Suggestions**: Added `CommandSuggestions.tsx` to intuitively suggest slash/at-commands as you type.
*   **Entity List & Scene Viz**: Immersive real-time tracking of combatants (`EntityListPanel`) and DM narrative visualizations (`SceneVisPanel`), now completely aware of bounding-boxes to prevent cutoffs.

### 🤖 AI Game Master Upgrades
*   **Dynamic Combat Narration**: Opportunity attacks now trigger custom DM narrations.
*   **Identify Command Overhaul**: The `@identify` command's mechanical success now perfectly dictates the narrative outcome.
*   **AI Token Counter Fixed**: Spectral economy restored! The UI now accurately bills token usage from LangGraph and Gemini models after intense combat turns.

### 🗄️ Frosty Infrastructure & Testing
*   **Expanded Verification Suite**: Added robust testing for monster attacks (`test_monster_attack.py`), equipment stats verification, and batched save testing.
*   **Database Migration**: Migrated from SQLite to robust PostgreSQL structure.
*   **Docker-Compose**: Included local `docker-compose.yml` for standing up the connected Postgres instances easily.
*   **Logging Refactor**: Cleansed the terminal of `print` clutter—everything is tracked via proper standard `logging`.
*   **Cloud Ready**: A robust deployment script (`deploy_cloud.ps1`) makes Cloud Run deployment a breeze.

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
