# Set Java Path for Firebase Emulators
$env:Path = 'C:\Program Files\Java\jdk-21.0.10\bin;' + $env:Path

# Set Emulator Host Variables for Backend/Frontend to find them
$env:FIRESTORE_EMULATOR_HOST="localhost:8080"
$env:FIREBASE_AUTH_EMULATOR_HOST="localhost:9099"

# Install dependencies if needed (optional, uncomment if desired)
# npm install

# Run Concurrently
# 1. Firebase Emulators
# 2. Backend (assuming venv is set up)
# 3. Frontend
npx concurrently -k -n "firebase,backend,frontend" -c "yellow,blue,green" `
    "firebase emulators:start --only auth,firestore,hosting,ui" `
    "cd backend && venv\Scripts\python -m uvicorn main:app --reload --port 8000" `
    "cd frontend && npm run dev"
