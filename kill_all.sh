#!/bin/bash

echo "Killing processes on ports 8000 (uvicorn/fastapi), 5173 (vite/react), and Firebase Emulator ports (4000, 4400, 4500, 5002, 8080, 9000, 9099, 9150)..."

# Array of ports used by the stack
PORTS=(8000 5173 4000 4400 4500 5002 8080 9000 9099 9150)

for PORT in "${PORTS[@]}"; do
    # Find PIDs listening on the port
    PIDS=$(lsof -t -i :"$PORT" -s TCP:LISTEN 2>/dev/null)
    
    if [ ! -z "$PIDS" ]; then
        echo "Found processes holding port $PORT: $PIDS"
        for PID in $PIDS; do
            echo "Killing PID $PID..."
            kill -9 "$PID" 2>/dev/null || true
        done
        echo "Port $PORT cleared."
    else
        echo "Port $PORT is free."
    fi
done

echo "Attempting to forcefully close dangling Node or Python processes just in case..."
pkill -f "uvicorn" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "firebase" 2>/dev/null || true

echo "Cleanup complete."
