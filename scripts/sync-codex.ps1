param(
    [string]$HarnessRoot,
    [string]$CodexHome,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$ManagedSkillContracts = @(
    [ordered]@{
        name = "global-task-orchestrator"
        source_dir = "skills\global-task-orchestrator"
        source_label = "skills/global-task-orchestrator"
    },
    [ordered]@{
        name = "command-failure-memory"
        source_dir = "skills\command-failure-memory"
        source_label = "skills/command-failure-memory"
    },
    [ordered]@{
        name = "pre-dev-benchmark"
        source_dir = "skills\pre-dev-benchmark"
        source_label = "skills/pre-dev-benchmark"
    }
)
$ManagedSkillNames = @($ManagedSkillContracts | ForEach-Object { [string]$_["name"] })
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
        $expanded = Join-Path $env:USERPROFILE $expanded.Substring(1).TrimStart("\", "/")
    }
    return [System.IO.Path]::GetFullPath($expanded)
}

function ConvertTo-NormalizedMap {
    param([object]$InputObject)
    if ($null -eq $InputObject) { return $null }
    if ($InputObject -is [System.Collections.IDictionary]) {
        $map = [ordered]@{}
        foreach ($key in $InputObject.Keys) {
            $map[$key] = ConvertTo-NormalizedMap -InputObject $InputObject[$key]
        }
        return $map
    }
    if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
        $items = @()
        foreach ($item in $InputObject) {
            $items += ,(ConvertTo-NormalizedMap -InputObject $item)
        }
        return $items
    }
    if ($InputObject -is [pscustomobject]) {
        $map = [ordered]@{}
        foreach ($prop in $InputObject.PSObject.Properties) {
            $map[$prop.Name] = ConvertTo-NormalizedMap -InputObject $prop.Value
        }
        return $map
    }
    return $InputObject
}

function Read-JsonMap {
    param([string]$PathValue)
    if (-not (Test-Path -LiteralPath $PathValue)) {
        return $null
    }
    $raw = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [ordered]@{}
    }
    if (-not $raw.TrimStart().StartsWith("{")) {
        throw ("json_root_not_object: {0}" -f $PathValue)
    }
    $parsed = ConvertTo-NormalizedMap -InputObject ($raw | ConvertFrom-Json)
    if ($null -eq $parsed) {
        return [ordered]@{}
    }
    if (-not ($parsed -is [System.Collections.IDictionary])) {
        throw ("json_root_not_object: {0}" -f $PathValue)
    }
    return $parsed
}

function Write-JsonFile {
    param([string]$PathValue, [object]$Data)
    Set-Content -LiteralPath $PathValue -Value ($Data | ConvertTo-Json -Depth 64) -Encoding UTF8
}

function Get-StringSha256 {
    param([string]$Content)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
    $hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    return ([System.BitConverter]::ToString($hash).Replace("-", "").ToLowerInvariant())
}

function Get-CompressedJson {
    param([object]$Data)
    return ($Data | ConvertTo-Json -Depth 64 -Compress)
}

$script:SyncLockTimeoutMs = 60000

function Get-SyncLockName {
    param([string]$CodexHomeValue)
    $lockIdentity = Normalize-UserPath -PathValue $CodexHomeValue
    if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
        $lockIdentity = $lockIdentity.ToLowerInvariant()
    }
    return ("Local\AiHarness.CodexSync.{0}" -f (Get-StringSha256 -Content $lockIdentity).Substring(0, 24))
}

function Invoke-WithSyncLock {
    param(
        [string]$CodexHomeValue,
        [scriptblock]$ScriptBlock
    )
    $mutex = New-Object System.Threading.Mutex($false, (Get-SyncLockName -CodexHomeValue $CodexHomeValue))
    $lockAcquired = $false
    try {
        try {
            $lockAcquired = $mutex.WaitOne($script:SyncLockTimeoutMs)
        } catch [System.Threading.AbandonedMutexException] {
            $lockAcquired = $true
        }
        if (-not $lockAcquired) {
            throw ("timed out waiting for codex sync lock after {0} ms." -f $script:SyncLockTimeoutMs)
        }
        return (& $ScriptBlock)
    } finally {
        if ($lockAcquired) {
            try {
                $mutex.ReleaseMutex()
            } catch {
            }
        }
        $mutex.Dispose()
    }
}

