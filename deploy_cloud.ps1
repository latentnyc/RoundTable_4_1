# Deploy Cloud Script
param (
    [string]$ProjectID = "roundtable41-1dc2c",
    [string]$Region = "us-central1",
    [string]$DBInstance = "roundtable41-1dc2c:us-central1:roundtable-db",
    [string]$DBName = "roundtable_prod",
    [string]$DBUser = "postgres"
)

Write-Host "Deploying to Project: $ProjectID"

# 0. Load Password from .env
$envFile = "backend/.env"
$DBPassword = $null

$GeminiKey = $null

if (Test-Path $envFile) {
    $content = Get-Content $envFile
    foreach ($line in $content) {
        if ($line -match "^DB_PASSWORD=(.*)") { $DBPassword = $matches[1].Trim() }
        if ($line -match "^GEMINI_API_KEY=(.*)") { $GeminiKey = $matches[1].Trim() }
    }
    if ([string]::IsNullOrEmpty($DBPassword)) {
        foreach ($line in $content) {
            if ($line -match "^DATABASE_URL=.*://.*:(.*)@") { $DBPassword = $matches[1].Trim() }
        }
    }
}

if ([string]::IsNullOrEmpty($DBPassword)) {
    Write-Warning "Could not find DB_PASSWORD or valid DATABASE_URL in backend/.env"
    $DBPassword = Read-Host -Prompt "Enter DB Password manually" -AsSecureString
    $DBPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($DBPassword))
} else {
    Write-Host "Loaded DB Password from .env." -ForegroundColor Green
}

# Update Cloud SQL User
Write-Host "Ensuring Cloud SQL user '$DBUser' has the configured password..."
$InstanceShortName = $DBInstance.Split(':')[-1]
gcloud sql users set-password $DBUser --instance=$InstanceShortName --password=$DBPassword --project=$ProjectID
if ($LASTEXITCODE -eq 0) { Write-Host "Password synchronized successfully." -ForegroundColor Green }

# --- DATABASE RESET LOGIC (MOVED START) ---
Write-Host "`n----------------------------------------------------------------"
Write-Host "DATABASE MANAGEMENT"
Write-Host "----------------------------------------------------------------"
Write-Host "Do you want to RESET the Cloud SQL database? (This will DROP and RECREATE '$DBName') (y/N)" -ForegroundColor Yellow
$resetDb = Read-Host "Enter 'y' to confirm reset, or press Enter to skip"
if ($resetDb -match "^[yY]$") {
    $resetDb = "y"
    Write-Host "Reset Confirmed!" -ForegroundColor Red
} else {
    $resetDb = "n"
    Write-Host "Skipping Reset." -ForegroundColor Green
}

if ($resetDb -eq "y") {
    Write-Host "Dropping database '$DBName' via Cloud SQL API..." -ForegroundColor Cyan
    # Notice: we removed 2>$null so if it fails due to active connections, the user sees it!
    gcloud sql databases delete $DBName --instance=$InstanceShortName --project=$ProjectID --quiet

    Write-Host "Creating fresh database '$DBName'..." -ForegroundColor Cyan
    gcloud sql databases create $DBName --instance=$InstanceShortName --project=$ProjectID

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database reset (re-created) successfully." -ForegroundColor Green
        Write-Host "Note: Schema will be initialized when the Backend service starts." -ForegroundColor Gray
    } else {
        Write-Error "Failed to re-create database. Please ensure no open tabs are keeping connections alive."
        exit 1
    }
} else {
    # Ensure Database exists
    Write-Host "Ensuring Database '$DBName' exists on Cloud SQL..."
    gcloud sql databases create $DBName --instance=$InstanceShortName --project=$ProjectID 2>$null
}
# -----------------------------

# 1. Build Frontend
Write-Host "Building Frontend..."
Set-Location "frontend"
npm run build
if ($LASTEXITCODE -ne 0) { Write-Error "Frontend build failed"; exit 1 }
Set-Location ..

# 2. Build Backend Container (Using Cloud Build)
Write-Host "Building Backend Container on Google Cloud..."
# Build from Root Context (.) so we can include 'games/' and 'backend/'
Copy-Item backend\Dockerfile .\Dockerfile -Force
gcloud builds submit --tag gcr.io/$ProjectID/roundtable-backend:latest .
$buildExitCode = $LASTEXITCODE
Remove-Item .\Dockerfile -Force
if ($buildExitCode -ne 0) { Write-Error "Backend build failed"; exit 1 }



# 3. Deploy Backend
Write-Host "Deploying Backend to Cloud Run..."

$deployArgs = @(
    "deploy", "roundtable-backend",
    "--image", "gcr.io/$ProjectID/roundtable-backend:latest",
    "--platform", "managed",
    "--region", $Region,
    "--allow-unauthenticated",
    "--project", $ProjectID,
    "--add-cloudsql-instances", $DBInstance
)

$DB_URL = "postgresql+asyncpg://${DBUser}:${DBPassword}@/${DBName}?host=/cloudsql/${DBInstance}"
$envVars = "DATABASE_URL=$DB_URL"
if ($GeminiKey) {
    $envVars += ",GEMINI_API_KEY=$GeminiKey"
}
$deployArgs += "--set-env-vars", $envVars
Write-Host "Updating Service Environment Variables..." -ForegroundColor Green

gcloud run @deployArgs

# 4. Deploy Frontend
Write-Host "Deploying Frontend to Firebase..."
Set-Location "frontend"
firebase deploy --only hosting --project $ProjectID
Set-Location ..

Write-Host "Deployment Complete!"
