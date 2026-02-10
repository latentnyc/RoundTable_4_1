# Deploy to Cloud Run (Windows Powershell)

$PROJECT_ID = "roundtable41-1dc2c"
$REGION = "us-central1"
$SERVICE_NAME = "roundtable-backend"

# 1. Build Container
echo "Building Container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME "$PSScriptRoot"

# 2. Deploy with CORS & Cloud SQL
echo "Deploying to Cloud Run with CORS and Cloud SQL..."

# Load .env variables
$envFile = "$PSScriptRoot\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -notmatch "^#" -and $line -match "=") {
            $name, $value = $line -split "=", 2
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    echo "Loaded environment variables from .env"
}

# Construct ALLOWED_ORIGINS (Firebase domains + Localhost)
$ALLOWED_ORIGINS = "https://$PROJECT_ID.web.app;https://$PROJECT_ID.firebaseapp.com;http://localhost:3000;http://localhost:5173"

# We add the Cloud SQL instance for PostgreSQL.
$DB_INSTANCE = "$PROJECT_ID`:$REGION`:roundtable-db"
$DB_URL = "postgresql+asyncpg://postgres:roundtable_password@/postgres?host=/cloudsql/$DB_INSTANCE"

# Get ALLOWED_USERS from env or default to empty
$ALLOWED_USERS = $env:ALLOWED_USERS
if (-not $ALLOWED_USERS) {
    Write-Host "WARNING: ALLOWED_USERS is not set. Anyone will be able to sign up!" -ForegroundColor Yellow
    $ALLOWED_USERS = ""
} else {
    Write-Host "Restricting access to: $ALLOWED_USERS" -ForegroundColor Green
}

gcloud beta run deploy $SERVICE_NAME `
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME `
  --platform managed `
  --region $REGION `
  --allow-unauthenticated `
  --execution-environment gen2 `
  --add-cloudsql-instances=$DB_INSTANCE `
  --set-env-vars "DATABASE_URL=$DB_URL,ALLOWED_ORIGINS=$ALLOWED_ORIGINS,FIREBASE_PROJECT_ID=$PROJECT_ID,ALLOWED_USERS=$ALLOWED_USERS" `
  --project $PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment failed!"
    exit 1
}

echo "----------------------------------------------------------------"
echo "Deployment Complete!"
echo "1. Database: Connected to Cloud SQL ($DB_INSTANCE)"
echo "2. CORS: Allowed origins set to $ALLOWED_ORIGINS"
echo "3. API URL: Check the output above for the Service URL."
echo "   If the URL changed, update frontend/.env.production"
echo "----------------------------------------------------------------"
