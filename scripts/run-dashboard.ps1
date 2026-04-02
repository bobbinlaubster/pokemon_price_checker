. "$PSScriptRoot\_common.ps1"

$projectRoot = Get-ProjectRoot
$pythonPath = Get-ProjectPython
Push-Location $projectRoot
try {
    & $pythonPath -m streamlit run dashboard.py --browser.gatherUsageStats false
    if ($LASTEXITCODE -ne 0) {
        throw "Dashboard launch failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
