# RoundTable 4.1


A TTRPG application with AI-powered Game Master and 5e rules integration.

## Changelog vs Previous Version
*   **Backend Refactor**: Migrated `campaigns` router and other key services to use **SQLAlchemy Core** for better performance and explicit query control, moving away from ORM dependency for complex queries.
*   **NPC Identification System**: Implemented `@identify` command mechanics, allowing players to roll Intelligence checks to reveal NPC names/roles. Added `identify_narration` mode to DM Agent for immersive reveals.
*   **Combat Improvements**:
    *   **Counterattacks**: Implemented recursive counterattack logic for hostile NPCs/Enemies with depth limits to prevent infinite loops.
    *   **Attack Verification**: Added regression tests (`verify_attack_fix.py`) to ensure DM does not suggest mechanical commands in narration.
*   **Bug Fixes**:
    *   **Message Visibility**: Fixed frontend/backend sync ensuring all messages (including rapid-fire mechanics) have unique IDs and timestamps to prevent frontend deduplication from hiding them.
    *   **SocketIO Reliability**: Enhanced `SocketIOCallbackHandler` to handle `ToolMessage` errors and prevent crashes during tool execution.
    *   **DM Repetition**: Refined System Prompt in `ai_service.py` to prevent the DM from repetitively stating "I am the DM" or mechanically restating the user's action.
*   **Frontend**:
    *   **Log Viewer**: Enhanced `LogViewer.tsx` with color-coding for different agents (System vs DM vs Character) and tool outputs.
    *   **Linting**: Addressed various React/TypeScript linting warnings.

## Future Improvements
*   [ ] **Entity Privacy**: Implement system for public vs. hidden entity names (e.g., "Unknown Figure" vs "Silas") to improve immersion before successful identification.



## Setup


1.  **One-Click Run (Recommended)**
    The `run_local.ps1` script handles all setup (Java path, Python venv, Node modules) and runs the full stack.
    ```powershell
    .\run_local.ps1
    ```

2.  **Manual Setup (Advanced)**
    If you prefer running components individually:

    **Backend**
    ```bash
    cd backend
    python -m venv venv
    .\venv\Scripts\activate
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

## Features

*   **5e Compendium**: Integrated 2014 SRD data for spells, monsters, classes, races, and items.
*   **AI Game Master**: Powered by LangGraph and Gemini.
