# RoundTable_4_1 - Movement, Maps, and Mranged Attacks Update 🗺️🏹

A TTRPG application with an AI-powered Game Master and 5e rules integration.

## 🏹 The "Movement, Maps, and Mranged Attacks" Changelog

We've been hard at work forging new paths and sharpening our arrows! This massive update brings rock-solid stability to combat, expands our maps, and makes sure every strike (ranged or otherwise) counts. Here is what's new:

### ⚔️ Combat Loop & Turn Concurrency
*   **Rock-Solid Turns**: Completely overhauled the `TurnManager` and combat loop to prevent race conditions and AI turn skipping. No more hanging encounters!
*   **Precision @attack**: Fixed critical targeting bugs ensuring the `@attack` command flawlessly identifies and strikes entities on the hex map.

### 🗺️ Maps, State, & Synchronization 
*   **State Stability**: Major enhancements to `SocketProvider` and game state patching. Synchronization between the server and your party is now smoother than ever.
*   **Corpse Rendering & Loot Bags**: Defeated foes no longer awkwardly stand around! Enemies now correctly collapse into interactive loot bags on the battlemap.
*   **Campaign Tuning**: Expanded several campaign maps (including `Goblin_Combat_Test.json`) with new NPC data, interactables, and fresh goblin encounters.

### 🗣️ Immersive Chat & AI Mastery
*   **Structured Messaging**: Introduced a robust `message_type` discriminator distinguishing between Player Chat, DM Narration, and System Messages for a cleaner, more readable interface.
*   **AI Tool Invocations**: Upgraded the AI Service with better tool activity logging and frontend support, giving you deeper insights into the DM's thought process behind the screen.

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
