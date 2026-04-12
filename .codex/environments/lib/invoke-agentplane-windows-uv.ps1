[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$RepoRoot,
    [string]$WindowsControlRoot,
    [string]$UvProjectEnvironment,
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

function Resolve-DefaultUvProjectEnvironment {
    param([Parameter(Mandatory = $true)][string]$RootPath)

    $base = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($base)) {
        $base = $env:TEMP
    }
    if ([string]::IsNullOrWhiteSpace($base)) {
        throw "LOCALAPPDATA/TEMP is unavailable; cannot place UV_PROJECT_ENVIRONMENT on a Windows-local path."
    }

    $projectName = Split-Path -Leaf $RootPath
    if ([string]::IsNullOrWhiteSpace($projectName)) {
        $projectName = "agentplane"
    }
    return Join-Path $base "AgentPlane\uv\$projectName"
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).ProviderPath
}

$effectiveRoot = (Resolve-Path $RepoRoot).ProviderPath
$hasWindowsControlRoot = -not [string]::IsNullOrWhiteSpace($WindowsControlRoot)
if (
    -not $PreferRepoRoot -and
    $hasWindowsControlRoot -and
    (Test-Path -LiteralPath $WindowsControlRoot) -and
    (Test-Path -LiteralPath (Join-Path $WindowsControlRoot "pyproject.toml"))
) {
    $effectiveRoot = (Resolve-Path $WindowsControlRoot).ProviderPath
}

if ([string]::IsNullOrWhiteSpace($UvProjectEnvironment) -and ($IsWindows -or (Test-IsWslUncPath $effectiveRoot))) {
    $projectEnvironmentRoot = if ($hasWindowsControlRoot) {
        $WindowsControlRoot
    }
    else {
        $effectiveRoot
    }
    $UvProjectEnvironment = Resolve-DefaultUvProjectEnvironment -RootPath $projectEnvironmentRoot
}

if (-not [string]::IsNullOrWhiteSpace($UvProjectEnvironment)) {
    $null = New-Item -ItemType Directory -Force -Path $UvProjectEnvironment
    $env:UV_PROJECT_ENVIRONMENT = $UvProjectEnvironment
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
