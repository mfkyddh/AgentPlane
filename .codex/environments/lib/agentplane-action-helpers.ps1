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
    if (Test-AgentPlanePosixPath -PathValue $sourceRoot) {
        return $sourceRoot
    }

    $backendRoot = [string]$InspectPayload.payload.linux_backend_root
    if (Test-AgentPlanePosixPath -PathValue $backendRoot) {
        return $backendRoot
    }

    throw "No WSL/Linux command root was resolved for the current repository."
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

    $inspect = Get-AgentPlaneLocalInspect -BaseDirectory $BaseDirectory -RepoRoot $RepoRoot
    $sourceRoot = [string]$inspect.payload.workspace.source_root
    if (Test-AgentPlanePosixPath -PathValue $sourceRoot) {
        $wslUvEnv = "$sourceRoot/.venv-wsl"
        & wsl.exe -e env "UV_PROJECT_ENVIRONMENT=$wslUvEnv" -C $sourceRoot uv "run" @UvArgs
        if ($LASTEXITCODE -ne 0) {
            throw "WSL uv run failed with exit code $LASTEXITCODE."
        }
        return
    }

    Invoke-AgentPlaneWindowsUv -BaseDirectory $BaseDirectory -RepoRoot $RepoRoot -UvArgs $UvArgs | Out-Null
}
