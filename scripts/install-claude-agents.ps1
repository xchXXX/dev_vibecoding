param(
    [string]$HarnessRoot,
    [string]$ManifestPath,
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
    if ($expanded.StartsWith('~')) {
        $tail = $expanded.Substring(1).TrimStart('\', '/')
        $expanded = Join-Path $env:USERPROFILE $tail
    }
    return [System.IO.Path]::GetFullPath($expanded)
}

function Normalize-RelativePath {
    param([string]$PathValue)
    if (-not $PathValue) {
        return ''
    }
    return ($PathValue -replace '/', '\').TrimStart('\', '/')
}

function Get-FileSha256 {
    param([string]$PathValue)
    return (Get-FileHash -LiteralPath $PathValue -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Ensure-Directory {
    param([string]$PathValue, [string]$Description)
    if (Test-Path -LiteralPath $PathValue) {
        return
    }
    if ($DryRun) {
        Add-Action 'dry_run' "Would create $Description" $PathValue
        return
    }
    New-Item -ItemType Directory -Path $PathValue -Force | Out-Null
    Add-Action 'create' "$Description created" $PathValue
}

function Add-Action {
    param(
        [string]$Type,
        [string]$Message,
        [string]$Details = ''
    )
    $script:ActionLog.Add([PSCustomObject]@{
        timestamp = (Get-Date).ToString('o')
        type      = $Type
        message   = $Message
        details   = $Details
    }) | Out-Null
    if (-not $Json) {
        Write-Host ("[{0}] {1}" -f $Type, $Message)
        if ($Details) {
            Write-Host ("  {0}" -f $Details)
        }
    }
}

function Load-Manifest {
    param([string]$PathValue)
    $manifest = Get-Content -LiteralPath $PathValue -Raw | ConvertFrom-Json
    if (-not $manifest.schema_version) { throw "Manifest missing schema_version: $PathValue" }
    if (-not $manifest.runtime) { throw "Manifest missing runtime: $PathValue" }
    if (-not $manifest.items -or @($manifest.items).Count -eq 0) { throw "Manifest has no items: $PathValue" }

    $seenIds = [System.Collections.Generic.HashSet[string]]::new()
    $seenTargets = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($item in @($manifest.items)) {
        if (-not $item.id) { throw "Manifest item missing id" }
        if (-not $item.source) { throw "Manifest item $($item.id) missing source" }
        if (-not $item.target) { throw "Manifest item $($item.id) missing target" }
        $normalizedTarget = Normalize-RelativePath $item.target
        if (-not $seenIds.Add([string]$item.id)) {
            throw "Manifest duplicate id: $($item.id)"
        }
        if (-not $seenTargets.Add($normalizedTarget)) {
            throw "Manifest duplicate target: $normalizedTarget"
        }
    }
    return $manifest
}

function Write-Receipt {
    param(
        [object[]]$ManagedFiles,
        [object]$Manifest,
        [string]$ReceiptPathValue,
        [string]$ReceiptDirValue
    )
    $payload = [PSCustomObject]@{
        schema_version = '1.0'
        harness_root   = $HarnessRoot
        manifest       = [PSCustomObject]@{
            path           = $ManifestPath
            schema_version = $Manifest.schema_version
            runtime        = $Manifest.runtime
            last_sync      = (Get-Date).ToString('o')
        }
        managed_files  = $ManagedFiles
    }
    if ($DryRun) {
        Add-Action 'dry_run' 'Would write receipt' $ReceiptPathValue
        return $false
    }
    Ensure-Directory -PathValue $ReceiptDirValue -Description 'receipt directory'
    $payload | ConvertTo-Json | Set-Content -LiteralPath $ReceiptPathValue -Encoding UTF8
    Add-Action 'write' 'Receipt written' $ReceiptPathValue
    return $true
}

function Write-Summary {
    param([string]$Operation, [object]$Summary, [string]$ReceiptPathValue)
    $payload = [PSCustomObject]@{
        operation            = $Operation
        dry_run              = $DryRun.IsPresent
        json_output          = $Json.IsPresent
        force_takeover       = $ForceTakeover.IsPresent
        added                = $Summary.Added
        updated              = $Summary.Updated
        adopted              = $Summary.Adopted
        unchanged            = $Summary.Unchanged
        removed              = $Summary.Removed
        skipped_conflicts    = $Summary.Skipped
        settings_initialized = $Summary.SettingsInitialized
        receipt_path         = $ReceiptPathValue
        actions              = $script:ActionLog
    }
    if ($Json) {
        $payload | ConvertTo-Json
        return
    }
    Write-Host "Summary:"
    Write-Host ("  Added: {0}" -f $Summary.Added.Count)
    Write-Host ("  Updated: {0}" -f $Summary.Updated.Count)
    Write-Host ("  Adopted: {0}" -f $Summary.Adopted.Count)
    Write-Host ("  Unchanged: {0}" -f $Summary.Unchanged.Count)
    Write-Host ("  Removed: {0}" -f $Summary.Removed.Count)
    Write-Host ("  Skipped conflicts: {0}" -f $Summary.Skipped.Count)
    if ($Summary.SettingsInitialized) {
        Write-Host "  settings.json initialized"
    }
    Write-Host ("  ReceiptPath = {0}" -f $ReceiptPathValue)
}

$script:ActionLog = [System.Collections.Generic.List[object]]::new()
$HarnessRoot = Normalize-UserPath $HarnessRoot
if (-not (Test-Path -LiteralPath $HarnessRoot)) {
    throw "Harness root not found: $HarnessRoot"
}

if (-not $ManifestPath) {
    $ManifestPath = Join-Path $HarnessRoot 'agents/manifest.json'
}
$ManifestPath = Normalize-UserPath $ManifestPath
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

if (-not $ClaudeHome) {
    $ClaudeHome = Join-Path $env:USERPROFILE '.claude'
}
$ClaudeHome = Normalize-UserPath $ClaudeHome

$AgentsRoot = Join-Path $ClaudeHome 'agents'
$ReceiptDir = Join-Path $ClaudeHome '.ai-harness'
$ReceiptPath = Join-Path $ReceiptDir 'claude-agents.receipt.json'
$SettingsPath = Join-Path $ClaudeHome 'settings.json'

$manifest = Load-Manifest -PathValue $ManifestPath
Add-Action 'info' ("Manifest loaded (schema {0})" -f $manifest.schema_version) $ManifestPath

if (Test-Path -LiteralPath $ReceiptPath) {
    Add-Action 'info' 'Receipt exists; install delegates to sync' $ReceiptPath
    $syncScript = Join-Path $ScriptRoot 'sync-claude-agents.ps1'
    $syncParams = @{
        HarnessRoot  = $HarnessRoot
        ManifestPath = $ManifestPath
        ClaudeHome   = $ClaudeHome
    }
    if ($DryRun) { $syncParams.DryRun = $true }
    if ($Json) { $syncParams.Json = $true }
    if ($ForceTakeover) { $syncParams.ForceTakeover = $true }
    & $syncScript @syncParams
    exit $LASTEXITCODE
}

Ensure-Directory -PathValue $ClaudeHome -Description 'Claude home'
Ensure-Directory -PathValue $AgentsRoot -Description 'Claude agents directory'
Ensure-Directory -PathValue $ReceiptDir -Description 'receipt directory'

$summary = [PSCustomObject]@{
    Added = [System.Collections.Generic.List[string]]::new()
    Updated = [System.Collections.Generic.List[string]]::new()
    Adopted = [System.Collections.Generic.List[string]]::new()
    Unchanged = [System.Collections.Generic.List[string]]::new()
    Removed = [System.Collections.Generic.List[string]]::new()
    Skipped = [System.Collections.Generic.List[string]]::new()
    SettingsInitialized = $false
}

if (-not (Test-Path -LiteralPath $SettingsPath)) {
    if ($DryRun) {
        Add-Action 'dry_run' 'Would initialize settings.json' $SettingsPath
    } else {
        '{}' | Set-Content -LiteralPath $SettingsPath -Encoding UTF8
        Add-Action 'create' 'settings.json initialized' $SettingsPath
    }
    $summary.SettingsInitialized = $true
}

$managedFiles = [System.Collections.Generic.List[object]]::new()
foreach ($item in @($manifest.items)) {
    $sourcePath = Join-Path $HarnessRoot $item.source
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        throw "Manifest source missing: $sourcePath"
    }
    $targetRelative = Normalize-RelativePath $item.target
    $targetPath = Join-Path $AgentsRoot $targetRelative
    $targetDir = Split-Path -Parent $targetPath
    if ($targetDir) {
        Ensure-Directory -PathValue $targetDir -Description ("target directory for {0}" -f $targetRelative)
    }

    $sourceHash = Get-FileSha256 -PathValue $sourcePath
    $targetExists = Test-Path -LiteralPath $targetPath
    $managedEntry = [PSCustomObject]@{
        id     = $item.id
        source = $item.source
        target = $targetRelative
        sha256 = $sourceHash
    }

    if (-not $targetExists) {
        if ($DryRun) {
            Add-Action 'dry_run' 'Would add managed file' ("{0} -> {1}" -f $sourcePath, $targetPath)
        } else {
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
            Add-Action 'add' 'Managed file installed' ("{0} -> {1}" -f $sourcePath, $targetPath)
        }
        $summary.Added.Add($targetRelative) | Out-Null
        $managedFiles.Add($managedEntry) | Out-Null
        continue
    }

    $targetHash = Get-FileSha256 -PathValue $targetPath
    if ($targetHash -eq $sourceHash) {
        Add-Action 'adopt' 'Existing file matches manifest and is now managed' $targetPath
        $summary.Adopted.Add($targetRelative) | Out-Null
        $managedFiles.Add($managedEntry) | Out-Null
        continue
    }

    if (-not $ForceTakeover) {
        Add-Action 'conflict' 'Unmanaged conflicting file skipped' $targetPath
        $summary.Skipped.Add($targetRelative) | Out-Null
        continue
    }

    if ($DryRun) {
        Add-Action 'dry_run' 'Would take over conflicting file' ("{0} -> {1}" -f $sourcePath, $targetPath)
    } else {
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
        Add-Action 'force_takeover' 'Conflicting file taken over' ("{0} -> {1}" -f $sourcePath, $targetPath)
    }
    $summary.Adopted.Add($targetRelative) | Out-Null
    $managedFiles.Add($managedEntry) | Out-Null
}

[void](Write-Receipt -ManagedFiles $managedFiles -Manifest $manifest -ReceiptPathValue $ReceiptPath -ReceiptDirValue $ReceiptDir)
Write-Summary -Operation 'install' -Summary $summary -ReceiptPathValue $ReceiptPath

if ($summary.Skipped.Count -gt 0) {
    exit 1
}

exit 0
