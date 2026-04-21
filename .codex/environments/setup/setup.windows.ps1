Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).ProviderPath
$windowsUvHelper = (Resolve-Path (Join-Path $PSScriptRoot "..\lib\invoke-agentplane-windows-uv.ps1")).ProviderPath
$formalCli = "pwsh -NoProfile -ExecutionPolicy Bypass -File $windowsUvHelper -RepoRoot $repoRoot -PreferRepoRoot python -m agentplane.cli host local inspect --repo-root $repoRoot"
$wsl = Get-Command wsl.exe -ErrorAction Stop
$backendProbe = & $wsl.Source -e pwd
if ($LASTEXITCODE -ne 0) {
    throw "WSL backend probe failed."
}

Write-Host "Repo root: $repoRoot"
Write-Host "Repo root exists: $(Test-Path -LiteralPath $repoRoot)"
Write-Host "Windows host entry shell: pwsh"
Write-Host "Linux backend: WSL"
Write-Host "WSL backend probe root: $backendProbe"
Write-Host "Formal local CLI: $formalCli"
Write-Host "Windows uv wrapper: $windowsUvHelper"
Write-Host "Workspace policy: Windows and WSL must use separate checkouts; this checkout owns .venv."
Write-Host "Linux-only actions should route through WSL backend without using a Windows-mounted repo as cwd."
