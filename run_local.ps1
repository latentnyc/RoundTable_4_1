# run_local.ps1

Write-Host "Starting RoundTable 4.1 Local Environment..." -ForegroundColor Cyan

# 1. Java Setup (Crucial for Firebase Emulators)
$javaPath = "C:\Program Files\Java\jdk-21.0.10"
if (Test-Path $javaPath) {
    $env:JAVA_HOME = $javaPath
    $env:Path = "$javaPath\bin;" + $env:Path
    Write-Host "Java configured: $javaPath" -ForegroundColor Green
} else {
    Write-Host "Warning: Java 21 not found at default path ($javaPath). Firebase Emulators might fail if Java is not in PATH." -ForegroundColor Yellow
}

# 2. Backend Dependencies
Write-Host "Checking Backend configuration..." -ForegroundColor Cyan
if (-not (Test-Path "backend\venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv backend\venv
}

# Install/Update requirements silently
Write-Host "Ensuring backend dependencies are installed..." -ForegroundColor Cyan
& "backend\venv\Scripts\python" -m pip install -r backend\requirements.txt | Out-Null
Write-Host "Backend ready." -ForegroundColor Green

# 3. Frontend Dependencies
Write-Host "Checking Frontend configuration..." -ForegroundColor Cyan
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing Frontend dependencies (this may take a moment)..." -ForegroundColor Yellow
    Push-Location frontend
    npm install | Out-Null
    Pop-Location
}
Write-Host "Frontend ready." -ForegroundColor Green

# 4. Set Environment Variables for Emulators
$env:FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"
$env:FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099"
$env:GCLOUD_PROJECT="roundtable-4-1" 

# 5. Run Everything
Write-Host "Launching services..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow

# We use npx concurrently to run everything.
# - Firebase Emulators
# - Backend (using venv python, running from backend dir)
# - Frontend (using npm run dev, running from frontend dir)

npx concurrently -k -n "firebase,backend,frontend" -c "yellow,blue,green" `
    "firebase emulators:start --only auth,firestore,hosting,ui" `
    "cd backend && venv\Scripts\python -m uvicorn main:app --reload --port 8000" `
    "cd frontend && npm run dev"
