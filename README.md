# RoundTable 4.1

A TTRPG application with AI-powered Game Master and 5e rules integration.

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
