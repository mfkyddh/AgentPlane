Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Resolve-Path (Join-Path $PSScriptRoot "..\lib\agentplane-action-helpers.ps1"))

$repoRoot = Resolve-AgentPlaneRepoRoot -BaseDirectory $PSScriptRoot
if (-not $IsWindows) {
    & bash (Resolve-Path (Join-Path $PSScriptRoot "compose-logs.sh"))
    exit $LASTEXITCODE
}

$inspect = Get-AgentPlaneLocalInspect -BaseDirectory $PSScriptRoot -RepoRoot $repoRoot
$linuxRoot = Resolve-AgentPlaneLinuxCommandRoot -InspectPayload $inspect
$linuxScript = "$linuxRoot/.codex/environments/actions/compose-logs.sh"

& wsl.exe -e env -C $linuxRoot bash $linuxScript
exit $LASTEXITCODE
