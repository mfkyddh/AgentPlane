[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$RepoRoot,
    [switch]$PreferRepoRoot,
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$UvArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).ProviderPath
}

$effectiveRoot = (Resolve-Path $RepoRoot).ProviderPath

$uv = Get-Command uv -ErrorAction Stop

Push-Location $effectiveRoot
try {
    & $uv.Source "run" @UvArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
