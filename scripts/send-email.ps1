param(
    [double]$DropThreshold = 10.0
)

. "$PSScriptRoot\_common.ps1"

Assert-EnvValue -Name 'GMAIL_APP_PASSWORD' | Out-Null
Assert-EnvValue -Name 'EMAIL_SENDER' | Out-Null
Assert-EnvValue -Name 'EMAIL_RECIPIENT' | Out-Null

Invoke-ProjectPython -Arguments @('daily_email.py', '--drop-threshold', $DropThreshold)
