#!/usr/bin/env bash
set -uo pipefail

# RoundTable 4.1 — View service logs
# Usage:
#   ./scripts/dev-logs.sh              # tail all logs interleaved
#   ./scripts/dev-logs.sh backend      # tail backend only
#   ./scripts/dev-logs.sh frontend     # tail frontend only
#   ./scripts/dev-logs.sh firebase     # tail firebase only

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/.dev-logs"

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ ! -d "$LOG_DIR" ]; then
    echo -e "${RED}No log directory found.${NC} Start services first with ./scripts/dev-start.sh"
    exit 1
fi

SERVICE="${1:-all}"

case "$SERVICE" in
    backend)
        if [ -f "$LOG_DIR/backend.log" ]; then
            tail -f "$LOG_DIR/backend.log"
        else
            echo -e "${YELLOW}No backend log found.${NC}"
        fi
        ;;
    frontend)
        if [ -f "$LOG_DIR/frontend.log" ]; then
            tail -f "$LOG_DIR/frontend.log"
        else
            echo -e "${YELLOW}No frontend log found.${NC}"
        fi
        ;;
    firebase)
        if [ -f "$LOG_DIR/firebase.log" ]; then
            tail -f "$LOG_DIR/firebase.log"
        else
            echo -e "${YELLOW}No firebase log found.${NC}"
        fi
        ;;
    all)
        # Interleave all logs with prefixes
        tail -f \
            "$LOG_DIR/firebase.log" \
            "$LOG_DIR/backend.log" \
            "$LOG_DIR/frontend.log" \
            2>/dev/null || echo -e "${YELLOW}Some log files not found. Are all services running?${NC}"
        ;;
    *)
        echo "Usage: $0 [backend|frontend|firebase|all]"
        exit 1
        ;;
esac
