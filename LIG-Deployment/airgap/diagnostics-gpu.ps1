$ErrorActionPreference = "Stop"
$previousDevice = $env:DEVICE
$previousProfiles = $env:COMPOSE_PROFILES
$previousWorkers = $env:TASK_EXECUTOR_WORKERS
try {
    $env:DEVICE = "gpu"
    $env:COMPOSE_PROFILES = "infinity,gpu"
    $env:TASK_EXECUTOR_WORKERS = "1"
    & (Join-Path $PSScriptRoot "LIG-Deployment\lig-ragflow.ps1") diagnostics
}
finally {
    if ($null -eq $previousDevice) { Remove-Item Env:DEVICE -ErrorAction SilentlyContinue } else { $env:DEVICE = $previousDevice }
    if ($null -eq $previousProfiles) { Remove-Item Env:COMPOSE_PROFILES -ErrorAction SilentlyContinue } else { $env:COMPOSE_PROFILES = $previousProfiles }
    if ($null -eq $previousWorkers) { Remove-Item Env:TASK_EXECUTOR_WORKERS -ErrorAction SilentlyContinue } else { $env:TASK_EXECUTOR_WORKERS = $previousWorkers }
}
