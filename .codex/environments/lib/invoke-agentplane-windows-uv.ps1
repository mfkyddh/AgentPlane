[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$RepoRoot,
    [string]$WindowsControlRoot = "D:\Projects\AgentPlane",
    [string]$UvProjectEnvironment,
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$UvArgs
)

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
if (
    (Test-Path -LiteralPath $WindowsControlRoot) -and
    (Test-Path -LiteralPath (Join-Path $WindowsControlRoot "pyproject.toml"))
) {
    $effectiveRoot = (Resolve-Path $WindowsControlRoot).ProviderPath
}

if (Test-IsWslUncPath $effectiveRoot) {
    if ([string]::IsNullOrWhiteSpace($UvProjectEnvironment)) {
        $UvProjectEnvironment = Resolve-DefaultUvProjectEnvironment -RootPath $WindowsControlRoot
    }
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
