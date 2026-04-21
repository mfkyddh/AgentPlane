Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-AgentPlaneRepoRoot {
    param([Parameter(Mandatory = $true)][string]$BaseDirectory)

    return (Resolve-Path (Join-Path $BaseDirectory "..\..\..")).ProviderPath
}

function Resolve-AgentPlaneWindowsUvHelper {
    param([Parameter(Mandatory = $true)][string]$BaseDirectory)

    return (Resolve-Path (Join-Path $BaseDirectory "..\lib\invoke-agentplane-windows-uv.ps1")).ProviderPath
}

function Invoke-AgentPlaneWindowsUv {
    param(
        [Parameter(Mandatory = $true)][string]$BaseDirectory,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [switch]$PreferRepoRoot,
        [Parameter(Mandatory = $true)][string[]]$UvArgs
    )

    $helper = Resolve-AgentPlaneWindowsUvHelper -BaseDirectory $BaseDirectory
    if ($PreferRepoRoot) {
        & $helper -RepoRoot $RepoRoot -PreferRepoRoot @UvArgs
    }
    else {
        & $helper -RepoRoot $RepoRoot @UvArgs
    }
    if ($LASTEXITCODE -ne 0) {
        throw "invoke-agentplane-windows-uv.ps1 failed with exit code $LASTEXITCODE."
    }
}

function Test-AgentPlaneWindowsMountedWslPath {
    param([AllowNull()][string]$PathValue)

    return -not [string]::IsNullOrWhiteSpace($PathValue) -and $PathValue -match '^/mnt/[A-Za-z]($|/)'
}

function Get-AgentPlaneLocalInspect {
    param(
        [Parameter(Mandatory = $true)][string]$BaseDirectory,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $json = Invoke-AgentPlaneWindowsUv `
        -BaseDirectory $BaseDirectory `
        -RepoRoot $RepoRoot `
        -PreferRepoRoot `
        -UvArgs @("python", "-m", "agentplane.cli", "host", "local", "inspect", "--repo-root", $RepoRoot) |
        Out-String
    return $json | ConvertFrom-Json -Depth 12
}

function Test-AgentPlanePosixPath {
    param([AllowNull()][string]$PathValue)

    return -not [string]::IsNullOrWhiteSpace($PathValue) -and $PathValue.StartsWith("/")
}

function Resolve-AgentPlaneLinuxCommandRoot {
    param([Parameter(Mandatory = $true)]$InspectPayload)

    $sourceRoot = [string]$InspectPayload.payload.workspace.source_root
    if ((Test-AgentPlanePosixPath -PathValue $sourceRoot) -and -not (Test-AgentPlaneWindowsMountedWslPath -PathValue $sourceRoot)) {
        return $sourceRoot
    }

    $backendRoot = [string]$InspectPayload.payload.linux_backend_root
    if ((Test-AgentPlanePosixPath -PathValue $backendRoot) -and -not (Test-AgentPlaneWindowsMountedWslPath -PathValue $backendRoot)) {
        return $backendRoot
    }

    throw "No separate WSL/Linux checkout was resolved for this repository. AgentPlane forbids using a Windows-mounted path such as /mnt/<drive>/... as the WSL working directory."
}

function Invoke-AgentPlaneRoutedUv {
    param(
        [Parameter(Mandatory = $true)][string]$BaseDirectory,
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)][string[]]$UvArgs
    )

    if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
        $RepoRoot = Resolve-AgentPlaneRepoRoot -BaseDirectory $BaseDirectory
    }

    if (-not $IsWindows) {
        Push-Location $RepoRoot
        try {
            & uv "run" @UvArgs
            if ($LASTEXITCODE -ne 0) {
                throw "uv run failed with exit code $LASTEXITCODE."
            }
            return
        }
        finally {
            Pop-Location
        }
    }

    Invoke-AgentPlaneWindowsUv -BaseDirectory $BaseDirectory -RepoRoot $RepoRoot -UvArgs $UvArgs | Out-Null
}
