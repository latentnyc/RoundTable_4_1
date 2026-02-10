# Orphaned Code Report: Transition to Firebase-Only Development

This report identifies codebase components that are either confirmed orphaned (unused) or are transitional artifacts from a previous architecture (FastAPI + SQLite + Docker) that conflict with a "pure" Firebase development model.

## 1. Confirmed Orphans (Recommended for Deletion)

These files and directories appear to be unused or remnants of past experiments:

*   **`chroma_db/` Directory**
    *   **Evidence**: The `chromadb` package is **not** listed in `backend/requirements.txt`. The `backend/` code does not import or use ChromaDB; it relies on `aiosqlite`.
    *   **Action**: Safe to delete.

*   **`dataconnect/` Directory**
    *   **Evidence**: Firebase Data Connect is for SQL (PostgreSQL). The application actively uses SQLite (`game.db`). There is no configuration linking the app to a Data Connect instance.
    *   **Action**: Safe to delete.

*   **Root-Level Migration Scripts**
    *   **Files**: `migrate_feats.py`, `append_backgrounds.py`, `verify_compendium_search.py`, `inspect_*.py`
    *   **Evidence**: These are likely one-off utility scripts for data verification or migration that are no longer part of the core application flow.
    *   **Action**: Archive (move to `scripts/archive/`) or delete.

## 2. Transitional Components (Critical - DO NOT DELETE YET)

These components are part of the *current* running application but represent technical debt if the goal is "only developing in Firebase now".

*   **`backend/` Directory (Python FastAPI Server)**
    *   **Status**: **Active Core Logic**. The frontend (`src/lib/api.ts`) depends entirely on this API for data operations.
    *   **Conflict**: In a pure Firebase app, backend logic typically resides in Cloud Functions (`functions/`). Currently, `functions/main.py` is empty.
    *   **Path Forward**: You must migrate the logic from `backend/` to `functions/` (using the Firebase Admin SDK) before this directory can be removed.

*   **`game.db` (SQLite Database)**
    *   **Status**: **Active Data Store**. Holds all campaign, character, and chat data.
    *   **Conflict**: Firebase apps typically use **Firestore**.
    *   **Path Forward**: Data migration from SQLite to Firestore is required.

*   **`backend/deploy.ps1` & `backend/Dockerfile`**
    *   **Status**: **Active Deployment**. Deploys the FastAPI container to Cloud Run with a persistent volume.
    *   **Conflict**: "Developing in Firebase" usually implies `firebase deploy` (Hosting + Functions). Custom Docker deployments are outside the standard Firebase flow.
    *   **Path Forward**: Once logic is moved to Functions, these deployment scripts become obsolete.

## 3. Configuration Review

*   **`firebase.json`**
    *   **Current State**: Configures Hosting (rewrites to `index.html`), Firestore, and Emulators.
    *   **Missing**: Does **not** configure a `rewrites` rule to direct API traffic (`/api/**`) to a Cloud Function or Cloud Run service. This forces the frontend to rely on a separately running backend (localhost:8000), which contradicts a unified "Firebase-only" dev experience.

## Recommendations

1.  **Immediate Cleanup**: Delete `chroma_db/` and `dataconnect/`.
2.  **Migration Planning**:
    *   Create a plan to port specific API endpoints (e.g., `/characters`, `/campaigns`) from FastAPI to Firebase Functions (`functions/main.py`).
    *   Script a data migration from `game.db` to Firestore Emulator.
3.  **Update Deployment**: Modify `firebase.json` to handle API routes via Functions, removing the need for `deploy.ps1`.
