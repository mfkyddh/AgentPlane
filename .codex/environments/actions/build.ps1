Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Resolve-Path (Join-Path $PSScriptRoot "..\lib\agentplane-action-helpers.ps1"))

$repoRoot = Resolve-AgentPlaneRepoRoot -BaseDirectory $PSScriptRoot
Invoke-AgentPlaneRoutedUv `
    -BaseDirectory $PSScriptRoot `
    -RepoRoot $repoRoot `
    -UvArgs @("build")
