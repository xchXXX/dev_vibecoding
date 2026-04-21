param(
    [string]$HarnessRoot,
    [string]$ManifestPath,
    [string]$SettingsTemplatePath,
    [string]$ClaudeHome,
    [switch]$DryRun,
    [switch]$Json,
    [switch]$ForceTakeover
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $HarnessRoot) {
    $HarnessRoot = Split-Path -Parent $ScriptRoot
}

function Normalize-UserPath {
    param([string]$PathValue)
    if (-not $PathValue) {
        return $null
    }
    $expanded = [Environment]::ExpandEnvironmentVariables($PathValue)
    if ($expanded.StartsWith("~")) {
        $tail = $expanded.Substring(1).TrimStart("\", "/")
        $expanded = Join-Path $env:USERPROFILE $tail
    }
    return [System.IO.Path]::GetFullPath($expanded)
}

$HarnessRoot = Normalize-UserPath $HarnessRoot
if (-not (Test-Path -LiteralPath $HarnessRoot)) {
    throw "Harness root not found: $HarnessRoot"
}

if (-not $ManifestPath) {
    $ManifestPath = Join-Path $HarnessRoot "hooks/claude/manifest.json"
}
$ManifestPath = Normalize-UserPath $ManifestPath
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

if (-not $SettingsTemplatePath) {
    $SettingsTemplatePath = Join-Path $HarnessRoot "hooks/claude/settings.json"
}
$SettingsTemplatePath = Normalize-UserPath $SettingsTemplatePath
if (-not (Test-Path -LiteralPath $SettingsTemplatePath)) {
    throw "Settings template not found: $SettingsTemplatePath"
}

if (-not $ClaudeHome) {
    $ClaudeHome = Join-Path $env:USERPROFILE ".claude"
}
$ClaudeHome = Normalize-UserPath $ClaudeHome

$syncScript = Join-Path $ScriptRoot "sync-claude-hooks.ps1"
if (-not (Test-Path -LiteralPath $syncScript)) {
    throw "Sync script not found: $syncScript"
}

$syncParams = @{
    HarnessRoot        = $HarnessRoot
    ManifestPath       = $ManifestPath
    SettingsTemplatePath = $SettingsTemplatePath
    ClaudeHome         = $ClaudeHome
    AllowBootstrap     = $true
}
if ($DryRun) { $syncParams.DryRun = $true }
if ($Json) { $syncParams.Json = $true }
if ($ForceTakeover) { $syncParams.ForceTakeover = $true }

& $syncScript @syncParams
exit $LASTEXITCODE
