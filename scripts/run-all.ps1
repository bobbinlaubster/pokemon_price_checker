param(
    [int]$MaxProducts = 5,
    [double]$DropThreshold = 10.0,
    [switch]$SkipEmail,
    [switch]$OpenDashboard
)

. "$PSScriptRoot\_common.ps1"

& "$PSScriptRoot\run-scrape.ps1" -MaxProducts $MaxProducts
if ($LASTEXITCODE -ne 0) {
    throw "Scrape step failed."
}

if (-not $SkipEmail) {
    & "$PSScriptRoot\send-email.ps1" -DropThreshold $DropThreshold
    if ($LASTEXITCODE -ne 0) {
        throw "Email step failed."
    }
}

if ($OpenDashboard) {
    & "$PSScriptRoot\run-dashboard.ps1"
}
