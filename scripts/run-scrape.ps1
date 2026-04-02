param(
    [int]$MaxProducts = 5,
    [switch]$DryRun
)

. "$PSScriptRoot\_common.ps1"

$args = @('price_checker.py', '--max-products', $MaxProducts)
if ($DryRun) {
    $args += '--dry-run'
}

Invoke-ProjectPython -Arguments $args
