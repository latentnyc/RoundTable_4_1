Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "py" -Force -ErrorAction SilentlyContinue
Write-Host "All python processes killed."
