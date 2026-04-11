$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$windowsControlRoot = "D:\Projects\AgentPlane"
$windowsUvHelper = Resolve-Path (Join-Path $PSScriptRoot "..\lib\invoke-agentplane-windows-uv.ps1")
$formalCli = "pwsh -NoProfile -ExecutionPolicy Bypass -File $windowsUvHelper python -m agentplane.cli host local inspect --repo-root D:\Projects\AgentPlane"
$uvProjectEnvironment = Join-Path $env:LOCALAPPDATA "AgentPlane\uv\AgentPlane"
$wsl = Get-Command wsl.exe -ErrorAction Stop
$backendProbe = & $wsl.Source -e bash -lc "if [ -d /root/work/AgentPlane ]; then printf '/root/work/AgentPlane'; else pwd; fi"
if ($LASTEXITCODE -ne 0) {
    throw "WSL backend probe failed."
}

Write-Host "Repo root: $repoRoot"
Write-Host "Windows control root: $windowsControlRoot"
Write-Host "Windows control root exists: $(Test-Path -LiteralPath $windowsControlRoot)"
Write-Host "Linux backend: WSL"
Write-Host "WSL backend probe root: $backendProbe"
Write-Host "Formal local CLI: $formalCli"
Write-Host "UNC-safe UV_PROJECT_ENVIRONMENT: $uvProjectEnvironment"
Write-Host "Windows uv wrapper: $windowsUvHelper"
