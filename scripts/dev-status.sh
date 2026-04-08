#!/usr/bin/env bash
set -uo pipefail

# RoundTable 4.1 — Check service status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_ROOT/scripts/.dev-pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_port() {
    local port=$1
    local name=$2
    local url=$3
    local pid=""

    # Try to find PID from PID file or port
    if lsof -i ":$port" &>/dev/null; then
        pid=$(lsof -ti ":$port" 2>/dev/null | head -1)
        echo -e "  ${GREEN}RUNNING${NC}  $name  (port $port, PID $pid)"
        if [ -n "$url" ]; then
            echo -e "           ${url}"
        fi
    else
        echo -e "  ${RED}STOPPED${NC}  $name  (port $port)"
    fi
}

echo ""
echo "RoundTable 4.1 — Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# PostgreSQL (Docker) — check via docker compose, not lsof (port is forwarded by Docker)
if docker compose -f "$PROJECT_ROOT/docker-compose.yml" ps --status running db 2>/dev/null | grep -q "db"; then
    echo -e "  ${GREEN}RUNNING${NC}  PostgreSQL  (port 5432, container roundtable_4_1-db-1)"
else
    echo -e "  ${RED}STOPPED${NC}  PostgreSQL  (port 5432)"
fi

check_port 9099 "Firebase Auth Emulator" ""
check_port 8080 "Firebase Firestore Emulator" ""
check_port 4000 "Firebase Emulator UI" "http://localhost:4000"
check_port 8000 "Backend (FastAPI)" "http://localhost:8000"
check_port 3000 "Frontend (Vite)" "http://localhost:3000"

echo ""

# PID file status
if [ -f "$PID_FILE" ]; then
    echo -e "  PID file: ${GREEN}exists${NC} ($PID_FILE)"
else
    echo -e "  PID file: ${YELLOW}not found${NC}"
fi

echo ""
