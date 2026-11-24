# EvoCode V2 - Unified Start Script
# Starts backend (port 8000), frontend dashboard (port 3001), and test-target app (port 3000)

Write-Host "=== Starting EvoCode V2 Suite ===" -ForegroundColor Cyan

# Kill any existing processes on ports 8000, 3001, and 3000
$portsToKill = @(8000, 3001, 3000)
foreach ($port in $portsToKill) {
    $proc = netstat -ano | findstr ":$port " | Select-String "LISTENING"
    if ($proc) {
        $procId = ($proc -split '\s+')[-1]
        Write-Host "Killing process $procId on port $port" -ForegroundColor Yellow
        taskkill /F /PID $procId 2>$null
        Start-Sleep -Milliseconds 400
    }
}

$backendPath = "$PSScriptRoot\evocode-v1\backend"
$frontendPath = "$PSScriptRoot\evocode-v1\frontend"
$targetPath = "C:\Users\hanua\OneDrive\Desktop\evocode-test-target"

# 1. Start backend (port 8000)
Write-Host "`n[1/3] Starting Backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; Write-Host 'Backend running on http://localhost:8000' -ForegroundColor Green; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload" -WindowStyle Normal

Start-Sleep -Seconds 3

# 2. Start frontend dashboard (port 3001)
Write-Host "[2/3] Starting Frontend Dashboard on http://localhost:3001 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; Write-Host 'Frontend Dashboard running on http://localhost:3001' -ForegroundColor Green; npm run dev" -WindowStyle Normal

Start-Sleep -Seconds 2

# 3. Start target application with Feedback Widget (port 3000)
if (Test-Path $targetPath) {
    Write-Host "[3/3] Starting Test Target App on http://localhost:3000 ..." -ForegroundColor Green
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$targetPath'; Write-Host 'Test Target App running on http://localhost:3000' -ForegroundColor Green; npm run dev" -WindowStyle Normal
}

Write-Host "`n=== EvoCode V2 Suite Active ===" -ForegroundColor Cyan
Write-Host "Target App (User Feedback Widget): http://localhost:3000" -ForegroundColor White
Write-Host "EvoCode Dashboard (Triage / Build): http://localhost:3001/developer/triage" -ForegroundColor White
Write-Host "EvoCode Backend API:                http://localhost:8000" -ForegroundColor White
Write-Host "`nReady for demo! Close windows to stop servers." -ForegroundColor Gray
try { $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") } catch {}
