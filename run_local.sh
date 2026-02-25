#!/bin/bash
# run_local.sh

# Exit on error
set -e

echo "Starting RoundTable 4.1 Local Environment (macOS/Linux)..."

# Ask for DB Reset early
echo -e "\033[1;33mDo you want to RESET the database? (y/N)\033[0m"
read -r -p "Enter 'y' to confirm reset, or press Enter to skip: " RESET_CONFIRM
if [[ "$RESET_CONFIRM" =~ ^[Yy]$ ]]; then
    RESET_CONFIRM="y"
    echo -e "\033[1;31mReset Confirmed!\033[0m"
else
    RESET_CONFIRM="n"
    echo -e "\033[1;32mSkipping Reset.\033[0m"
fi

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


echo "Ensuring Database (Docker Postgres) is running..."
if ! docker compose up -d db; then
    echo "Error starting Docker. Please ensure Docker Desktop is running."
    exit 1
fi

# Wait for DB to be ready (simple pause for now)
sleep 5

export DATABASE_URL="postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres"

if [ "$RESET_CONFIRM" == "y" ]; then
    echo "RESETTING DATABASE..."
    python3 backend/scripts/manage_db.py reset --force
fi

echo "Initializing Database Schema..."
python3 backend/db/init_db.py

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
export FIREBASE_DATABASE_EMULATOR_HOST="127.0.0.1:9000"
export GCLOUD_PROJECT="roundtable41-1dc2c"

# 5. Run Everything
echo "Launching services..."
echo "Press Ctrl+C to stop all services."

# Use npx to run concurrently
npx -y concurrently -k -n "firebase,backend,frontend" -c "yellow,blue,green" \
    "npx -y -p firebase-tools firebase emulators:start --only auth,firestore,database,hosting,ui" \
    "cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000 --log-level debug" \
    "cd frontend && npm run dev"
