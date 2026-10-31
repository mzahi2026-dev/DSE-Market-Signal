param(
    [ValidateRange(1,15)]
    [int]$Phase = 1
)

$ErrorActionPreference = "Stop"
Set-Location "D:\DSE-Market-Signal"

function Fail($message) {
    Write-Host "FAIL: $message" -ForegroundColor Red
    exit 1
}

function Pass($message) {
    Write-Host "PASS: $message" -ForegroundColor Green
}

$python = ".\.venv\Scripts\python.exe"
if (!(Test-Path $python)) {
    Fail "Python virtual environment missing"
}

if ($Phase -eq 1) {
    foreach ($path in @("backend", "data", "tests", "requirements.txt", "backend\main.py")) {
        if (!(Test-Path $path)) {
            Fail "Missing: $path"
        }
    }
    Pass "Project structure"

    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        Fail "Automated tests"
    }
    Pass "Automated tests"

    try {
        $health = Invoke-RestMethod "http://127.0.0.1:8000/health"
        if ($health.status -ne "ok") {
            Fail "API health is not OK"
        }
    }
    catch {
        Fail "Backend is not running on port 8000"
    }
    Pass "Backend API"

        $dbTest = @"
from backend.db import connect
con = connect()
tables = con.execute("SELECT name FROM sqlite_master WHERE type=?", ("table",)).fetchall()
assert ("prices",) in tables, "prices table not found"
con.close()
print("Database verified")
"@
    $dbTest | & $python -
    if ($LASTEXITCODE -ne 0) {
        Fail "Database verification"
    }
    Pass "Database"

    Pass "PHASE 1 AUTOMATED GATE PASSED"
    exit 0
}

if ($Phase -eq 2) {
    Write-Host "Testing live DSE collection..."

    try {
        $url = "http://127.0.0.1:8000/collect?symbol=GP&days=7"
        $result = Invoke-RestMethod -Method Post -Uri $url

        if ($result.fetched -le 0) {
            Fail "No actual DSE data fetched. Check HTTP 403."
        }

        $prices = Invoke-RestMethod "http://127.0.0.1:8000/prices?symbol=GP"
        if (@($prices.rows).Count -eq 0) {
            Fail "No market data stored in database"
        }

        Pass "Live collection and database storage"
        Write-Host "NOTE: Scheduler, backfill and duplicate tests remain pending."
        Write-Host "PHASE 2 NOT YET FULLY VERIFIED" -ForegroundColor Yellow
        exit 2
    }
    catch {
        Fail "Collection failed: $($_.Exception.Message)"
    }
}

Write-Host "Phase $Phase has no automated gate yet." -ForegroundColor Yellow
Write-Host "Implement its tests before marking it complete."
exit 2

