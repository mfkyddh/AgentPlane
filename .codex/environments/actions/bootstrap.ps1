Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$setupScript = if ($IsWindows) {
    Resolve-Path (Join-Path $PSScriptRoot "..\setup\setup.windows.ps1")
}
else {
    Resolve-Path (Join-Path $PSScriptRoot "..\setup\setup.linux.sh")
}

if ($IsWindows) {
    & $setupScript
}
else {
    & bash $setupScript
}
exit $LASTEXITCODE
