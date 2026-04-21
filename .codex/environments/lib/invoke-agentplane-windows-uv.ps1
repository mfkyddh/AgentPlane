[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$RepoRoot,
    [switch]$PreferRepoRoot,
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$UvArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IsWslUncPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $normalized = $Path.Replace("/", "\").ToLowerInvariant()
    return $normalized.StartsWith("\\wsl.localhost\") -or $normalized.StartsWith("\\wsl$\")
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).ProviderPath
}

$effectiveRoot = (Resolve-Path $RepoRoot).ProviderPath
if (Test-IsWslUncPath $effectiveRoot) {
    throw "AgentPlane forbids running the Windows uv entry from a WSL UNC checkout: $effectiveRoot. Use a Windows-local checkout with its single .venv, or run from a separate Linux-filesystem checkout inside WSL."
}

$uv = Get-Command uv -ErrorAction Stop

Push-Location $effectiveRoot
try {
    & $uv.Source "run" @UvArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
