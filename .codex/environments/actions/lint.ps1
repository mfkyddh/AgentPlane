Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Resolve-Path (Join-Path $PSScriptRoot "..\lib\agentplane-action-helpers.ps1"))

$repoRoot = Resolve-AgentPlaneRepoRoot -BaseDirectory $PSScriptRoot
# Uses invoke-agentplane-windows-uv.ps1 for Windows-host uv entry.
$windowsUvHelper = Resolve-AgentPlaneWindowsUvHelper -BaseDirectory $PSScriptRoot
Invoke-AgentPlaneRoutedUv `
    -BaseDirectory $PSScriptRoot `
    -RepoRoot $repoRoot `
    -UvArgs @("python", "-m", "compileall", "agentplane", "tests")
