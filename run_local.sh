#!/bin/bash
# run_local.sh

# Exit on error
set -e

echo "Starting RoundTable 4.1 Local Environment (macOS/Linux)..."

# 1. Java Setup
export JAVA_HOME="/opt/homebrew/opt/openjdk@21"
export PATH="$JAVA_HOME/bin:$PATH"

if java -version >/dev/null 2>&1; then
    echo "Java configured: $(which java)"
else
    echo "Error: Java 21 not found. Please install via brew install openjdk@21"
    exit 1
fi

# 2. Backend Environment & DB Setup
echo "Checking Backend configuration..."
if [ ! -d "backend/venv" ]; then
    echo "Creating Python virtual environment..."
    /opt/homebrew/bin/python3.11 -m venv backend/venv
fi

source backend/venv/bin/activate
echo "Ensuring backend dependencies..."
pip install -r backend/requirements.txt

# Database Logic
DB_URL=$(grep "^DATABASE_URL=" backend/.env | cut -d '=' -f 2)

if [[ "$DB_URL" == postgresql* ]]; then
    echo "---------------------------------------------------"
    echo "Detected Cloud SQL Configuration (Postgres)"
    echo "---------------------------------------------------"

    # 1. Check/Start Instance
    # Need gcloud in path
    if ! command -v gcloud &> /dev/null; then
         # Try sourcing .zshrc if user uses zsh, or standard paths
         source ~/.zshrc 2>/dev/null || true
         export PATH="/opt/homebrew/share/google-cloud-sdk/bin:$PATH"
    fi

    echo "Checking Cloud SQL Instance status..."
    INSTANCE_STATE=$(gcloud sql instances describe roundtable-db --project=roundtable41-1dc2c --format="value(state)" 2>/dev/null || echo "UNKNOWN")

    if [ "$INSTANCE_STATE" != "RUNNABLE" ]; then
        echo "Instance state is: $INSTANCE_STATE. Starting instance..."
        gcloud sql instances patch roundtable-db --project=roundtable41-1dc2c --activation-policy=ALWAYS
        # Wait loop? patch is async but gcloud waits by default usually unless --async
        # But patch command output says "Patching..." then returns.
        # We should wait until runnable.
        echo "Waiting for instance to be RUNNABLE..."
        while [ "$(gcloud sql instances describe roundtable-db --project=roundtable41-1dc2c --format="value(state)")" != "RUNNABLE" ]; do
            sleep 5
            echo -n "."
        done
        echo "Instance is RUNNABLE."
    else
        echo "Instance is RUNNABLE."
    fi

    # 2. Check/Start Proxy
    if ! lsof -i :5432 >/dev/null; then
        echo "Starting Cloud SQL Proxy..."
        ./run_cloud_sql_proxy.sh > proxy.log 2>&1 &
        PROXY_PID=$!
        echo "Waiting for proxy to start..."
        sleep 5
        if ! lsof -i :5432 >/dev/null; then
            echo "Error: Proxy failed to start (port 5432 not listening). Check proxy.log."
            exit 1
        fi
        echo "Proxy started (PID $PROXY_PID)."
    else
        echo "Cloud SQL Proxy appears to be running (port 5432 in use)."
    fi

    # 3. Reset Database (Optional)
    echo "---------------------------------------------------"
    read -p "Reset Database Schema and Reload Data? (y/N): " RESET_CONFIRM
    if [[ "$RESET_CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Resetting Database Schema..."
        echo "y" | python3 backend/scripts/manage_db.py reset

        # 4. Initialize Data
        echo "Initializing Data..."
        python3 backend/db/init_db.py
    else
        echo "Skipping Database Reset. (Existing data preserved)"
        # Still run init to ensure any NEW migrations apply, but init_db.py handles that safely
        # However, init_db.py also triggers data loading checks in main.py, so we should be good.
        # Actually init_db.py just does schema create_all (idempotent) and migrations.
        echo "Ensuring Schema..."
        python3 backend/db/init_db.py
    fi

else
    echo "---------------------------------------------------"
    echo "Error: Postgres DATABASE_URL not found. Local SQLite is no longer supported."
    echo "Please configure DATABASE_URL in backend/.env"
    echo "---------------------------------------------------"
    exit 1
fi

echo "Backend ready."

# 3. Frontend
echo "Checking Frontend configuration..."
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing Frontend dependencies..."
    cd frontend && npm install && cd ..
fi
echo "Frontend ready."

# 4. Environment Variables
export FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"
export FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099"
export GCLOUD_PROJECT="roundtable41-1dc2c"

# 5. Run Everything
echo "Launching services..."
echo "Press Ctrl+C to stop all services."

# Use npx to run concurrently
npx -y concurrently -k -n "firebase,backend,frontend" -c "yellow,blue,green" \
    "npx -y -p firebase-tools firebase emulators:start --only auth,firestore,hosting,ui" \
    "cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000 --log-level debug" \
    "cd frontend && npm run dev"
