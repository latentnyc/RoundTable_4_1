#!/usr/bin/env bash
set -euo pipefail

# RoundTable 4.1 — Start all development services
# Usage: ./scripts/dev-start.sh [--skip-deps] [--reset-db]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/scripts/.dev-logs"
PID_FILE="$PROJECT_ROOT/scripts/.dev-pids"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# Parse args
SKIP_DEPS=false
RESET_DB=false
for arg in "$@"; do
    case "$arg" in
        --skip-deps) SKIP_DEPS=true ;;
        --reset-db)  RESET_DB=true ;;
        *)           warn "Unknown argument: $arg" ;;
    esac
done

# ─────────────────────────────────────────────
# 1. Prerequisites
# ─────────────────────────────────────────────
info "Checking prerequisites..."

# Docker
if ! docker info &>/dev/null; then
    fail "Docker is not running. Start Docker Desktop first."
fi
ok "Docker is running"

# Java (for Firebase emulators)
export JAVA_HOME="/opt/homebrew/opt/openjdk@21"
export PATH="$JAVA_HOME/bin:$PATH"
if ! java -version &>/dev/null; then
    fail "Java 21 not found. Install with: brew install openjdk@21"
fi
ok "Java 21 available"

# Python
if [ ! -f "$PROJECT_ROOT/backend/venv/bin/python" ]; then
    info "Creating Python virtual environment..."
    python3.11 -m venv "$PROJECT_ROOT/backend/venv"
fi
ok "Python venv exists"

# Check if already running
if [ -f "$PID_FILE" ]; then
    warn "Services may already be running (PID file exists)."
    warn "Run ./scripts/dev-stop.sh first, or delete $PID_FILE if stale."
    exit 1
fi

# Check ports
for port in 3000 8000 9099 8080 4000; do
    if lsof -i ":$port" &>/dev/null; then
        fail "Port $port is already in use. Stop the process or run dev-stop.sh"
    fi
done
ok "All ports available (3000, 8000, 9099, 8080, 4000)"

# ─────────────────────────────────────────────
# 2. Dependencies (optional skip)
# ─────────────────────────────────────────────
if [ "$SKIP_DEPS" = false ]; then
    info "Checking backend dependencies..."
    cd "$PROJECT_ROOT/backend"
    ./venv/bin/pip install -q -r requirements.txt 2>&1 | tail -1 || true
    ok "Backend deps up to date"

    info "Checking frontend dependencies..."
    cd "$PROJECT_ROOT/frontend"
    if [ ! -d "node_modules" ]; then
        npm ci --silent
    fi
    ok "Frontend deps up to date"
    cd "$PROJECT_ROOT"
fi

# ─────────────────────────────────────────────
# 3. Database
# ─────────────────────────────────────────────
info "Starting PostgreSQL..."
cd "$PROJECT_ROOT"
docker compose up -d db 2>&1 | grep -v "^$" || true

# Wait for DB to accept connections
info "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U postgres &>/dev/null; then
        break
    fi
    if [ "$i" -eq 30 ]; then
        fail "PostgreSQL failed to start within 30 seconds"
    fi
    sleep 1
done
ok "PostgreSQL ready on port 5432"

# Optional DB reset
if [ "$RESET_DB" = true ]; then
    warn "Resetting database..."
    cd "$PROJECT_ROOT/backend"
    ./venv/bin/python scripts/manage_db.py reset --force 2>&1 || warn "DB reset script failed (may not exist)"
    cd "$PROJECT_ROOT"
fi

# ─────────────────────────────────────────────
# 4. Start services
# ─────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# 4a. Firebase Emulators
info "Starting Firebase emulators..."
cd "$PROJECT_ROOT"
npx -y -p firebase-tools firebase emulators:start \
    --only auth,firestore \
    --project roundtable41-1dc2c \
    > "$LOG_DIR/firebase.log" 2>&1 &
FIREBASE_PID=$!

# Wait for auth emulator
info "Waiting for Firebase auth emulator (port 9099)..."
for i in $(seq 1 60); do
    if curl -s http://127.0.0.1:9099/ &>/dev/null; then
        break
    fi
    if ! kill -0 "$FIREBASE_PID" 2>/dev/null; then
        fail "Firebase emulators crashed. Check $LOG_DIR/firebase.log"
    fi
    if [ "$i" -eq 60 ]; then
        fail "Firebase emulators failed to start within 60s. Check $LOG_DIR/firebase.log"
    fi
    sleep 1
done
ok "Firebase emulators ready (auth:9099, firestore:8080, ui:4000)"

# 4b. Backend
info "Starting backend..."
cd "$PROJECT_ROOT/backend"
./venv/bin/uvicorn main:app --reload --port 8000 --log-level info \
    > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# Wait for backend health check
info "Waiting for backend (port 8000)..."
for i in $(seq 1 90); do
    if curl -s http://localhost:8000/ | grep -q "online" 2>/dev/null; then
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo ""
        fail "Backend crashed. Check $LOG_DIR/backend.log"
    fi
    if [ "$i" -eq 90 ]; then
        echo ""
        fail "Backend failed to start within 90s. Check $LOG_DIR/backend.log"
    fi
    sleep 1
done
ok "Backend ready on port 8000"

# 4c. Frontend
info "Starting frontend..."
cd "$PROJECT_ROOT/frontend"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Wait for frontend
info "Waiting for frontend (port 3000)..."
for i in $(seq 1 30); do
    if curl -s http://localhost:3000/ &>/dev/null; then
        break
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        fail "Frontend crashed. Check $LOG_DIR/frontend.log"
    fi
    if [ "$i" -eq 30 ]; then
        fail "Frontend failed to start within 30s. Check $LOG_DIR/frontend.log"
    fi
    sleep 1
done
ok "Frontend ready on port 3000"

# ─────────────────────────────────────────────
# 5. Save PIDs and print summary
# ─────────────────────────────────────────────
cat > "$PID_FILE" <<EOF
FIREBASE_PID=$FIREBASE_PID
BACKEND_PID=$BACKEND_PID
FRONTEND_PID=$FRONTEND_PID
EOF

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  RoundTable 4.1 — All services running${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Frontend:           ${BLUE}http://localhost:3000${NC}"
echo -e "  Backend API:        ${BLUE}http://localhost:8000${NC}"
echo -e "  Firebase Emulators: ${BLUE}http://localhost:4000${NC}"
echo ""
echo -e "  Test Campaign:      ${BLUE}http://localhost:3000/campaign_dash/dev-test-campaign-001${NC}"
echo ""
echo -e "  First time? After login, run:"
echo -e "    curl -X POST http://localhost:8000/dev/quickjoin/dev-test-campaign-001 -H 'Authorization: Bearer <token>'"
echo -e "  Or just navigate to the test campaign URL above — it handles setup."
echo ""
echo -e "  Logs:    ./scripts/dev-logs.sh [backend|frontend|firebase]"
echo -e "  Status:  ./scripts/dev-status.sh"
echo -e "  Stop:    ./scripts/dev-stop.sh"
echo ""
