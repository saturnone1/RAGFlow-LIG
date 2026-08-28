param([string]$Destination, [switch]$LeaveStopped)
$arguments = @{}
if ($Destination) { $arguments.Destination = $Destination }
if ($LeaveStopped) { $arguments.LeaveStopped = $true }
& (Join-Path $PSScriptRoot "LIG-Deployment\backup-ragflow.ps1") @arguments
