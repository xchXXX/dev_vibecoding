param(
    [string]$HarnessRoot,
    [string]$ManifestPath,
    [string]$SettingsTemplatePath,
    [string]$ClaudeHome,
    [switch]$DryRun,
    [switch]$Json,
    [switch]$ForceTakeover,
    [switch]$AllowBootstrap
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $HarnessRoot) {
    $HarnessRoot = Split-Path -Parent $ScriptRoot
}

$AllowedEvents = @(
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SubagentStop"
)
$ExpectedManifestRuntime = "claude-native"
$ExpectedManifestTargets = [ordered]@{
    SessionStart    = "session_start"
    UserPromptSubmit = "user_prompt_submit"
    PreToolUse      = "pre_tool_use"
    PostToolUse     = "post_tool_use"
    Stop            = "stop"
    SubagentStop    = "subagent_stop"
}
$ToolMatcher = "^(Bash|Write|Edit|MultiEdit)$"

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

function Normalize-RelativePath {
    param([string]$PathValue)
    if (-not $PathValue) {
        return ""
    }
    return ($PathValue -replace "\\", "/").TrimStart("/", "\")
}

if (-not ("AiHarness.PathNative" -as [type])) {
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

function Get-CanonicalPath {
    param(
        [string]$PathValue,
        [switch]$AllowMissing
    )
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        throw "Path is empty"
    }
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

    $canonicalPath = Normalize-FinalPath -PathValue ([AiHarness.PathNative]::GetFinalPath($probe))
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

function Resolve-PathWithinRoot {
    param(
        [string]$RootPath,
        [string]$RelativePath
    )
    $normalizedRelative = Normalize-RelativePath -PathValue $RelativePath
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $RootPath ($normalizedRelative -replace "/", "\")))
    if (-not (Test-PathWithinRoot -RootPath $RootPath -CandidatePath $candidate)) {
        throw "Resolved path escapes managed root: $RelativePath -> $candidate"
    }
    return $candidate
}

function Test-PathWithinRoot {
    param(
        [string]$RootPath,
        [string]$CandidatePath
    )
    $rootPrefix = Get-NormalizedDirectoryPrefix -PathValue $RootPath
    $fullCandidate = Get-CanonicalPath -PathValue $CandidatePath -AllowMissing
    return $fullCandidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Resolve-PathAgainstRoot {
    param(
        [string]$RootPath,
        [string]$PathValue,
        [string]$Description
    )
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        throw "$Description is empty"
    }
    $candidate = if ([System.IO.Path]::IsPathRooted($PathValue)) {
        [System.IO.Path]::GetFullPath($PathValue)
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $RootPath $PathValue))
    }
    if (-not (Test-PathWithinRoot -RootPath $RootPath -CandidatePath $candidate)) {
        throw "$Description escapes root: $PathValue -> $candidate"
    }
    return $candidate
}

function Get-RelativePathWithinRoot {
    param(
        [string]$RootPath,
        [string]$PathValue
    )
    $fullPath = Get-CanonicalPath -PathValue $PathValue
    $rootPrefix = Get-NormalizedDirectoryPrefix -PathValue $RootPath
    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside managed root: $PathValue"
    }
    return ($fullPath.Substring($rootPrefix.Length) -replace "\\", "/")
}

function Get-ExpectedManifestTargetValue {
    param([string]$EventName)
    if (-not $ExpectedManifestTargets.Contains($EventName)) {
        throw "Unexpected manifest event id: $EventName"
    }
    return [string]$ExpectedManifestTargets[$EventName]
}

function Get-ExpectedRuntimeRelativePath {
    param([string]$EventName)
    return ("scripts/{0}.ps1" -f (Get-ExpectedManifestTargetValue -EventName $EventName))
}

function Test-MapHasKey {
    param(
        [object]$Map,
        [string]$Key
    )
    if ($null -eq $Map) {
        return $false
    }
    if ($Map -is [System.Collections.Specialized.OrderedDictionary]) {
        return $Map.Contains($Key)
    }
    if ($Map -is [System.Collections.IDictionary]) {
        if ($Map.PSObject.Methods.Name -contains "ContainsKey") {
            return $Map.ContainsKey($Key)
        }
        return $Map.Contains($Key)
    }
    if (($Map -is [psobject]) -and $Map.PSObject.Properties.Name -contains $Key) {
        return $true
    }
    return $false
}

function Get-MapKeys {
    param([object]$Map)
    if ($null -eq $Map) {
        return @()
    }
    if ($Map -is [System.Collections.Specialized.OrderedDictionary]) {
        return @($Map.Keys)
    }
    if ($Map -is [System.Collections.IDictionary]) {
        return @($Map.Keys)
    }
    if ($Map -is [psobject]) {
        return @($Map.PSObject.Properties.Name)
    }
    return @()
}

