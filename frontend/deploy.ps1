# Deployment Script (Frontend)

# Deploy Frontend to Firebase Hosting
# Must be run from the frontend directory or with correct context

if (Test-Path .env.production) {
    Get-Content .env.production | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $parts = $line.Split('=', 2)
            if ($parts.Length -eq 2) {
                [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
            }
        }
    }
}

Write-Host "Building Frontend with VITE_API_URL=$([System.Environment]::GetEnvironmentVariable('VITE_API_URL'))..."
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed!"
    exit 1
}

Write-Host "Deploying to Firebase Hosting..."
firebase deploy --only hosting
