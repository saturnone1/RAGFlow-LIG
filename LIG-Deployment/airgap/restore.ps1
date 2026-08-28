param(
    [Parameter(Mandatory)][string]$Source,
    [switch]$ConfirmRestore,
    [switch]$RestoreConfiguration,
    [switch]$LeaveStopped
)
& (Join-Path $PSScriptRoot "LIG-Deployment\restore-ragflow.ps1") -Source $Source -ConfirmRestore:$ConfirmRestore -RestoreConfiguration:$RestoreConfiguration -LeaveStopped:$LeaveStopped
