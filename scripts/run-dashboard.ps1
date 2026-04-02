. "$PSScriptRoot\_common.ps1"

$projectRoot = Get-ProjectRoot
$pythonPath = Get-ProjectPython
$stdoutPath = Join-Path $projectRoot 'dashboard_stdout.log'
$stderrPath = Join-Path $projectRoot 'dashboard_stderr.log'

$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
$env:STREAMLIT_SERVER_HEADLESS = 'true'

Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @(
        '-m',
        'streamlit',
        'run',
        'dashboard.py',
        '--server.headless',
        'true',
        '--browser.gatherUsageStats',
        'false'
    ) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath
