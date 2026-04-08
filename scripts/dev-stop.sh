#!/usr/bin/env bash
set -uo pipefail

# RoundTable 4.1 — Stop all development services
# Usage: ./scripts/dev-stop.sh [--with-db]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_ROOT/scripts/.dev-pids"
LOG_DIR="$PROJECT_ROOT/scripts/.dev-logs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

STOP_DB=false
for arg in "$@"; do
    case "$arg" in
        --with-db) STOP_DB=true ;;
    esac
done

# Kill a process and its children
kill_tree() {
    local pid=$1
    local name=$2
    if kill -0 "$pid" 2>/dev/null; then
        # Kill the process group (handles children like node, java subprocesses)
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
        # Wait briefly for graceful shutdown
        for i in $(seq 1 5); do
            if ! kill -0 "$pid" 2>/dev/null; then
                ok "Stopped $name (PID $pid)"
                return
            fi
            sleep 1
        done
        # Force kill if still running
        kill -9 "$pid" 2>/dev/null || true
        ok "Force-stopped $name (PID $pid)"
    else
        warn "$name (PID $pid) was not running"
    fi
}

echo ""
info "Stopping RoundTable services..."

if [ -f "$PID_FILE" ]; then
    source "$PID_FILE"

    # Stop in reverse order
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill_tree "$FRONTEND_PID" "Frontend"
    fi
    if [ -n "${BACKEND_PID:-}" ]; then
        kill_tree "$BACKEND_PID" "Backend"
    fi
    if [ -n "${FIREBASE_PID:-}" ]; then
        kill_tree "$FIREBASE_PID" "Firebase Emulators"
    fi

    rm -f "$PID_FILE"
else
    warn "No PID file found. Trying to find processes by port..."

    # Fallback: kill by port
    for port_name in "3000:Frontend" "8000:Backend" "9099:Firebase"; do
        port="${port_name%%:*}"
        name="${port_name##*:}"
        pid=$(lsof -ti ":$port" 2>/dev/null | head -1)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null && ok "Stopped $name (port $port, PID $pid)" || warn "Could not stop $name"
        fi
    done
fi

# Optionally stop database
if [ "$STOP_DB" = true ]; then
    info "Stopping PostgreSQL..."
    cd "$PROJECT_ROOT"
    docker compose stop db 2>&1 | grep -v "^$" || true
    ok "PostgreSQL stopped"
fi

# Clean up any lingering Firebase emulator processes
pkill -f "firebase.*emulators" 2>/dev/null || true

# Verify ports are free
echo ""
all_clear=true
for port in 3000 8000 9099 8080 4000; do
    if lsof -i ":$port" &>/dev/null; then
        warn "Port $port still in use"
        all_clear=false
    fi
done

if [ "$all_clear" = true ]; then
    ok "All ports are free"
fi

echo ""
echo -e "${GREEN}All services stopped.${NC}"
echo ""