$script:PathNativeAvailable = $false
$script:PathNativeFailureReason = ""
$script:WindowsPathSafetyRequired = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
if ($script:WindowsPathSafetyRequired -and ($env:AI_HARNESS_DISABLE_NATIVE_PATH -eq "1")) {
    $script:PathNativeAvailable = $false
    $script:PathNativeFailureReason = "disabled by AI_HARNESS_DISABLE_NATIVE_PATH"
} elseif (-not ("AiHarness.PathNative" -as [type])) {
    try {
        Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace AiHarness {
    public static class PathNative {
        private const uint FILE_SHARE_READ = 0x00000001;
        private const uint FILE_SHARE_WRITE = 0x00000002;
        private const uint FILE_SHARE_DELETE = 0x00000004;
        private const uint OPEN_EXISTING = 3;
        private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafeFileHandle CreateFileW(
            string lpFileName,
            uint dwDesiredAccess,
            uint dwShareMode,
            IntPtr lpSecurityAttributes,
            uint dwCreationDisposition,
            uint dwFlagsAndAttributes,
            IntPtr hTemplateFile);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetFinalPathNameByHandleW(
            SafeFileHandle hFile,
            StringBuilder lpszFilePath,
            uint cchFilePath,
            uint dwFlags);

        public static string GetFinalPath(string path) {
            using (SafeFileHandle handle = CreateFileW(
                path,
                0,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                IntPtr.Zero,
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS,
                IntPtr.Zero)) {
                if (handle.IsInvalid) {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateFileW failed for " + path);
                }

                StringBuilder buffer = new StringBuilder(1024);
                uint result = GetFinalPathNameByHandleW(handle, buffer, (uint)buffer.Capacity, 0);
                if (result == 0) {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "GetFinalPathNameByHandleW failed for " + path);
                }
                if (result >= buffer.Capacity) {
                    buffer = new StringBuilder((int)result + 1);
                    result = GetFinalPathNameByHandleW(handle, buffer, (uint)buffer.Capacity, 0);
                    if (result == 0) {
                        throw new Win32Exception(Marshal.GetLastWin32Error(), "GetFinalPathNameByHandleW failed for " + path);
                    }
                }
                return buffer.ToString();
            }
        }
    }
}
"@
        $script:PathNativeAvailable = $true
    } catch {
        $script:PathNativeAvailable = $false
        $script:PathNativeFailureReason = $_.Exception.Message
    }
} else {
    $script:PathNativeAvailable = $true
}

