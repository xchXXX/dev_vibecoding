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
    return $manifest
}

function Load-Receipt {
    param([string]$PathValue)
    if (-not (Test-Path -LiteralPath $PathValue)) {
        return $null
    }
    $receipt = Get-Content -LiteralPath $PathValue -Raw | ConvertFrom-Json
    if ($receipt.managed_files) {
        return $receipt
    }
    if ($receipt.items) {
        $receipt | Add-Member -NotePropertyName managed_files -NotePropertyValue @()
        foreach ($item in @($receipt.items)) {
            $receipt.managed_files += [PSCustomObject]@{
                id     = $item.id
                source = $item.source
                target = $item.target
                sha256 = $null
            }
        }
        return $receipt
    }
    throw "Receipt format is invalid: $PathValue"
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
    param([object]$Summary, [string]$ReceiptPathValue)
    $payload = [PSCustomObject]@{
        operation            = 'sync'
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
$receipt = Load-Receipt -PathValue $ReceiptPath
if (-not $receipt) {
    Add-Action 'error' 'Receipt not found; run install first' $ReceiptPath
    if ($Json) {
        Write-Summary -Summary ([PSCustomObject]@{
            Added = [System.Collections.Generic.List[string]]::new()
            Updated = [System.Collections.Generic.List[string]]::new()
            Adopted = [System.Collections.Generic.List[string]]::new()
            Unchanged = [System.Collections.Generic.List[string]]::new()
            Removed = [System.Collections.Generic.List[string]]::new()
            Skipped = [System.Collections.Generic.List[string]]::new()
            SettingsInitialized = $false
        }) -ReceiptPathValue $ReceiptPath
    }
    exit 1
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

$previousManaged = @{}
foreach ($entry in @($receipt.managed_files)) {
    $previousManaged[(Normalize-RelativePath $entry.target)] = $entry
}

$manifestTargets = @{}
foreach ($item in @($manifest.items)) {
    $manifestTargets[(Normalize-RelativePath $item.target)] = $item
}

foreach ($trackedTarget in $previousManaged.Keys) {
    if ($manifestTargets.ContainsKey($trackedTarget)) {
        continue
    }
    $stalePath = Join-Path $AgentsRoot $trackedTarget
    if (-not (Test-Path -LiteralPath $stalePath)) {
        continue
    }
    if ($DryRun) {
        Add-Action 'dry_run' 'Would remove stale managed file' $stalePath
    } else {
        Remove-Item -LiteralPath $stalePath -Force
        Add-Action 'remove' 'Removed stale managed file' $stalePath
    }
    $summary.Removed.Add($trackedTarget) | Out-Null
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
    $managedEntry = [PSCustomObject]@{
        id     = $item.id
        source = $item.source
        target = $targetRelative
        sha256 = $sourceHash
    }
    $wasTracked = $previousManaged.ContainsKey($targetRelative)
    $targetExists = Test-Path -LiteralPath $targetPath

    if (-not $targetExists) {
        if ($DryRun) {
            Add-Action 'dry_run' 'Would add managed file' ("{0} -> {1}" -f $sourcePath, $targetPath)
        } else {
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
            Add-Action 'add' 'Managed file added' ("{0} -> {1}" -f $sourcePath, $targetPath)
        }
        $summary.Added.Add($targetRelative) | Out-Null
        $managedFiles.Add($managedEntry) | Out-Null
        continue
    }

    $targetHash = Get-FileSha256 -PathValue $targetPath
    if ($wasTracked) {
        if ($targetHash -eq $sourceHash) {
            Add-Action 'unchanged' 'Managed file already up to date' $targetPath
            $summary.Unchanged.Add($targetRelative) | Out-Null
            $managedFiles.Add($managedEntry) | Out-Null
            continue
        }
        if ($DryRun) {
            Add-Action 'dry_run' 'Would update managed file' ("{0} -> {1}" -f $sourcePath, $targetPath)
        } else {
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
            Add-Action 'update' 'Managed file updated' ("{0} -> {1}" -f $sourcePath, $targetPath)
        }
        $summary.Updated.Add($targetRelative) | Out-Null
        $managedFiles.Add($managedEntry) | Out-Null
        continue
    }

    if ($targetHash -eq $sourceHash) {
        Add-Action 'adopt' 'Unmanaged file matches manifest and is now managed' $targetPath
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
Write-Summary -Summary $summary -ReceiptPathValue $ReceiptPath

if ($summary.Skipped.Count -gt 0) {
    exit 1
}

exit 0
