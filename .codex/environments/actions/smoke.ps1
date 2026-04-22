Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Resolve-Path (Join-Path $PSScriptRoot "..\lib\agentplane-action-helpers.ps1"))

$repoRoot = Resolve-AgentPlaneRepoRoot -BaseDirectory $PSScriptRoot
# Uses invoke-agentplane-windows-uv.ps1 for Windows-host uv entry.
$windowsUvHelper = Resolve-AgentPlaneWindowsUvHelper -BaseDirectory $PSScriptRoot
Invoke-AgentPlaneRoutedUv `
    -BaseDirectory $PSScriptRoot `
    -RepoRoot $repoRoot `
    -UvArgs @("python", "-m", "pytest", "tests/repository/test_docs_no_legacy_terms.py", "tests/host/test_wsl_first_docs.py", "tests/repository/test_repo_snapshot_contracts.py", "tests/onepanel/test_onepanel_plugin_and_skills.py", "tests/app/test_app_onboarding_standard.py", "-q")
