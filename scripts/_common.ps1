Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Get-ProjectPython {
    $projectRoot = Get-ProjectRoot
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $pythonPath)) {
        throw "Project virtualenv python not found at $pythonPath"
    }
    return $pythonPath
}

function Assert-EnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, 'User')
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, 'Machine')
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Required environment variable '$Name' is not set."
    }
    return $value
}

function Invoke-ProjectPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $projectRoot = Get-ProjectRoot
    $pythonPath = Get-ProjectPython
    Push-Location $projectRoot
    try {
        & $pythonPath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Python command failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