function Normalize-FinalPath {
    param([string]$PathValue)
    if ($PathValue.StartsWith("\\?\UNC\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return ("\\{0}" -f $PathValue.Substring(8))
    }
    if ($PathValue.StartsWith("\\?\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $PathValue.Substring(4)
    }
    if ($PathValue.StartsWith("\??\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $PathValue.Substring(4)
    }
    return $PathValue
}

function Assert-NoReparsePointTraversal {
    param(
        [string]$RootPath,
        [string]$CandidatePath,
        [string]$Description
    )
    $fullRoot = [System.IO.Path]::GetFullPath($RootPath).TrimEnd("\", "/")
    $fullCandidate = [System.IO.Path]::GetFullPath($CandidatePath)
    if ($fullCandidate.Length -le $fullRoot.Length) {
        return
    }
    $relativeRemainder = $fullCandidate.Substring($fullRoot.Length).TrimStart("\", "/")
    if ([string]::IsNullOrWhiteSpace($relativeRemainder)) {
        return
    }
    $currentPath = $fullRoot
    foreach ($segment in ($relativeRemainder -split "[\\/]")) {
        if ([string]::IsNullOrWhiteSpace($segment)) {
            continue
        }
        $currentPath = Join-Path $currentPath $segment
        if (-not (Test-Path -LiteralPath $currentPath)) {
            break
        }
        $item = Get-Item -LiteralPath $currentPath -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw ("{0} contains reparse point traversal: {1}" -f $Description, $currentPath)
        }
    }
}

function Get-CanonicalPath {
    param(
        [string]$PathValue,
        [switch]$AllowMissing
    )
    $fullPath = [System.IO.Path]::GetFullPath($PathValue)
    $missingSegments = New-Object System.Collections.Generic.List[string]
    $probe = $fullPath
    while (-not (Test-Path -LiteralPath $probe)) {
        if (-not $AllowMissing) {
            throw "Path not found: $fullPath"
        }
        $leaf = Split-Path -Leaf $probe
        if ([string]::IsNullOrWhiteSpace($leaf)) {
            throw "Cannot resolve canonical path without existing ancestor: $fullPath"
        }
        $missingSegments.Insert(0, $leaf)
        $parent = Split-Path -Parent $probe
        if ([string]::IsNullOrWhiteSpace($parent) -or ($parent -eq $probe)) {
            throw "Cannot resolve canonical path without existing ancestor: $fullPath"
        }
        $probe = $parent
    }
    if ($script:PathNativeAvailable) {
        $canonicalPath = Normalize-FinalPath -PathValue ([AiHarness.PathNative]::GetFinalPath($probe))
    } else {
        $canonicalPath = [System.IO.Path]::GetFullPath($probe)
    }
    foreach ($segment in $missingSegments) {
        $canonicalPath = [System.IO.Path]::GetFullPath((Join-Path $canonicalPath $segment))
    }
    return $canonicalPath
}

function Get-NormalizedDirectoryPrefix {
    param([string]$PathValue)
    $fullPath = Get-CanonicalPath -PathValue $PathValue -AllowMissing
    if ($fullPath.EndsWith([System.IO.Path]::DirectorySeparatorChar) -or $fullPath.EndsWith([System.IO.Path]::AltDirectorySeparatorChar)) {
        return $fullPath
    }
    return ($fullPath + [System.IO.Path]::DirectorySeparatorChar)
}

function Test-PathWithinRoot {
    param([string]$RootPath, [string]$CandidatePath)
    $rootPrefix = Get-NormalizedDirectoryPrefix -PathValue $RootPath
    $fullCandidate = Get-CanonicalPath -PathValue $CandidatePath -AllowMissing
    $withinRoot = $fullCandidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    if ($withinRoot) {
        Assert-NoReparsePointTraversal -RootPath $RootPath -CandidatePath $CandidatePath -Description "managed root path"
    }
    return $withinRoot
}

function Resolve-PathWithinRoot {
    param([string]$RootPath, [string]$RelativePath)
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $RootPath ($RelativePath -replace "/", "\")))
    if (-not (Test-PathWithinRoot -RootPath $RootPath -CandidatePath $candidate)) {
        throw "Resolved path escapes managed root: $RelativePath -> $candidate"
    }
    return $candidate
}

function Get-RelativePathWithinRoot {
    param([string]$RootPath, [string]$PathValue)
    $fullPath = Get-CanonicalPath -PathValue $PathValue
    $rootPrefix = Get-NormalizedDirectoryPrefix -PathValue $RootPath
    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside managed root: $PathValue"
    }
    Assert-NoReparsePointTraversal -RootPath $RootPath -CandidatePath $PathValue -Description "managed root path"
    return ($fullPath.Substring($rootPrefix.Length) -replace "\\", "/")
}

function Get-FileSha256 {
    param([string]$PathValue)
    return (Get-FileHash -LiteralPath $PathValue -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-TreeFileSpecs {
    param(
        [string]$RootPath,
        [string]$ManagedSkillName,
        [string]$TargetPrefix,
        [string]$SourcePrefix
    )
    $specs = [System.Collections.Generic.List[object]]::new()
    Get-ChildItem -LiteralPath $RootPath -Recurse -File | Sort-Object FullName | ForEach-Object {
        $relative = Get-RelativePathWithinRoot -RootPath $RootPath -PathValue $_.FullName
        $targetRel = if ([string]::IsNullOrWhiteSpace($TargetPrefix)) { $relative } else { ("{0}/{1}" -f $TargetPrefix, $relative) }
        $specs.Add([ordered]@{
            source_path = $_.FullName
            source_rel  = ("{0}/{1}" -f $SourcePrefix, $relative)
            target_rel  = $targetRel
            sha256      = Get-FileSha256 -PathValue $_.FullName
        }) | Out-Null
    }
    return $specs
}

function Get-RelativeTreeHashes {
    param([string]$RootPath)
    $map = [ordered]@{}
    if (-not (Test-Path -LiteralPath $RootPath)) {
        return $map
    }
    Get-ChildItem -LiteralPath $RootPath -Recurse -File | Sort-Object FullName | ForEach-Object {
        $relative = Get-RelativePathWithinRoot -RootPath $RootPath -PathValue $_.FullName
        $map[$relative] = Get-FileSha256 -PathValue $_.FullName
    }
    return $map
}

function New-ReceiptPayload {
    param(
        [string]$CodexHomeValue,
        [string]$RuntimeRootValue,
        [string[]]$ManagedSkillNames,
        [object[]]$ManagedFiles
    )
    return [ordered]@{
        schema_version = "2.0"
        harness_root   = $HarnessRoot
        codex_home     = $CodexHomeValue
        runtime_root   = $RuntimeRootValue
        managed_skills = @($ManagedSkillNames | Sort-Object)
        managed_files  = $ManagedFiles
        last_sync      = (Get-Date).ToString("o")
    }
}

function Test-ManagedSkillTarget {
    param(
        [string]$TargetPath,
        [string[]]$ManagedSkillNames
    )
    $normalizedTarget = ([string]$TargetPath).Replace('\', '/').TrimStart('/')
    if ([string]::IsNullOrWhiteSpace($normalizedTarget)) {
        return $false
    }
    foreach ($managedSkillName in @($ManagedSkillNames)) {
        if (($normalizedTarget -eq $managedSkillName) -or $normalizedTarget.StartsWith(("{0}/" -f $managedSkillName))) {
            return $true
        }
    }
    return $false
}

function Get-ReceiptTrustInfo {
    param(
        [object]$ReceiptData,
        [string]$CodexHomeValue,
        [string]$RuntimeRootValue,
        [string[]]$ManagedSkillNames
    )
    if ($null -eq $ReceiptData) {
        return [PSCustomObject]@{
            Exists = $false
            Trusted = $false
            ManagedTargets = @{}
            Issues = @()
        }
    }

    $issues = [System.Collections.Generic.List[string]]::new()
    $trustedTargets = @{}
    if ("$($ReceiptData["harness_root"])" -ne $HarnessRoot) {
        $issues.Add("receipt_harness_root_mismatch") | Out-Null
    }
    if ("$($ReceiptData["codex_home"])" -ne $CodexHomeValue) {
        $issues.Add("receipt_codex_home_mismatch") | Out-Null
    }
    if ("$($ReceiptData["runtime_root"])" -ne $RuntimeRootValue) {
        $issues.Add("receipt_runtime_root_mismatch") | Out-Null
    }
    if (-not ($ReceiptData -is [System.Collections.IDictionary]) -or (-not $ReceiptData.Contains("managed_files"))) {
        $issues.Add("receipt_missing_managed_files") | Out-Null
    } else {
        $managedFiles = @($ReceiptData["managed_files"])
        if ($managedFiles.Count -eq 0) {
            $issues.Add("receipt_managed_files_empty") | Out-Null
        }
    foreach ($entry in $managedFiles) {
        if ($null -eq $entry) { continue }
        $target = ([string]$entry["target"]).Replace('\', '/').TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($target)) {
            $issues.Add("receipt_missing_target") | Out-Null
            continue
        }
        try {
            $resolved = Resolve-PathWithinRoot -RootPath $RuntimeRootValue -RelativePath $target
        } catch {
            $issues.Add("receipt_target_out_of_runtime_root") | Out-Null
            continue
        }
        $runtimeRootPrefix = Get-NormalizedDirectoryPrefix -PathValue $RuntimeRootValue
        $canonicalTarget = ((Get-CanonicalPath -PathValue $resolved -AllowMissing).Substring($runtimeRootPrefix.Length) -replace "\\", "/")
        if (-not (Test-ManagedSkillTarget -TargetPath $canonicalTarget -ManagedSkillNames $ManagedSkillNames)) {
            $issues.Add("receipt_unmanaged_skill_target") | Out-Null
            continue
        }
        if (-not (Test-Path -LiteralPath $resolved)) {
            $issues.Add("receipt_target_missing") | Out-Null
            continue
        }
        $expectedSha = [string]$entry["sha256"]
        if ([string]::IsNullOrWhiteSpace($expectedSha)) {
            $issues.Add("receipt_target_sha256_missing") | Out-Null
            continue
        }
        $actualSha = Get-FileSha256 -PathValue $resolved
        if ($actualSha -ne $expectedSha.ToLowerInvariant()) {
            $issues.Add("receipt_target_sha256_mismatch") | Out-Null
            continue
        }
        $trustedTargets[$canonicalTarget] = $entry
    }
    }
    return [PSCustomObject]@{
        Exists = $true
        Trusted = ($issues.Count -eq 0)
        ManagedTargets = $trustedTargets
        Issues = @($issues)
    }
}

function Get-UniqueBackupPath {
    param([string]$PathValue)
    return ("{0}.bak.{1}" -f $PathValue, ([guid]::NewGuid().ToString("N")))
}

function Invoke-Commit {
    param(
        [object[]]$SkillStages,
        [string]$StageReceiptPath,
        [string]$ActualReceiptPath
    )
    $skillBackups = [System.Collections.Generic.List[object]]::new()
    $skillCommittedPaths = [System.Collections.Generic.List[string]]::new()
    $receiptBackup = $null
    $receiptCommitted = $false
    try {
        foreach ($stage in @($SkillStages)) {
            $actualSkillDir = [string]$stage["actual_path"]
            $stageSkillDir = [string]$stage["stage_path"]
            $skillBackup = $null
            if (Test-Path -LiteralPath $ActualSkillDir) {
                $skillBackup = Get-UniqueBackupPath -PathValue $ActualSkillDir
                Move-Item -LiteralPath $ActualSkillDir -Destination $skillBackup
            }
            $skillBackups.Add([ordered]@{
                actual_path = $actualSkillDir
                backup_path = $skillBackup
            }) | Out-Null
            Move-Item -LiteralPath $StageSkillDir -Destination $ActualSkillDir
            $skillCommittedPaths.Add($actualSkillDir) | Out-Null
        }

        if (Test-Path -LiteralPath $ActualReceiptPath) {
            $receiptBackup = Get-UniqueBackupPath -PathValue $ActualReceiptPath
            Move-Item -LiteralPath $ActualReceiptPath -Destination $receiptBackup
        }
        Move-Item -LiteralPath $StageReceiptPath -Destination $ActualReceiptPath
        $receiptCommitted = $true

        foreach ($backupPath in @($receiptBackup)) {
            if ($backupPath -and (Test-Path -LiteralPath $backupPath)) {
                Remove-Item -LiteralPath $backupPath -Recurse -Force
            }
        }
        foreach ($skillBackupEntry in @($skillBackups)) {
            $backupPath = [string]$skillBackupEntry["backup_path"]
            if ($backupPath -and (Test-Path -LiteralPath $backupPath)) {
                Remove-Item -LiteralPath $backupPath -Recurse -Force
            }
        }
    } catch {
        if ($receiptCommitted -and (Test-Path -LiteralPath $ActualReceiptPath)) {
            Remove-Item -LiteralPath $ActualReceiptPath -Force
        }
        if ($receiptBackup -and (Test-Path -LiteralPath $receiptBackup)) {
            Move-Item -LiteralPath $receiptBackup -Destination $ActualReceiptPath
        }
        for ($index = ($skillCommittedPaths.Count - 1); $index -ge 0; $index--) {
            $actualSkillDir = $skillCommittedPaths[$index]
            if (Test-Path -LiteralPath $actualSkillDir) {
                Remove-Item -LiteralPath $actualSkillDir -Recurse -Force
            }
        }
        for ($index = ($skillBackups.Count - 1); $index -ge 0; $index--) {
            $skillBackupEntry = $skillBackups[$index]
            $actualSkillDir = [string]$skillBackupEntry["actual_path"]
            $skillBackup = [string]$skillBackupEntry["backup_path"]
            if ($skillBackup -and (Test-Path -LiteralPath $skillBackup)) {
                Move-Item -LiteralPath $skillBackup -Destination $actualSkillDir
            }
        }
        throw
    }
}

$HarnessRoot = Normalize-UserPath -PathValue $HarnessRoot
if (-not $CodexHome) {
    $CodexHome = Join-Path $env:USERPROFILE ".codex"
}
$CodexHome = Normalize-UserPath -PathValue $CodexHome
$RuntimeSkillsRoot = Join-Path $CodexHome "skills"
$ReceiptDir = Join-Path $CodexHome ".ai-harness"
$ReceiptPath = Join-Path $ReceiptDir "codex-sync.receipt.json"
$SourceSkillDirs = [ordered]@{}
$SourceSkillLabels = [ordered]@{}
$RuntimeSkillDirs = [ordered]@{}
foreach ($managedSkillContract in $ManagedSkillContracts) {
    $managedSkillName = [string]$managedSkillContract["name"]
    $sourceDirRel = [string]$managedSkillContract["source_dir"]
    if ([string]::IsNullOrWhiteSpace($sourceDirRel)) {
        $sourceDirRel = ("skills\{0}" -f $managedSkillName)
    }
    $sourceLabel = [string]$managedSkillContract["source_label"]
    if ([string]::IsNullOrWhiteSpace($sourceLabel)) {
        $sourceLabel = ("skills/{0}" -f $managedSkillName)
    }
    $sourceSkillDir = Join-Path $HarnessRoot ($sourceDirRel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $sourceSkillDir)) {
        throw "Managed source skill missing: $sourceSkillDir"
    }
    $SourceSkillDirs[$managedSkillName] = $sourceSkillDir
    $SourceSkillLabels[$managedSkillName] = $sourceLabel
    $RuntimeSkillDirs[$managedSkillName] = (Join-Path $RuntimeSkillsRoot $managedSkillName)
}

$result = Invoke-WithSyncLock -CodexHomeValue $CodexHome -ScriptBlock {
    $sourceSpecs = [System.Collections.Generic.List[object]]::new()
    $desiredTargetHashes = [ordered]@{}
    foreach ($managedSkillName in $ManagedSkillNames) {
        $skillSpecs = Get-TreeFileSpecs -RootPath $SourceSkillDirs[$managedSkillName] -ManagedSkillName $managedSkillName -TargetPrefix $managedSkillName -SourcePrefix $SourceSkillLabels[$managedSkillName]
        foreach ($spec in $skillSpecs) {
            $sourceSpecs.Add($spec) | Out-Null
            $desiredTargetHashes[$spec["target_rel"]] = $spec["sha256"]
        }
    }

    $receiptReadError = $null
    try {
        $receipt = Read-JsonMap -PathValue $ReceiptPath
    } catch {
        $receipt = $null
        $receiptReadError = $_.Exception.Message
    }
    if ($null -ne $receiptReadError) {
        $receiptTrust = [PSCustomObject]@{
            Exists = $true
            Trusted = $false
            ManagedTargets = @{}
            Issues = @('receipt_invalid_json_root')
        }
    } else {
        $receiptTrust = Get-ReceiptTrustInfo -ReceiptData $receipt -CodexHomeValue $CodexHome -RuntimeRootValue $RuntimeSkillsRoot -ManagedSkillNames $ManagedSkillNames
    }
    $runtimeTargetHashes = [ordered]@{}
    $runtimeExists = $false
    foreach ($managedSkillName in $ManagedSkillNames) {
        $runtimeSkillDir = $RuntimeSkillDirs[$managedSkillName]
        if (Test-Path -LiteralPath $runtimeSkillDir) {
            $runtimeExists = $true
        }
        $runtimeHashes = Get-RelativeTreeHashes -RootPath $runtimeSkillDir
        foreach ($key in $runtimeHashes.Keys) {
            $runtimeTargetHashes[("{0}/{1}" -f $managedSkillName, $key)] = $runtimeHashes[$key]
        }
    }

    $conflicts = [System.Collections.Generic.List[string]]::new()
    if ($receiptTrust.Exists -and (-not $receiptTrust.Trusted)) {
        foreach ($issue in $receiptTrust.Issues) {
            $conflicts.Add($issue) | Out-Null
        }
    }
    if ((-not $receiptTrust.Exists) -and $runtimeExists) {
        $conflicts.Add("runtime_unmanaged_conflict") | Out-Null
    }

    $summary = [ordered]@{
        operation = "sync_codex"
        managed_skills = @($ManagedSkillNames)
        codex_home = $CodexHome
        runtime_root = $RuntimeSkillsRoot
        receipt_path = $ReceiptPath
        updated = $false
        adopted = $false
        unchanged = $false
        conflicts = @($conflicts)
    }

    if ($conflicts.Count -gt 0) {
        return [PSCustomObject]@{
            Summary = $summary
            ExitCode = 1
        }
    }

    $desiredRuntimeJson = Get-CompressedJson -Data $desiredTargetHashes
    $currentRuntimeJson = Get-CompressedJson -Data $runtimeTargetHashes
    $needsRuntimeUpdate = ($desiredRuntimeJson -ne $currentRuntimeJson)
    $expectedReceiptTargets = [System.Collections.Generic.List[object]]::new()
    foreach ($spec in @($sourceSpecs)) {
        $expectedReceiptTargets.Add([ordered]@{
            source = $spec["source_rel"]
            target = $spec["target_rel"]
            sha256 = $spec["sha256"]
        }) | Out-Null
    }

    $writeReceipt = $true
    if ($receiptTrust.Trusted) {
        $expectedReceiptPayload = New-ReceiptPayload -CodexHomeValue $CodexHome -RuntimeRootValue $RuntimeSkillsRoot -ManagedSkillNames $ManagedSkillNames -ManagedFiles $expectedReceiptTargets
        if (Test-Path -LiteralPath $ReceiptPath) {
            $existingReceiptText = Get-Content -LiteralPath $ReceiptPath -Raw -Encoding UTF8
            $existingReceipt = ConvertTo-NormalizedMap -InputObject ($existingReceiptText | ConvertFrom-Json)
            $comparisonReceipt = ConvertTo-NormalizedMap -InputObject (($expectedReceiptPayload | ConvertTo-Json -Depth 64) | ConvertFrom-Json)
            $existingReceipt.Remove("last_sync")
            $comparisonReceipt.Remove("last_sync")
            if (($existingReceipt | ConvertTo-Json -Depth 64 -Compress) -eq ($comparisonReceipt | ConvertTo-Json -Depth 64 -Compress)) {
                $writeReceipt = $false
            }
        }
    }

    if (-not $needsRuntimeUpdate -and $receiptTrust.Trusted -and (-not $writeReceipt)) {
        $summary["unchanged"] = $true
        return [PSCustomObject]@{
            Summary = $summary
            ExitCode = 0
        }
    }

    New-Item -ItemType Directory -Path $RuntimeSkillsRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $ReceiptDir -Force | Out-Null
    $stageRoot = Join-Path $ReceiptDir (".staging\codex-sync-{0}" -f ([guid]::NewGuid().ToString("N")))
    $stageReceiptPath = Join-Path $stageRoot "codex-sync.receipt.json"
    New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
    $skillStages = [System.Collections.Generic.List[object]]::new()
    foreach ($managedSkillName in $ManagedSkillNames) {
        $stageSkillDir = Join-Path $stageRoot $managedSkillName
        Copy-Item -LiteralPath $SourceSkillDirs[$managedSkillName] -Destination $stageSkillDir -Recurse -Force
        $skillStages.Add([ordered]@{
            stage_path = $stageSkillDir
            actual_path = $RuntimeSkillDirs[$managedSkillName]
            source_prefix = $SourceSkillLabels[$managedSkillName]
        }) | Out-Null
    }

    $managedFiles = [System.Collections.Generic.List[object]]::new()
    foreach ($skillStage in @($skillStages)) {
        $stageSkillDir = [string]$skillStage["stage_path"]
        $actualSkillDir = [string]$skillStage["actual_path"]
        $managedSkillName = Split-Path -Leaf $actualSkillDir
        $sourcePrefix = [string]$skillStage["source_prefix"]
        Get-ChildItem -LiteralPath $stageSkillDir -Recurse -File | Sort-Object FullName | ForEach-Object {
            $relative = Get-RelativePathWithinRoot -RootPath $stageSkillDir -PathValue $_.FullName
            $managedFiles.Add([ordered]@{
                source = ("{0}/{1}" -f $sourcePrefix, $relative)
                target = ("{0}/{1}" -f $managedSkillName, $relative)
                sha256 = Get-FileSha256 -PathValue $_.FullName
            }) | Out-Null
        }
    }
    $receiptPayload = New-ReceiptPayload -CodexHomeValue $CodexHome -RuntimeRootValue $RuntimeSkillsRoot -ManagedSkillNames $ManagedSkillNames -ManagedFiles $managedFiles
    Write-JsonFile -PathValue $stageReceiptPath -Data $receiptPayload

    try {
        Invoke-Commit -SkillStages $skillStages -StageReceiptPath $stageReceiptPath -ActualReceiptPath $ReceiptPath
    } finally {
        if (Test-Path -LiteralPath $stageRoot) {
            Remove-Item -LiteralPath $stageRoot -Recurse -Force
        }
    }

    $summary["updated"] = $true
    $summary["adopted"] = ((-not $receiptTrust.Exists) -and $runtimeExists -and ($runtimeTargetHashes.Count -gt 0))
    return [PSCustomObject]@{
        Summary = $summary
        ExitCode = 0
    }
}

$summary = $result.Summary
if ($Json) { $summary | ConvertTo-Json -Depth 16 } else { $summary }
exit ([int]$result.ExitCode)