function Add-Action {
    param(
        [string]$Type,
        [string]$Message,
        [string]$Details = ""
    )
    $script:ActionLog.Add([PSCustomObject]@{
        timestamp = (Get-Date).ToString("o")
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

function Ensure-Directory {
    param(
        [string]$PathValue,
        [string]$Description
    )
    if (Test-Path -LiteralPath $PathValue) {
        return
    }
    if ($DryRun) {
        Add-Action "dry_run" ("Would create {0}" -f $Description) $PathValue
        return
    }
    New-Item -ItemType Directory -Path $PathValue -Force | Out-Null
    Add-Action "create" ("{0} created" -f $Description) $PathValue
}

function Get-FileSha256 {
    param([string]$PathValue)
    return (Get-FileHash -LiteralPath $PathValue -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-StringSha256 {
    param([string]$Content)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha256.ComputeHash($bytes)
    } finally {
        $sha256.Dispose()
    }
    return ([BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
}

function ConvertTo-NormalizedMap {
    param([object]$InputObject)
    if ($null -eq $InputObject) {
        return $null
    }
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
        throw "JSON file not found: $PathValue"
    }
    $raw = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [ordered]@{}
    }
    $parsed = ConvertTo-NormalizedMap -InputObject ($raw | ConvertFrom-Json)
    if ($null -eq $parsed) {
        return [ordered]@{}
    }
    if (-not ($parsed -is [System.Collections.IDictionary])) {
        throw "JSON root must be an object: $PathValue"
    }
    return $parsed
}

function Write-JsonFile {
    param(
        [string]$PathValue,
        [object]$Data
    )
    $jsonText = $Data | ConvertTo-Json -Depth 64
    Set-Content -LiteralPath $PathValue -Value $jsonText -Encoding UTF8
}

function Get-CompressedJson {
    param([object]$Data)
    return ($Data | ConvertTo-Json -Depth 64 -Compress)
}

function Get-HookCommandExecutable {
    $pwshCommand = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($null -ne $pwshCommand) {
        return "pwsh"
    }
    return "powershell"
}

function Get-ManifestScriptRuntimeRelativePath {
    param([object]$ManifestItem)
    $itemId = [string]$ManifestItem.id
    $targetValue = Normalize-RelativePath -PathValue ([string]$ManifestItem.target)
    if ([string]::IsNullOrWhiteSpace($targetValue)) {
        throw "Manifest item target is empty: $itemId"
    }
    $expectedTarget = Get-ExpectedManifestTargetValue -EventName $itemId
    if ($targetValue -ne $expectedTarget) {
        throw ("Manifest item target mismatch for {0}: expected {1}, actual {2}" -f $itemId, $expectedTarget, $targetValue)
    }
    return (Get-ExpectedRuntimeRelativePath -EventName $itemId)
}

function Load-Manifest {
    param([string]$PathValue)
    $manifest = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $manifest.schema_version) { throw "Manifest missing schema_version: $PathValue" }
    if (-not $manifest.runtime) { throw "Manifest missing runtime: $PathValue" }
    if ([string]$manifest.runtime -ne $ExpectedManifestRuntime) { throw ("Manifest runtime must be {0}: {1}" -f $ExpectedManifestRuntime, $PathValue) }
    if (-not $manifest.items -or @($manifest.items).Count -eq 0) { throw "Manifest has no items: $PathValue" }

    $seenIds = [System.Collections.Generic.HashSet[string]]::new()
    $seenRuntimeTargets = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($item in @($manifest.items)) {
        if (-not $item.id) { throw "Manifest item missing id" }
        if (-not $item.source) { throw "Manifest item $($item.id) missing source" }
        if (-not $item.target) { throw "Manifest item $($item.id) missing target" }
        if ($AllowedEvents -notcontains [string]$item.id) {
            throw "Manifest item id is out of scope: $($item.id)"
        }
        if (-not $seenIds.Add([string]$item.id)) {
            throw "Manifest duplicate id: $($item.id)"
        }
        $resolvedSourcePath = Resolve-PathAgainstRoot -RootPath $HarnessRoot -PathValue ([string]$item.source) -Description ("Manifest item source for {0}" -f $item.id)
        if (-not (Test-Path -LiteralPath $resolvedSourcePath)) {
            throw "Manifest source missing: $resolvedSourcePath"
        }
        $item | Add-Member -NotePropertyName source_resolved_path -NotePropertyValue $resolvedSourcePath -Force
        $runtimeTargetRelative = Get-ManifestScriptRuntimeRelativePath -ManifestItem $item
        if (-not $seenRuntimeTargets.Add($runtimeTargetRelative)) {
            throw "Manifest duplicate runtime target: $runtimeTargetRelative"
        }
    }
    foreach ($eventName in $AllowedEvents) {
        if (-not $seenIds.Contains($eventName)) {
            throw "Manifest missing event item: $eventName"
        }
    }
    return $manifest
}

function Validate-SettingsTemplate {
  param([object]$TemplateMap)
    if (-not (Test-MapHasKey -Map $TemplateMap -Key "hooks")) {
        throw "Settings template missing top-level hooks"
    }
    if (-not ($TemplateMap["hooks"] -is [System.Collections.IDictionary])) {
        throw "Settings template hooks must be object"
    }
    $hooksMap = $TemplateMap["hooks"]
    $unknownEvents = @((Get-MapKeys -Map $hooksMap) | Where-Object { $AllowedEvents -notcontains [string]$_ })
    if ($unknownEvents.Count -gt 0) {
        throw ("Settings template contains out-of-scope hooks events: {0}" -f ($unknownEvents -join ", "))
    }
    foreach ($eventName in $AllowedEvents) {
        if (-not (Test-MapHasKey -Map $hooksMap -Key $eventName)) {
            throw "Settings template missing event hooks: $eventName"
        }
        $eventEntries = @($hooksMap[$eventName])
        if ($eventEntries.Count -eq 0) {
            throw "Settings template event has no entries: $eventName"
        }
        foreach ($entry in $eventEntries) {
            if (-not ($entry -is [System.Collections.IDictionary])) {
                throw "Settings template event entry must be object: $eventName"
            }
            if ((@("PreToolUse", "PostToolUse") -contains $eventName) -and ($entry["matcher"] -ne $ToolMatcher)) {
                throw "Settings template matcher mismatch for $eventName"
            }
            $handlers = @($entry["hooks"])
            if ($handlers.Count -eq 0) {
                throw "Settings template event entry has no handlers: $eventName"
            }
            foreach ($handler in $handlers) {
                if (-not ($handler -is [System.Collections.IDictionary])) {
                    throw "Settings template handler must be object: $eventName"
                }
                if ($handler["type"] -ne "command") {
                    throw "Settings template handler type must be command: $eventName"
                }
                if ($handler["shell"] -ne "powershell") {
                    throw "Settings template handler shell must be powershell: $eventName"
                }
            }
        }
    }
}

function Build-RuntimeHooks {
    param(
        [object]$TemplateHooksMap,
        [string]$RuntimeRootValue,
        [string]$CommandExecutable,
        [hashtable]$EventRuntimeScriptMap
    )
    $clonedHooks = ConvertTo-NormalizedMap -InputObject ((Get-CompressedJson -Data $TemplateHooksMap) | ConvertFrom-Json)
    $runtimeHooks = [ordered]@{}
    foreach ($eventName in $AllowedEvents) {
        $eventEntries = @($clonedHooks[$eventName])
        foreach ($entry in $eventEntries) {
            if ((@("PreToolUse", "PostToolUse") -contains $eventName)) {
                $entry["matcher"] = $ToolMatcher
            }
            $handlers = @($entry["hooks"])
            foreach ($handler in $handlers) {
                $handler["type"] = "command"
                $handler["shell"] = "powershell"
                $runtimeScript = Resolve-PathWithinRoot -RootPath $RuntimeRootValue -RelativePath $EventRuntimeScriptMap[$eventName]
                $handler["command"] = ('{0} -NoProfile -ExecutionPolicy Bypass -File "{1}"' -f $CommandExecutable, $runtimeScript)
            }
        }
        $runtimeHooks[$eventName] = $eventEntries
    }
    return $runtimeHooks
}

function Load-Receipt {
    param([string]$PathValue)
    if (-not (Test-Path -LiteralPath $PathValue)) {
        return $null
    }
    $receipt = Read-JsonMap -PathValue $PathValue
    if (Test-MapHasKey -Map $receipt -Key "managed_files") {
        return $receipt
    }
    if (Test-MapHasKey -Map $receipt -Key "items") {
        $receipt["managed_files"] = @()
        foreach ($item in @($receipt["items"])) {
            $receipt["managed_files"] += [ordered]@{
                id     = $item["id"]
                kind   = "legacy"
                source = $item["source"]
                target = Normalize-RelativePath $item["target"]
                sha256 = ""
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
        [string]$ReceiptDirValue,
        [string]$RuntimeRootValue,
        [string]$SettingsPathValue,
        [string]$RuntimeSettingsRelativePath,
        [string]$HooksHash
    )
    $payload = [ordered]@{
        schema_version = "1.0"
        harness_root   = $HarnessRoot
        runtime_root   = $RuntimeRootValue
        manifest       = [ordered]@{
            path           = $ManifestPath
            schema_version = $Manifest.schema_version
            runtime        = $Manifest.runtime
            last_sync      = (Get-Date).ToString("o")
        }
        settings       = [ordered]@{
            path                     = $SettingsPathValue
            managed_top_level        = "hooks"
            runtime_fragment_path    = $RuntimeSettingsRelativePath
            managed_hooks_sha256     = $HooksHash
        }
        managed_files  = $ManagedFiles
    }
    if ($DryRun) {
        Add-Action "dry_run" "Would write receipt" $ReceiptPathValue
        return
    }
    Ensure-Directory -PathValue $ReceiptDirValue -Description "receipt directory"
    Write-JsonFile -PathValue $ReceiptPathValue -Data $payload
    Add-Action "write" "Receipt written" $ReceiptPathValue
}

function New-ReceiptPayload {
    param(
        [object[]]$ManagedFiles,
        [object]$Manifest,
        [string]$RuntimeRootValue,
        [string]$SettingsPathValue,
        [string]$RuntimeSettingsRelativePath,
        [string]$HooksHash
    )
    return [ordered]@{
        schema_version = "1.0"
        harness_root   = $HarnessRoot
        runtime_root   = $RuntimeRootValue
        manifest       = [ordered]@{
            path           = $ManifestPath
            schema_version = $Manifest.schema_version
            runtime        = $Manifest.runtime
            last_sync      = (Get-Date).ToString("o")
        }
        settings       = [ordered]@{
            path                  = $SettingsPathValue
            managed_top_level     = "hooks"
            runtime_fragment_path = $RuntimeSettingsRelativePath
            managed_hooks_sha256  = $HooksHash
        }
        managed_files  = $ManagedFiles
    }
}

function Get-ReceiptTrustInfo {
    param(
        [object]$ReceiptData,
        [string]$RuntimeRootValue,
        [string]$SettingsPathValue,
        [bool]$SettingsHasHooks,
        [string]$CurrentHooksHash
    )
    $trustedManagedTargets = @{}
    $issues = [System.Collections.Generic.List[string]]::new()
    $runtimeTrusted = $false
    $settingsTrusted = $false
    if ($null -eq $ReceiptData) {
        return [PSCustomObject]@{
            Exists                 = $false
            RuntimeTrusted         = $false
            SettingsTrusted        = $false
            TrustedManagedTargets  = $trustedManagedTargets
            Issues                 = @()
        }
    }

    $rootsOk = $true
    if ("$($ReceiptData["harness_root"])" -ne $HarnessRoot) {
        $issues.Add("receipt.harness_root") | Out-Null
        $rootsOk = $false
    }
    if ("$($ReceiptData["runtime_root"])" -ne $RuntimeRootValue) {
        $issues.Add("receipt.runtime_root") | Out-Null
        $rootsOk = $false
    }

    $managedFilesOk = $true
    if (-not (Test-MapHasKey -Map $ReceiptData -Key "managed_files")) {
        $issues.Add("receipt.managed_files") | Out-Null
        $managedFilesOk = $false
    } else {
        foreach ($entry in @($ReceiptData["managed_files"])) {
            if ($null -eq $entry -or -not ($entry -is [System.Collections.IDictionary])) {
                $issues.Add("receipt.managed_files.type") | Out-Null
                $managedFilesOk = $false
                continue
            }
            $targetRel = Normalize-RelativePath -PathValue ([string]$entry["target"])
            $targetSha = "$($entry["sha256"])".ToLowerInvariant()
            if ([string]::IsNullOrWhiteSpace($targetRel) -or [string]::IsNullOrWhiteSpace($targetSha)) {
                $issues.Add("receipt.managed_files.entry") | Out-Null
                $managedFilesOk = $false
                continue
            }
            try {
                $resolvedTarget = Resolve-PathWithinRoot -RootPath $RuntimeRootValue -RelativePath $targetRel
            } catch {
                $issues.Add(("receipt.managed_files.target:{0}" -f $targetRel)) | Out-Null
                $managedFilesOk = $false
                continue
            }
            if (-not (Test-Path -LiteralPath $resolvedTarget)) {
                $issues.Add(("receipt.managed_files.missing:{0}" -f $targetRel)) | Out-Null
                $managedFilesOk = $false
                continue
            }
            $actualSha = Get-FileSha256 -PathValue $resolvedTarget
            if ($actualSha -ne $targetSha) {
                $issues.Add(("receipt.managed_files.sha256:{0}" -f $targetRel)) | Out-Null
                $managedFilesOk = $false
                continue
            }
            $trustedManagedTargets[$targetRel] = $entry
        }
    }

    if ($rootsOk -and $managedFilesOk) {
        $runtimeTrusted = $true
    }

    $settingsOk = $true
    if (-not (Test-MapHasKey -Map $ReceiptData -Key "settings")) {
        $issues.Add("receipt.settings") | Out-Null
        $settingsOk = $false
    } else {
        $settingsSection = $ReceiptData["settings"]
        if (-not ($settingsSection -is [System.Collections.IDictionary])) {
            $issues.Add("receipt.settings.type") | Out-Null
            $settingsOk = $false
        } else {
            if ("$($settingsSection["path"])" -ne $SettingsPathValue) {
                $issues.Add("receipt.settings.path") | Out-Null
                $settingsOk = $false
            }
            if ("$($settingsSection["managed_top_level"])" -ne "hooks") {
                $issues.Add("receipt.settings.managed_top_level") | Out-Null
                $settingsOk = $false
            }
            $fragmentRel = Normalize-RelativePath -PathValue ([string]$settingsSection["runtime_fragment_path"])
            if ([string]::IsNullOrWhiteSpace($fragmentRel)) {
                $issues.Add("receipt.settings.runtime_fragment_path") | Out-Null
                $settingsOk = $false
            } else {
                try {
                    $fragmentPath = Resolve-PathWithinRoot -RootPath $RuntimeRootValue -RelativePath $fragmentRel
                    if (-not (Test-Path -LiteralPath $fragmentPath)) {
                        $issues.Add("receipt.settings.runtime_fragment_missing") | Out-Null
                        $settingsOk = $false
                    }
                } catch {
                    $issues.Add("receipt.settings.runtime_fragment_root") | Out-Null
                    $settingsOk = $false
                }
            }
            $expectedHooksHash = "$($settingsSection["managed_hooks_sha256"])".ToLowerInvariant()
            if ([string]::IsNullOrWhiteSpace($expectedHooksHash)) {
                $issues.Add("receipt.settings.managed_hooks_sha256") | Out-Null
                $settingsOk = $false
            } elseif ($SettingsHasHooks) {
                if ($CurrentHooksHash -ne $expectedHooksHash) {
                    $issues.Add("receipt.settings.current_hooks_sha256") | Out-Null
                    $settingsOk = $false
                }
            }
        }
    }
    if ($rootsOk -and $settingsOk) {
        $settingsTrusted = $true
    }

    return [PSCustomObject]@{
        Exists                = $true
        RuntimeTrusted        = $runtimeTrusted
        SettingsTrusted       = $settingsTrusted
        TrustedManagedTargets = $trustedManagedTargets
        Issues                = @($issues)
    }
}

function Get-RuntimeFileMap {
    param([string]$RuntimeRootValue)
    $runtimeFiles = @{}
    if (-not (Test-Path -LiteralPath $RuntimeRootValue)) {
        return $runtimeFiles
    }
    Get-ChildItem -LiteralPath $RuntimeRootValue -Recurse -File | ForEach-Object {
        $relativePath = Get-RelativePathWithinRoot -RootPath $RuntimeRootValue -PathValue $_.FullName
        $runtimeFiles[$relativePath] = $_.FullName
    }
    return $runtimeFiles
}

function Get-UniqueBackupPath {
    param([string]$PathValue)
    return ("{0}.bak.{1}" -f $PathValue, ([guid]::NewGuid().ToString("N")))
}

function Invoke-StagedCommit {
    param(
        [string]$StageRuntimeRoot,
        [string]$StageSettingsPath,
        [string]$StageReceiptPath,
        [string]$ActualRuntimeRoot,
        [string]$ActualSettingsPath,
        [string]$ActualReceiptPath,
        [string]$StageRoot
    )
    $runtimeBackupPath = $null
    $settingsBackupPath = $null
    $receiptBackupPath = $null
    $runtimeCommitted = $false
    $settingsCommitted = $false
    $receiptCommitted = $false
    try {
        Ensure-Directory -PathValue (Split-Path -Parent $ActualRuntimeRoot) -Description "Claude hooks runtime parent"
        Ensure-Directory -PathValue (Split-Path -Parent $ActualSettingsPath) -Description "Claude home"
        Ensure-Directory -PathValue (Split-Path -Parent $ActualReceiptPath) -Description "receipt directory"

        if (Test-Path -LiteralPath $ActualRuntimeRoot) {
            $runtimeBackupPath = Get-UniqueBackupPath -PathValue $ActualRuntimeRoot
            Move-Item -LiteralPath $ActualRuntimeRoot -Destination $runtimeBackupPath
        }
        Move-Item -LiteralPath $StageRuntimeRoot -Destination $ActualRuntimeRoot
        $runtimeCommitted = $true

        if ($env:AI_HARNESS_TEST_FAIL_STAGE -eq 'settings') {
            throw 'Test-injected failure before settings commit'
        }

        if (Test-Path -LiteralPath $ActualSettingsPath) {
            $settingsBackupPath = Get-UniqueBackupPath -PathValue $ActualSettingsPath
            Move-Item -LiteralPath $ActualSettingsPath -Destination $settingsBackupPath
        }
        Move-Item -LiteralPath $StageSettingsPath -Destination $ActualSettingsPath
        $settingsCommitted = $true

        if ($env:AI_HARNESS_TEST_FAIL_STAGE -eq 'receipt') {
            throw 'Test-injected failure before receipt commit'
        }

        if (Test-Path -LiteralPath $ActualReceiptPath) {
            $receiptBackupPath = Get-UniqueBackupPath -PathValue $ActualReceiptPath
            Move-Item -LiteralPath $ActualReceiptPath -Destination $receiptBackupPath
        }
        Move-Item -LiteralPath $StageReceiptPath -Destination $ActualReceiptPath
        $receiptCommitted = $true

        foreach ($backupPath in @($runtimeBackupPath, $settingsBackupPath, $receiptBackupPath)) {
            if ($backupPath -and (Test-Path -LiteralPath $backupPath)) {
                Remove-Item -LiteralPath $backupPath -Recurse -Force
            }
        }
    } catch {
        if ($receiptCommitted -and (Test-Path -LiteralPath $ActualReceiptPath)) {
            Remove-Item -LiteralPath $ActualReceiptPath -Force
        }
        if ($receiptBackupPath -and (Test-Path -LiteralPath $receiptBackupPath)) {
            Move-Item -LiteralPath $receiptBackupPath -Destination $ActualReceiptPath
        }

        if ($settingsCommitted -and (Test-Path -LiteralPath $ActualSettingsPath)) {
            Remove-Item -LiteralPath $ActualSettingsPath -Force
        }
        if ($settingsBackupPath -and (Test-Path -LiteralPath $settingsBackupPath)) {
            Move-Item -LiteralPath $settingsBackupPath -Destination $ActualSettingsPath
        }

        if ($runtimeCommitted -and (Test-Path -LiteralPath $ActualRuntimeRoot)) {
            Remove-Item -LiteralPath $ActualRuntimeRoot -Recurse -Force
        }
        if ($runtimeBackupPath -and (Test-Path -LiteralPath $runtimeBackupPath)) {
            Move-Item -LiteralPath $runtimeBackupPath -Destination $ActualRuntimeRoot
        }
        throw
    } finally {
        if (Test-Path -LiteralPath $StageRoot) {
            Remove-Item -LiteralPath $StageRoot -Recurse -Force
        }
    }
}

function Write-Summary {
    param([object]$Summary, [string]$ReceiptPathValue)
    $payload = [ordered]@{
        operation             = "sync_hooks"
        dry_run               = $DryRun.IsPresent
        json_output           = $Json.IsPresent
        force_takeover        = $ForceTakeover.IsPresent
        allow_bootstrap       = $AllowBootstrap.IsPresent
        added                 = $Summary.Added
        updated               = $Summary.Updated
        adopted               = $Summary.Adopted
        unchanged             = $Summary.Unchanged
        removed               = $Summary.Removed
        skipped_conflicts     = $Summary.Skipped
        settings_initialized  = $Summary.SettingsInitialized
        settings_hooks_update = $Summary.SettingsHooksUpdated
        receipt_path          = $ReceiptPathValue
        actions               = $script:ActionLog
    }
    if ($Json) {
        $payload | ConvertTo-Json -Depth 16
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
    if ($Summary.SettingsHooksUpdated) {
        Write-Host "  settings.json top-level hooks updated"
    }
    Write-Host ("  ReceiptPath = {0}" -f $ReceiptPathValue)
}

$script:ActionLog = [System.Collections.Generic.List[object]]::new()
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

$RuntimeRoot = Join-Path $ClaudeHome ".ai-harness/hooks/claude"
$RuntimeScriptsDir = Join-Path $RuntimeRoot "scripts"
$RuntimeManifestPath = Join-Path $RuntimeRoot "manifest.json"
$RuntimeTemplatePath = Join-Path $RuntimeRoot "settings.template.json"
$RuntimeSettingsPath = Join-Path $RuntimeRoot "settings.runtime.json"
$RuntimeSettingsRelativePath = "settings.runtime.json"
$ReceiptDir = Join-Path $ClaudeHome ".ai-harness"
$ReceiptPath = Join-Path $ReceiptDir "claude-hooks.receipt.json"
$SettingsPath = Join-Path $ClaudeHome "settings.json"

$manifest = Load-Manifest -PathValue $ManifestPath
$settingsTemplate = Read-JsonMap -PathValue $SettingsTemplatePath
Validate-SettingsTemplate -TemplateMap $settingsTemplate
$commandExecutable = Get-HookCommandExecutable
$eventRuntimeScriptMap = @{}
foreach ($item in @($manifest.items)) {
    $eventRuntimeScriptMap[[string]$item.id] = Get-ManifestScriptRuntimeRelativePath -ManifestItem $item
}
$runtimeHooks = Build-RuntimeHooks -TemplateHooksMap $settingsTemplate["hooks"] -RuntimeRootValue $RuntimeRoot -CommandExecutable $commandExecutable -EventRuntimeScriptMap $eventRuntimeScriptMap
$runtimeSettingsPayload = [ordered]@{ hooks = $runtimeHooks }
$runtimeSettingsJson = $runtimeSettingsPayload | ConvertTo-Json -Depth 64
$runtimeHooksHash = Get-StringSha256 -Content (Get-CompressedJson -Data $runtimeHooks)

$receipt = Load-Receipt -PathValue $ReceiptPath
if (($null -eq $receipt) -and (-not $AllowBootstrap)) {
    Add-Action "error" "Receipt not found; run install script first" $ReceiptPath
    Write-Summary -Summary ([PSCustomObject]@{
        Added = [System.Collections.Generic.List[string]]::new()
        Updated = [System.Collections.Generic.List[string]]::new()
        Adopted = [System.Collections.Generic.List[string]]::new()
        Unchanged = [System.Collections.Generic.List[string]]::new()
        Removed = [System.Collections.Generic.List[string]]::new()
        Skipped = [System.Collections.Generic.List[string]]::new()
        SettingsInitialized = $false
        SettingsHooksUpdated = $false
    }) -ReceiptPathValue $ReceiptPath
    exit 1
}

$summary = [PSCustomObject]@{
    Added = [System.Collections.Generic.List[string]]::new()
    Updated = [System.Collections.Generic.List[string]]::new()
    Adopted = [System.Collections.Generic.List[string]]::new()
    Unchanged = [System.Collections.Generic.List[string]]::new()
    Removed = [System.Collections.Generic.List[string]]::new()
    Skipped = [System.Collections.Generic.List[string]]::new()
    SettingsInitialized = $false
    SettingsHooksUpdated = $false
}

$desiredSpecs = [System.Collections.Generic.List[object]]::new()
$desiredSpecs.Add([ordered]@{
    id          = "manifest"
    kind        = "manifest_copy"
    source_rel  = "hooks/claude/manifest.json"
    source_path = $ManifestPath
    target_rel  = "manifest.json"
    target_path = $RuntimeManifestPath
}) | Out-Null
$desiredSpecs.Add([ordered]@{
    id          = "settings-template"
    kind        = "settings_template_copy"
    source_rel  = "hooks/claude/settings.json"
    source_path = $SettingsTemplatePath
    target_rel  = "settings.template.json"
    target_path = $RuntimeTemplatePath
}) | Out-Null
$hookCommonSourcePath = Join-Path $HarnessRoot "hooks/claude/scripts/HookCommon.ps1"
if (-not (Test-Path -LiteralPath $hookCommonSourcePath)) {
    throw "Hook helper source missing: $hookCommonSourcePath"
}
$desiredSpecs.Add([ordered]@{
    id          = "hook-common"
    kind        = "script_helper"
    source_rel  = "hooks/claude/scripts/HookCommon.ps1"
    source_path = $hookCommonSourcePath
    target_rel  = "scripts/HookCommon.ps1"
    target_path = (Resolve-PathWithinRoot -RootPath $RuntimeRoot -RelativePath "scripts/HookCommon.ps1")
}) | Out-Null
foreach ($item in @($manifest.items)) {
    $sourcePath = [string]$item.source_resolved_path
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        throw "Manifest source missing: $sourcePath"
    }
    $targetRel = Get-ManifestScriptRuntimeRelativePath -ManifestItem $item
    $targetPath = Resolve-PathWithinRoot -RootPath $RuntimeRoot -RelativePath $targetRel
    $desiredSpecs.Add([ordered]@{
        id          = [string]$item.id
        kind        = "script"
        source_rel  = [string]$item.source
        source_path = $sourcePath
        target_rel  = $targetRel
        target_path = $targetPath
    }) | Out-Null
}
$desiredSpecs.Add([ordered]@{
    id               = "runtime-settings"
    kind             = "runtime_settings"
    source_rel       = "generated:runtime_hooks"
    source_path      = $null
    generated_text   = $runtimeSettingsJson
    target_rel       = $RuntimeSettingsRelativePath
    target_path      = $RuntimeSettingsPath
}) | Out-Null

$settingsExists = Test-Path -LiteralPath $SettingsPath
$settingsMap = if ($settingsExists) {
    Read-JsonMap -PathValue $SettingsPath
} else {
    [ordered]@{}
}
if (-not ($settingsMap -is [System.Collections.IDictionary])) {
    throw "settings.json root must be object: $SettingsPath"
}
$settingsHasHooks = Test-MapHasKey -Map $settingsMap -Key "hooks"
$currentHooksJson = ""
$currentHooksHash = ""
if ($settingsHasHooks) {
    $currentHooksJson = Get-CompressedJson -Data $settingsMap["hooks"]
    $currentHooksHash = Get-StringSha256 -Content $currentHooksJson
}
$desiredHooksJson = Get-CompressedJson -Data $runtimeHooks
$receiptTrust = Get-ReceiptTrustInfo -ReceiptData $receipt -RuntimeRootValue $RuntimeRoot -SettingsPathValue $SettingsPath -SettingsHasHooks $settingsHasHooks -CurrentHooksHash $currentHooksHash
$previousManaged = if ($receiptTrust.RuntimeTrusted) { $receiptTrust.TrustedManagedTargets } else { @{} }
$settingsHooksManaged = $receiptTrust.SettingsTrusted

$desiredTargetSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($spec in $desiredSpecs) {
    [void]$desiredTargetSet.Add($spec["target_rel"])
}

$currentRuntimeFiles = Get-RuntimeFileMap -RuntimeRootValue $RuntimeRoot
$staleSpecs = [System.Collections.Generic.List[object]]::new()
$plannedSpecs = [System.Collections.Generic.List[object]]::new()
$plannedConflicts = [System.Collections.Generic.List[string]]::new()

if ($receiptTrust.Exists -and (-not $receiptTrust.RuntimeTrusted) -and (-not $ForceTakeover)) {
    $plannedConflicts.Add("receipt:runtime_untrusted") | Out-Null
}
if ($receiptTrust.Exists -and (-not $receiptTrust.SettingsTrusted) -and (-not $ForceTakeover)) {
    $plannedConflicts.Add("settings.json:hooks_untrusted_receipt") | Out-Null
}

foreach ($existingTarget in $currentRuntimeFiles.Keys) {
    if ($desiredTargetSet.Contains($existingTarget)) {
        continue
    }
    if ($receiptTrust.RuntimeTrusted -and $previousManaged.ContainsKey($existingTarget)) {
        $staleSpecs.Add([ordered]@{ target_rel = $existingTarget; target_path = $currentRuntimeFiles[$existingTarget] }) | Out-Null
        continue
    }
    if (-not $ForceTakeover) {
        $plannedConflicts.Add($existingTarget) | Out-Null
        continue
    }
    $staleSpecs.Add([ordered]@{ target_rel = $existingTarget; target_path = $currentRuntimeFiles[$existingTarget] }) | Out-Null
}

foreach ($spec in $desiredSpecs) {
    $targetRel = $spec["target_rel"]
    $targetPath = $spec["target_path"]
    $expectedHash = if ($null -ne $spec["source_path"]) {
        Get-FileSha256 -PathValue $spec["source_path"]
    } else {
        Get-StringSha256 -Content $spec["generated_text"]
    }

    if (-not (Test-Path -LiteralPath $targetPath)) {
        if ($receiptTrust.Exists -and (-not $receiptTrust.RuntimeTrusted) -and (-not $ForceTakeover)) {
            $plannedConflicts.Add($targetRel) | Out-Null
            continue
        }
        $plannedSpecs.Add([ordered]@{ action = "add"; spec = $spec; expected_hash = $expectedHash }) | Out-Null
        continue
    }

    $targetHash = Get-FileSha256 -PathValue $targetPath
    if ($receiptTrust.RuntimeTrusted -and $previousManaged.ContainsKey($targetRel)) {
        if ($targetHash -eq $expectedHash) {
            $plannedSpecs.Add([ordered]@{ action = "unchanged"; spec = $spec; expected_hash = $expectedHash }) | Out-Null
        } else {
            $plannedSpecs.Add([ordered]@{ action = "update"; spec = $spec; expected_hash = $expectedHash }) | Out-Null
        }
        continue
    }

    if ($receiptTrust.Exists) {
        if (-not $ForceTakeover) {
            $plannedConflicts.Add($targetRel) | Out-Null
            continue
        }
        $plannedSpecs.Add([ordered]@{ action = "force_takeover"; spec = $spec; expected_hash = $expectedHash }) | Out-Null
        continue
    }

    if ($targetHash -eq $expectedHash) {
        $plannedSpecs.Add([ordered]@{ action = "adopt"; spec = $spec; expected_hash = $expectedHash }) | Out-Null
        continue
    }

    if (-not $ForceTakeover) {
        $plannedConflicts.Add($targetRel) | Out-Null
        continue
    }
    $plannedSpecs.Add([ordered]@{ action = "force_takeover"; spec = $spec; expected_hash = $expectedHash }) | Out-Null
}

if ($currentHooksJson -ne $desiredHooksJson) {
    if ($settingsHasHooks -and (-not $settingsHooksManaged) -and (-not $ForceTakeover)) {
        $plannedConflicts.Add("settings.json:hooks") | Out-Null
    }
}

foreach ($conflictTarget in ($plannedConflicts | Select-Object -Unique)) {
    Add-Action "conflict" "Unmanaged conflicting state skipped" $conflictTarget
    $summary.Skipped.Add($conflictTarget) | Out-Null
}

if ($summary.Skipped.Count -eq 0) {
    if (-not $settingsExists) {
        $summary.SettingsInitialized = $true
    }

    $managedFiles = [System.Collections.Generic.List[object]]::new()
    foreach ($plannedSpec in $plannedSpecs) {
        $spec = $plannedSpec.spec
        $targetRel = $spec["target_rel"]
        $action = $plannedSpec.action
        $expectedHash = $plannedSpec.expected_hash
        if ($action -eq "add") {
            $summary.Added.Add($targetRel) | Out-Null
            if ($DryRun) {
                Add-Action "dry_run" "Would add managed file" ("{0} -> {1}" -f $spec["source_rel"], $spec["target_path"])
            }
        } elseif ($action -eq "update") {
            $summary.Updated.Add($targetRel) | Out-Null
            if ($DryRun) {
                Add-Action "dry_run" "Would update managed file" ("{0} -> {1}" -f $spec["source_rel"], $spec["target_path"])
            }
        } elseif ($action -eq "adopt") {
            $summary.Adopted.Add($targetRel) | Out-Null
            Add-Action "adopt" "Unmanaged file matches desired state and is now managed" $spec["target_path"]
        } elseif ($action -eq "unchanged") {
            $summary.Unchanged.Add($targetRel) | Out-Null
            Add-Action "unchanged" "Managed file already up to date" $spec["target_path"]
        } elseif ($action -eq "force_takeover") {
            $summary.Adopted.Add($targetRel) | Out-Null
            if ($DryRun) {
                Add-Action "dry_run" "Would take over conflicting file" ("{0} -> {1}" -f $spec["source_rel"], $spec["target_path"])
            }
        }
        $managedFiles.Add([ordered]@{
            id     = $spec["id"]
            kind   = $spec["kind"]
            source = $spec["source_rel"]
            target = $targetRel
            sha256 = $expectedHash
        }) | Out-Null
    }

    foreach ($staleSpec in $staleSpecs) {
        $summary.Removed.Add($staleSpec.target_rel) | Out-Null
        if ($DryRun) {
            Add-Action "dry_run" "Would remove stale managed file" $staleSpec.target_path
        }
    }

    if ($currentHooksJson -ne $desiredHooksJson) {
        $summary.SettingsHooksUpdated = $true
        if ($DryRun) {
            Add-Action "dry_run" "Would update settings.json top-level hooks" $SettingsPath
        }
    } elseif ($settingsHasHooks -and (-not $settingsHooksManaged)) {
        Add-Action "adopt" "Existing settings.json top-level hooks matches desired state and is now managed" $SettingsPath
    } else {
        Add-Action "unchanged" "settings.json top-level hooks already matches managed runtime hooks" $SettingsPath
    }

    if (-not $DryRun) {
        $stageRoot = Join-Path $ReceiptDir (".staging\claude-hooks-{0}" -f ([guid]::NewGuid().ToString("N")))
        $stageRuntimeRoot = Join-Path $stageRoot "runtime_root"
        $stageSettingsPath = Join-Path $stageRoot "settings.json"
        $stageReceiptPath = Join-Path $stageRoot "claude-hooks.receipt.json"

        Ensure-Directory -PathValue $stageRuntimeRoot -Description "staged runtime root"
        foreach ($plannedSpec in $plannedSpecs) {
            $spec = $plannedSpec.spec
            $stageTargetPath = Resolve-PathWithinRoot -RootPath $stageRuntimeRoot -RelativePath $spec["target_rel"]
            $stageTargetDir = Split-Path -Parent $stageTargetPath
            if ($stageTargetDir) {
                Ensure-Directory -PathValue $stageTargetDir -Description ("staged target directory for {0}" -f $spec["target_rel"])
            }
            if ($null -ne $spec["source_path"]) {
                Copy-Item -LiteralPath $spec["source_path"] -Destination $stageTargetPath -Force
            } else {
                Set-Content -LiteralPath $stageTargetPath -Value $spec["generated_text"] -Encoding UTF8
            }
        }

        $stagedSettingsMap = ConvertTo-NormalizedMap -InputObject $settingsMap
        if ($null -eq $stagedSettingsMap) {
            $stagedSettingsMap = [ordered]@{}
        }
        $stagedSettingsMap["hooks"] = $runtimeHooks
        Write-JsonFile -PathValue $stageSettingsPath -Data $stagedSettingsMap

        $persistedManagedFiles = [System.Collections.Generic.List[object]]::new()
        foreach ($managedFile in $managedFiles) {
            $stagedTargetPath = Resolve-PathWithinRoot -RootPath $stageRuntimeRoot -RelativePath ([string]$managedFile["target"])
            $persistedManagedFiles.Add([ordered]@{
                id     = $managedFile["id"]
                kind   = $managedFile["kind"]
                source = $managedFile["source"]
                target = $managedFile["target"]
                sha256 = Get-FileSha256 -PathValue $stagedTargetPath
            }) | Out-Null
        }

        $persistedRuntimeHooksHash = $runtimeHooksHash
        $stagedRuntimeSettingsPath = Resolve-PathWithinRoot -RootPath $stageRuntimeRoot -RelativePath $RuntimeSettingsRelativePath
        if (Test-Path -LiteralPath $stagedRuntimeSettingsPath) {
            $persistedRuntimeSettings = Read-JsonMap -PathValue $stagedRuntimeSettingsPath
            if (Test-MapHasKey -Map $persistedRuntimeSettings -Key "hooks") {
                $persistedRuntimeHooksHash = Get-StringSha256 -Content (Get-CompressedJson -Data $persistedRuntimeSettings["hooks"])
            }
        }

        $receiptPayload = New-ReceiptPayload -ManagedFiles $persistedManagedFiles -Manifest $manifest -RuntimeRootValue $RuntimeRoot -SettingsPathValue $SettingsPath -RuntimeSettingsRelativePath $RuntimeSettingsRelativePath -HooksHash $persistedRuntimeHooksHash
        Write-JsonFile -PathValue $stageReceiptPath -Data $receiptPayload

        Invoke-StagedCommit -StageRuntimeRoot $stageRuntimeRoot -StageSettingsPath $stageSettingsPath -StageReceiptPath $stageReceiptPath -ActualRuntimeRoot $RuntimeRoot -ActualSettingsPath $SettingsPath -ActualReceiptPath $ReceiptPath -StageRoot $stageRoot

        foreach ($plannedSpec in $plannedSpecs) {
            $spec = $plannedSpec.spec
            $action = $plannedSpec.action
            if ($action -eq "add") {
                Add-Action "add" "Managed file added" ("{0} -> {1}" -f $spec["source_rel"], $spec["target_path"])
            } elseif ($action -eq "update") {
                Add-Action "update" "Managed file updated" ("{0} -> {1}" -f $spec["source_rel"], $spec["target_path"])
            } elseif ($action -eq "force_takeover") {
                Add-Action "force_takeover" "Conflicting file taken over" ("{0} -> {1}" -f $spec["source_rel"], $spec["target_path"])
            }
        }
        foreach ($staleSpec in $staleSpecs) {
            Add-Action "remove" "Removed stale managed file" $staleSpec.target_path
        }
        if ($summary.SettingsInitialized) {
            Add-Action "create" "settings.json initialized" $SettingsPath
        }
        if ($summary.SettingsHooksUpdated) {
            Add-Action "write" "settings.json top-level hooks updated" $SettingsPath
        }
        Add-Action "write" "Receipt written" $ReceiptPath
    }
}
Write-Summary -Summary $summary -ReceiptPathValue $ReceiptPath

if ($summary.Skipped.Count -gt 0) {
    exit 1
}

exit 0
