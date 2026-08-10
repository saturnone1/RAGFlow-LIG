$ErrorActionPreference = "Stop"
$previousDevice = $env:DEVICE
$previousProfiles = $env:COMPOSE_PROFILES
try {
    $env:DEVICE = "gpu"
    $profiles = "infinity,gpu"
    $env:COMPOSE_PROFILES = $profiles
    & (Join-Path $PSScriptRoot "LIG-Deployment\lig-ragflow.ps1") start
}
finally {
    if ($null -eq $previousDevice) { Remove-Item Env:DEVICE -ErrorAction SilentlyContinue } else { $env:DEVICE = $previousDevice }
    if ($null -eq $previousProfiles) { Remove-Item Env:COMPOSE_PROFILES -ErrorAction SilentlyContinue } else { $env:COMPOSE_PROFILES = $previousProfiles }
}
