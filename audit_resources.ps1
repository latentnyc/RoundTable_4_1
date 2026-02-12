$projects = @(
    "roundtable41-1dc2c",
    "roundtable41",
    "stockdashboard-486720",
    "python-test-255414",
    "gen-lang-client-0868970660",
    "project-c8f44b5e-715e-46ba-854"
)

foreach ($p in $projects) {
    Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Project: $p" -ForegroundColor Yellow
    Write-Host "----------------------------------------------------------------"

    # Cloud Run
    Write-Host "  [Cloud Run Services]" -ForegroundColor White
    try {
        $run = gcloud run services list --project $p --platform managed --format="value(SERVICE,REGION,URL)" 2>$null
        if ($run) { $run } else { Write-Host "    (None)" -ForegroundColor DarkGray }
    } catch { Write-Host "    (Error or API disabled)" -ForegroundColor Red }

    # Cloud SQL
    Write-Host "  [Cloud SQL Instances]" -ForegroundColor White
    try {
        $sql = gcloud sql instances list --project $p --format="value(NAME,DATABASE_VERSION,TIER,STATE)" 2>$null
        if ($sql) { $sql } else { Write-Host "    (None)" -ForegroundColor DarkGray }
    } catch { Write-Host "    (Error or API disabled)" -ForegroundColor Red }

    # Storage Buckets
    Write-Host "  [Storage Buckets]" -ForegroundColor White
    try {
        $buckets = gcloud storage buckets list --project $p --format="value(name)" 2>$null
        if ($buckets) { $buckets } else { Write-Host "    (None)" -ForegroundColor DarkGray }
    } catch { Write-Host "    (Error or API disabled)" -ForegroundColor Red }

    Write-Host ""
}
