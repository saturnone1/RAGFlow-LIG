$ErrorActionPreference = "Stop"
$previousDevice = $env:DEVICE
$previousProfiles = $env:COMPOSE_PROFILES
try {
    $env:DEVICE = "gpu"
    $env:COMPOSE_PROFILES = "infinity,gpu"
    & (Join-Path $PSScriptRoot "LIG-Deployment\lig-ragflow.ps1") diagnostics
}
finally {
    if ($null -eq $previousDevice) { Remove-Item Env:DEVICE -ErrorAction SilentlyContinue } else { $env:DEVICE = $previousDevice }
    if ($null -eq $previousProfiles) { Remove-Item Env:COMPOSE_PROFILES -ErrorAction SilentlyContinue } else { $env:COMPOSE_PROFILES = $previousProfiles }
}
