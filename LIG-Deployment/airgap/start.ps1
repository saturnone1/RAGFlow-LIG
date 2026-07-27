$ErrorActionPreference = "Stop"
$previousProfiles = $env:COMPOSE_PROFILES
try {
    $profiles = "infinity,cpu"
    $env:COMPOSE_PROFILES = $profiles
    & (Join-Path $PSScriptRoot "LIG-Deployment\lig-ragflow.ps1") start
}
finally {
    if ($null -eq $previousProfiles) { Remove-Item Env:COMPOSE_PROFILES -ErrorAction SilentlyContinue } else { $env:COMPOSE_PROFILES = $previousProfiles }
}
