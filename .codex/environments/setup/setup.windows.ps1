Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).ProviderPath
$windowsControlRoot = $repoRoot
$windowsUvHelper = (Resolve-Path (Join-Path $PSScriptRoot "..\lib\invoke-agentplane-windows-uv.ps1")).ProviderPath
$formalCli = "pwsh -NoProfile -ExecutionPolicy Bypass -File $windowsUvHelper -RepoRoot $repoRoot -PreferRepoRoot python -m agentplane.cli host local inspect --repo-root $repoRoot"
$uvProjectEnvironment = Join-Path $env:LOCALAPPDATA "AgentPlane\uv\$(Split-Path -Leaf $repoRoot)"
$wsl = Get-Command wsl.exe -ErrorAction Stop
$backendProbe = & $wsl.Source -e pwd
if ($LASTEXITCODE -ne 0) {
    throw "WSL backend probe failed."
}

Write-Host "Repo root: $repoRoot"
Write-Host "Windows control root: $windowsControlRoot"
Write-Host "Windows control root exists: $(Test-Path -LiteralPath $windowsControlRoot)"
Write-Host "Windows host entry shell: pwsh"
Write-Host "Linux backend: WSL"
Write-Host "WSL backend probe root: $backendProbe"
Write-Host "Formal local CLI: $formalCli"
Write-Host "UNC-safe UV_PROJECT_ENVIRONMENT: $uvProjectEnvironment"
Write-Host "Windows uv wrapper: $windowsUvHelper"
Write-Host "Linux-only actions should route through WSL backend."
