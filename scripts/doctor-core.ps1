param(
  [string]$Root = "",
  [string]$ClaudeHome = "",
  [string]$CodexHome = "",
  [ValidateSet('claude_hooks','codex_minimal')]
  [string]$AuditTarget = "claude_hooks",
  [switch]$Json,
  [switch]$Strict,
  [switch]$IncludeRepoAudit,
  [string[]]$RequiredPaths = @(),
  [string[]]$LegacyMarkers = @(),
  [string[]]$TextRoots = @()
)

$ErrorActionPreference = "Stop"
$AllowedHookEvents = @('SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','Stop','SubagentStop')
$ExpectedManifestRuntime = 'claude-native'
$ManagedCodexSkillContracts = @(
  [ordered]@{
    name = 'global-task-orchestrator'
    source_dir = 'skills/global-task-orchestrator'
    source_label = 'skills/global-task-orchestrator'
    required_files = @('SKILL.md','agents/openai.yaml','scripts/bootstrap-task.ps1')
  },
  [ordered]@{
    name = 'command-failure-memory'
    source_dir = 'skills/command-failure-memory'
    source_label = 'skills/command-failure-memory'
    required_files = @('SKILL.md','scripts/command-failure-memory.cmd','scripts/command-failure-memory.py','scripts/command-failure-memory.ps1')
  },
  [ordered]@{
    name = 'pre-dev-benchmark'
    source_dir = 'skills/pre-dev-benchmark'
    source_label = 'skills/pre-dev-benchmark'
    required_files = @('SKILL.md','agents/openai.yaml','references/benchmark-design.md','assets/benchmark-plan.template.md','assets/fixture-matrix.template.md','assets/runbook.template.md','scripts/scaffold_benchmark.py')
  }
)
$ExpectedManifestTargets = [ordered]@{
  SessionStart     = 'session_start'
  UserPromptSubmit = 'user_prompt_submit'
  PreToolUse       = 'pre_tool_use'
  PostToolUse      = 'post_tool_use'
  Stop             = 'stop'
  SubagentStop     = 'subagent_stop'
}

function Get-RepoRoot {
  param([string]$ScriptPath)
  if ($Root -ne "") {
    return (Resolve-Path $Root).Path
  }
  $p = Resolve-Path $ScriptPath
  return (Split-Path (Split-Path $p))
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

$script:PathNativeAvailable = $false
$script:PathNativeFailureReason = ''
$script:WindowsPathSafetyRequired = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
if ($script:WindowsPathSafetyRequired -and ($env:AI_HARNESS_DISABLE_NATIVE_PATH -eq '1')) {
  $script:PathNativeAvailable = $false
  $script:PathNativeFailureReason = 'disabled by AI_HARNESS_DISABLE_NATIVE_PATH'
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
  $fullRoot = [System.IO.Path]::GetFullPath($RootPath).TrimEnd('\', '/')
  $fullCandidate = [System.IO.Path]::GetFullPath($CandidatePath)
  if ($fullCandidate.Length -le $fullRoot.Length) {
    return
  }
  $relativeRemainder = $fullCandidate.Substring($fullRoot.Length).TrimStart('\', '/')
  if ([string]::IsNullOrWhiteSpace($relativeRemainder)) {
    return
  }
  $currentPath = $fullRoot
  foreach ($segment in ($relativeRemainder -split '[\\/]')) {
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

function Get-ExpectedManifestTargetValue {
  param([string]$EventName)
  if (-not $ExpectedManifestTargets.Contains($EventName)) {
    throw "Unexpected manifest event id: $EventName"
  }
  return [string]$ExpectedManifestTargets[$EventName]
}

function Get-ExpectedRuntimeRelativePath {
  param([string]$EventName)
  return ('scripts/{0}.ps1' -f (Get-ExpectedManifestTargetValue -EventName $EventName))
}

function Get-PathStatuses {
  param([string]$RepoRoot, [string[]]$Paths)
  $result = @()
  foreach ($rel in $Paths) {
    $full = Join-Path $RepoRoot $rel
    $exists = Test-Path $full
    $kind = "file"
    if ($exists -and (Get-Item $full).PSIsContainer) {
      $kind = "dir"
    }
    $result += [ordered]@{
      path = $rel
      exists = $exists
      kind = $kind
    }
  }
  return $result
}

function Get-TextFiles {
  param([string]$RepoRoot, [string[]]$Roots)
  $files = New-Object System.Collections.Generic.List[string]
  foreach ($entry in $Roots) {
    $target = if ([System.IO.Path]::IsPathRooted($entry)) { $entry } else { Join-Path $RepoRoot $entry }
    if (-not (Test-Path $target)) { continue }
    $item = Get-Item $target
    if (-not $item.PSIsContainer) {
      $files.Add($item.FullName) | Out-Null
      continue
    }
    Get-ChildItem -Path $item.FullName -Recurse -File | ForEach-Object {
      if (@('.md','.txt','.json','.yml','.yaml','.py','.ps1') -contains $_.Extension.ToLower()) {
        $files.Add($_.FullName) | Out-Null
      }
    }
  }
  return $files
}

function Get-LegacyMarkerCounts {
  param([string]$RepoRoot, [string[]]$Markers, [string[]]$Roots)
  $counts = @{}
  foreach ($m in $Markers) { $counts[$m] = 0 }
  if ($Markers.Count -eq 0) { return $counts }
  foreach ($file in (Get-TextFiles -RepoRoot $RepoRoot -Roots $Roots)) {
    try {
      $content = Get-Content -Path $file -Raw -Encoding UTF8
    } catch {
      continue
    }
    foreach ($m in $Markers) {
      $counts[$m] += ([regex]::Matches($content, [regex]::Escape($m))).Count
    }
  }
  return $counts
}

function Parse-FrontMatter {
  param([string]$Content)
  $match = [regex]::Match($Content, '^---\r?\n(.*?)\r?\n---\r?\n?', [System.Text.RegularExpressions.RegexOptions]::Singleline)
  if (-not $match.Success) {
    return [ordered]@{ metadata = $null; body = $Content }
  }
  $metadata = @{}
  $lines = $match.Groups[1].Value -split "`r?`n"
  foreach ($rawLine in $lines) {
    $line = $rawLine.Trim()
    if ($line -eq "" -or -not $line.Contains(':')) { continue }
    $parts = $line.Split(':', 2)
    $metadata[$parts[0].Trim()] = $parts[1].Trim()
  }
  return [ordered]@{ metadata = $metadata; body = $Content.Substring($match.Length) }
}

function Parse-KeyValueRecords {
  param([string]$Body, [string]$PrimaryKey)
  $records = New-Object System.Collections.Generic.List[hashtable]
  $current = $null
  $lines = $Body -split "`r?`n"
  foreach ($rawLine in $lines) {
    $line = $rawLine.Trim()
    if ($line -eq "" -or $line.StartsWith('#')) { continue }
    $match = [regex]::Match($line, '^-?\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$')
    if (-not $match.Success) { continue }
    $key = $match.Groups[1].Value.Trim()
    $value = $match.Groups[2].Value.Trim()
    if ($key -eq $PrimaryKey) {
      if ($null -ne $current) { $records.Add($current) | Out-Null }
      $current = @{}
      $current[$key] = $value
      continue
    }
    if ($null -ne $current) { $current[$key] = $value }
  }
  if ($null -ne $current) { $records.Add($current) | Out-Null }
  return $records
}

function Normalize-PathReference {
  param([string]$RawPath)
  $candidate = $RawPath.Trim().Trim('`').Trim("'").Trim('"')
  if ($candidate.EndsWith(',') -or $candidate.EndsWith('.')) {
    $candidate = $candidate.Substring(0, $candidate.Length - 1).TrimEnd()
  }
  $match = [regex]::Match($candidate, '.*\(([^)]+)\)\s*$')
  if ($match.Success) { $candidate = $match.Groups[1].Value.Trim() }
  if ($candidate.ToLower().StartsWith('file:')) { $candidate = $candidate.Substring(5).Trim() }
  return $candidate
}

function Test-IsPlaceholder {
  param([string]$Value)
  if ($null -eq $Value) { return $true }
  return @('', '-', '待补充', 'tbd', 'n/a', 'none') -contains $Value.Trim().ToLower()
}

function Test-IsLocalPathReference {
  param([string]$RawPath)
  if ($null -eq $RawPath) { return $false }
  $candidate = Normalize-PathReference -RawPath $RawPath
  if (Test-IsPlaceholder -Value $candidate) { return $false }
  $lower = $candidate.ToLower()
  if ([regex]::IsMatch($lower, '^[a-z][a-z0-9+.-]*://')) { return $false }
  if ($lower.StartsWith('link:') -or $lower.StartsWith('cmd:') -or $lower.StartsWith('ssh ') -or $lower.StartsWith('scp ')) { return $false }
  if ($candidate.Contains('*') -or $candidate.Contains('?')) { return $false }
  return $true
}

function Resolve-LocalPath {
  param([string]$RepoRoot, [string]$RawPath)
  $candidate = Normalize-PathReference -RawPath $RawPath
  if ([System.IO.Path]::IsPathRooted($candidate)) { return $candidate }
  return Join-Path $RepoRoot $candidate
}

function Get-SessionAudit {
  param([string]$RepoRoot)
  $sessionsRoot = Join-Path $RepoRoot '.ai\session'
  $legacySessions = New-Object System.Collections.Generic.List[object]
  $missingDocuments = New-Object System.Collections.Generic.List[object]
  $missingMetaFields = New-Object System.Collections.Generic.List[object]
  $invalidDocTypes = New-Object System.Collections.Generic.List[object]
  $invalidTaskIds = New-Object System.Collections.Generic.List[object]
  $invalidStatuses = New-Object System.Collections.Generic.List[object]
  $stepIdMismatches = New-Object System.Collections.Generic.List[object]
  $missingPathReferences = New-Object System.Collections.Generic.List[object]
  $requiredDocs = [ordered]@{ 'task_plan.md'='task_plan'; 'findings.md'='findings'; 'progress.md'='progress' }
  $requiredMeta = @('task_id','plan_id','doc_type','owner','status','updated_at')
  $docStatusEnum = @('todo','in_progress','blocked','done')
  $stepStatusEnum = @('todo','in_progress','blocked','done')
  $scanned = 0
  if (-not (Test-Path $sessionsRoot)) {
    return [ordered]@{ scanned=0; legacy_sessions=@(); missing_documents=@(); missing_meta_fields=@(); invalid_doc_types=@(); invalid_task_ids=@(); invalid_statuses=@(); step_id_mismatches=@(); missing_path_references=@() }
  }
  Get-ChildItem -Path $sessionsRoot -Directory | ForEach-Object {
    $sessionDir = $_
    $parsedDocs = @{}
    $hasAnyDoc = $false
    $isStructured = $false
    foreach ($filename in $requiredDocs.Keys) {
      $docPath = Join-Path $sessionDir.FullName $filename
      if (-not (Test-Path $docPath)) { continue }
      $hasAnyDoc = $true
      try { $content = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8 } catch {
        $missingMetaFields.Add([ordered]@{ session=($sessionDir.FullName.Replace($RepoRoot + '\','').Replace('\','/')); document=($docPath.Replace($RepoRoot + '\','').Replace('\','/')); missing_fields=$requiredMeta }) | Out-Null
        continue
      }
      $parsed = Parse-FrontMatter -Content $content
      if ($null -ne $parsed.metadata) { $isStructured = $true }
      $parsedDocs[$filename] = [ordered]@{ path=$docPath; metadata=$parsed.metadata; body=$parsed.body; expected_doc_type=$requiredDocs[$filename] }
    }
    if (-not $hasAnyDoc) { return }
    $scanned += 1
    $sessionRelative = $sessionDir.FullName.Replace($RepoRoot + '\','').Replace('\','/')
    if (-not $isStructured) {
      $legacySessions.Add($sessionRelative) | Out-Null
      return
    }
    foreach ($filename in $requiredDocs.Keys) {
      if (-not $parsedDocs.ContainsKey($filename)) {
        $missingDocuments.Add([ordered]@{ session=$sessionRelative; document=((Join-Path $sessionDir.FullName $filename).Replace($RepoRoot + '\','').Replace('\','/')) }) | Out-Null
        continue
      }
      $parsedDoc = $parsedDocs[$filename]
      $metadata = $parsedDoc.metadata
      $documentRelative = $parsedDoc.path.Replace($RepoRoot + '\','').Replace('\','/')
      $missing = @()
      foreach ($field in $requiredMeta) {
        if ($null -eq $metadata -or -not $metadata.ContainsKey($field) -or (Test-IsPlaceholder -Value $metadata[$field])) { $missing += $field }
      }
      if ($missing.Count -gt 0) {
        $missingMetaFields.Add([ordered]@{ session=$sessionRelative; document=$documentRelative; missing_fields=$missing }) | Out-Null
        continue
      }
      if ($metadata['doc_type'] -ne $parsedDoc.expected_doc_type) {
        $invalidDocTypes.Add([ordered]@{ session=$sessionRelative; document=$documentRelative; expected=$parsedDoc.expected_doc_type; actual=$metadata['doc_type'] }) | Out-Null
      }
      if ($metadata['task_id'] -ne $sessionDir.Name) {
        $invalidTaskIds.Add([ordered]@{ session=$sessionRelative; document=$documentRelative; expected=$sessionDir.Name; actual=$metadata['task_id'] }) | Out-Null
      }
      if ($docStatusEnum -notcontains $metadata['status']) {
        $invalidStatuses.Add([ordered]@{ session=$sessionRelative; document=$documentRelative; field='status'; value=$metadata['status'] }) | Out-Null
      }
    }
    $planStepIds = New-Object System.Collections.Generic.HashSet[string]
    if ($parsedDocs.ContainsKey('task_plan.md') -and $null -ne $parsedDocs['task_plan.md'].metadata) {
      $planDoc = $parsedDocs['task_plan.md']
      $stepRecords = Parse-KeyValueRecords -Body $planDoc.body -PrimaryKey 'step_id'
      $planRelative = $planDoc.path.Replace($RepoRoot + '\','').Replace('\','/')
      foreach ($record in $stepRecords) {
        $stepId = if ($record.ContainsKey('step_id')) { $record['step_id'] } else { '' }
        if (Test-IsPlaceholder -Value $stepId) { continue }
        $null = $planStepIds.Add($stepId)
        $status = if ($record.ContainsKey('status')) { $record['status'] } else { '' }
        if ($stepStatusEnum -notcontains $status) {
          $invalidStatuses.Add([ordered]@{ session=$sessionRelative; document=$planRelative; field=('step:' + $stepId); value=$status }) | Out-Null
        }
      }
    }
    foreach ($filename in @('findings.md','progress.md')) {
      if (-not $parsedDocs.ContainsKey($filename)) { continue }
      $doc = $parsedDocs[$filename]
      if ($null -eq $doc.metadata) { continue }
      $docRelative = $doc.path.Replace($RepoRoot + '\','').Replace('\','/')
      $entries = Parse-KeyValueRecords -Body $doc.body -PrimaryKey 'entry_id'
      foreach ($record in $entries) {
        $stepId = if ($record.ContainsKey('step_id')) { $record['step_id'] } else { $null }
        if ($null -ne $stepId -and -not (Test-IsPlaceholder -Value $stepId)) {
          if (-not $planStepIds.Contains($stepId)) {
            $stepIdMismatches.Add([ordered]@{ session=$sessionRelative; document=$docRelative; step_id=$stepId }) | Out-Null
          }
        }
        $rawPath = if ($record.ContainsKey('path')) { $record['path'] } else { $null }
        if ($null -ne $rawPath -and (Test-IsLocalPathReference -RawPath $rawPath)) {
          $resolved = Resolve-LocalPath -RepoRoot $RepoRoot -RawPath $rawPath
          if (-not (Test-Path $resolved)) {
            $missingPathReferences.Add([ordered]@{ session=$sessionRelative; document=$docRelative; path=(Normalize-PathReference -RawPath $rawPath) }) | Out-Null
          }
        }
      }
    }
  }
  return [ordered]@{ scanned=$scanned; legacy_sessions=$legacySessions.ToArray(); missing_documents=$missingDocuments.ToArray(); missing_meta_fields=$missingMetaFields.ToArray(); invalid_doc_types=$invalidDocTypes.ToArray(); invalid_task_ids=$invalidTaskIds.ToArray(); invalid_statuses=$invalidStatuses.ToArray(); step_id_mismatches=$stepIdMismatches.ToArray(); missing_path_references=$missingPathReferences.ToArray() }
}

function Get-WorkOrderAudit {
  param([string]$RepoRoot)
  $runsRoot = Join-Path $RepoRoot 'docs\ai\runs'
  $missingFields = New-Object System.Collections.Generic.List[object]
  $missingDispatch = New-Object System.Collections.Generic.List[object]
  $missingDispatchMessageRaw = New-Object System.Collections.Generic.List[object]
  $invalidWorkOrders = New-Object System.Collections.Generic.List[object]
  $requiredFields = @('change_spec','execution_steps','verification_steps')
  $scanned = 0
  if (-not (Test-Path $runsRoot)) {
    return [ordered]@{ scanned=0; missing_fields=@(); missing_dispatch_packets=@(); missing_dispatch_message_raw=@(); invalid_work_orders=@() }
  }
  Get-ChildItem -Path $runsRoot -Recurse -File -Filter *.json | Where-Object { $_.FullName -match '\\work_orders\\' } | ForEach-Object {
    $scanned += 1
    $relative = $_.FullName.Replace($RepoRoot + '\','').Replace('\','/')
    try {
      $raw = Get-Content -Path $_.FullName -Raw -Encoding UTF8
      $payload = $raw | ConvertFrom-Json
    } catch {
      $invalidWorkOrders.Add([ordered]@{ work_order=$relative; error=$_.Exception.Message }) | Out-Null
      return
    }
    $missing = @()
    foreach ($field in $requiredFields) {
      if ($null -eq $payload.$field -or ($payload.$field -is [System.Array] -and $payload.$field.Count -eq 0)) { $missing += $field }
    }
    if ($missing.Count -gt 0) {
      $missingFields.Add([ordered]@{ work_order=$relative; missing_fields=$missing }) | Out-Null
    }
    if ($null -eq $payload.dispatch_message_raw) {
      $missingDispatchMessageRaw.Add([ordered]@{ work_order=$relative }) | Out-Null
    }
    if ($null -ne $payload.dispatch_packet_path -and "$($payload.dispatch_packet_path)".Trim() -ne '') {
      $dispatchPath = Join-Path $RepoRoot $payload.dispatch_packet_path
      if (-not (Test-Path $dispatchPath)) {
        $missingDispatch.Add([ordered]@{ work_order=$relative; dispatch_packet_path=$payload.dispatch_packet_path }) | Out-Null
      }
    }
  }
  return [ordered]@{ scanned=$scanned; missing_fields=$missingFields.ToArray(); missing_dispatch_packets=$missingDispatch.ToArray(); missing_dispatch_message_raw=$missingDispatchMessageRaw.ToArray(); invalid_work_orders=$invalidWorkOrders.ToArray() }
}

function Resolve-CommandFilePath {
  param([string]$CommandText, [string]$BaseRoot)
  if ([string]::IsNullOrWhiteSpace($CommandText)) { return $null }
  $matchQuoted = [regex]::Match($CommandText, '-File\s+"([^"]+)"')
  if ($matchQuoted.Success) {
    $candidate = $matchQuoted.Groups[1].Value.Trim()
  } else {
    $matchPlain = [regex]::Match($CommandText, '-File\s+([^\s]+)')
    if (-not $matchPlain.Success) { return $null }
    $candidate = $matchPlain.Groups[1].Value.Trim().Trim("'").Trim('"')
  }
  if ([System.IO.Path]::IsPathRooted($candidate)) { return $candidate }
  if ([string]::IsNullOrWhiteSpace($BaseRoot)) { return $candidate }
  return Join-Path $BaseRoot $candidate
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
  param(
    [string]$RootPath,
    [string]$CandidatePath
  )
  $rootPrefix = Get-NormalizedDirectoryPrefix -PathValue $RootPath
  $fullCandidate = Get-CanonicalPath -PathValue $CandidatePath -AllowMissing
  $withinRoot = $fullCandidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
  if ($withinRoot) {
    Assert-NoReparsePointTraversal -RootPath $RootPath -CandidatePath $CandidatePath -Description 'runtime root path'
  }
  return $withinRoot
}

function Resolve-PathWithinRoot {
  param(
    [string]$RootPath,
    [string]$RelativePath
  )
  $normalizedRelative = ($RelativePath -replace '\\','/').TrimStart('/')
  $candidate = [System.IO.Path]::GetFullPath((Join-Path $RootPath ($normalizedRelative -replace '/', '\')))
  if (-not (Test-PathWithinRoot -RootPath $RootPath -CandidatePath $candidate)) {
    throw "Resolved path escapes runtime root: $RelativePath -> $candidate"
  }
  return $candidate
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
  Assert-NoReparsePointTraversal -RootPath $RootPath -CandidatePath $PathValue -Description 'runtime root path'
  return ($fullPath.Substring($rootPrefix.Length) -replace '\\', '/')
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
  return ([BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant()
}

function Get-ManifestScriptRuntimeRelativePath {
  param([object]$ManifestItem)
  $itemId = "$($ManifestItem['id'])"
  $targetValue = "$($ManifestItem['target'])".Replace('\','/').TrimStart('/')
  if ([string]::IsNullOrWhiteSpace($targetValue)) {
    throw "Manifest item target is empty: $itemId"
  }
  $expectedTarget = Get-ExpectedManifestTargetValue -EventName $itemId
  if ($targetValue -ne $expectedTarget) {
    throw ("Manifest item target mismatch for {0}: expected {1}, actual {2}" -f $itemId, $expectedTarget, $targetValue)
  }
  return (Get-ExpectedRuntimeRelativePath -EventName $itemId)
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
    if ($Map.PSObject.Methods.Name -contains 'ContainsKey') {
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

function Test-HooksStructure {
  param(
    [object]$HooksMap,
    [string]$ScopeName
  )
  $issues = New-Object System.Collections.Generic.List[object]
  $commands = New-Object System.Collections.Generic.List[object]
  $allowedEvents = $AllowedHookEvents
  $toolMatcher = '^(Bash|Write|Edit|MultiEdit)$'
  if ($null -eq $HooksMap -or -not ($HooksMap -is [System.Collections.IDictionary])) {
    $issues.Add([ordered]@{ scope=$ScopeName; type='hooks_root_type'; message='hooks root must be object' }) | Out-Null
    return [ordered]@{ issues=$issues.ToArray(); commands=$commands.ToArray() }
  }
  $unknownEvents = @((Get-MapKeys -Map $HooksMap) | Where-Object { $allowedEvents -notcontains [string]$_ })
  foreach ($unknownEvent in $unknownEvents) {
    $issues.Add([ordered]@{ scope=$ScopeName; type='unknown_event'; event=[string]$unknownEvent; message='hooks event is out of scope' }) | Out-Null
  }
  foreach ($eventName in $allowedEvents) {
    if (-not (Test-MapHasKey -Map $HooksMap -Key $eventName)) {
      $issues.Add([ordered]@{ scope=$ScopeName; type='missing_event'; event=$eventName; message='missing hooks event' }) | Out-Null
      continue
    }
    $eventEntries = @($HooksMap[$eventName])
    if ($eventEntries.Count -eq 0) {
      $issues.Add([ordered]@{ scope=$ScopeName; type='empty_event'; event=$eventName; message='event hooks array is empty' }) | Out-Null
      continue
    }
    for ($i = 0; $i -lt $eventEntries.Count; $i++) {
      $entry = $eventEntries[$i]
      if (-not ($entry -is [System.Collections.IDictionary])) {
        $issues.Add([ordered]@{ scope=$ScopeName; type='event_entry_type'; event=$eventName; index=$i; message='event entry must be object' }) | Out-Null
        continue
      }
      if (@('PreToolUse','PostToolUse') -contains $eventName) {
        if ("$($entry['matcher'])" -ne $toolMatcher) {
          $issues.Add([ordered]@{ scope=$ScopeName; type='matcher_mismatch'; event=$eventName; index=$i; expected=$toolMatcher; actual=$entry['matcher'] }) | Out-Null
        }
      }
      if (-not (Test-MapHasKey -Map $entry -Key 'hooks')) {
        $issues.Add([ordered]@{ scope=$ScopeName; type='missing_handlers'; event=$eventName; index=$i; message='event entry missing hooks handlers array' }) | Out-Null
        continue
      }
      $handlers = @($entry['hooks'])
      if ($handlers.Count -eq 0) {
        $issues.Add([ordered]@{ scope=$ScopeName; type='empty_handlers'; event=$eventName; index=$i; message='event entry hooks handlers array is empty' }) | Out-Null
        continue
      }
      for ($h = 0; $h -lt $handlers.Count; $h++) {
        $handler = $handlers[$h]
        if (-not ($handler -is [System.Collections.IDictionary])) {
          $issues.Add([ordered]@{ scope=$ScopeName; type='handler_type'; event=$eventName; index=$i; handler_index=$h; message='handler must be object' }) | Out-Null
          continue
        }
        if ("$($handler['type'])" -ne 'command') {
          $issues.Add([ordered]@{ scope=$ScopeName; type='handler_command_type'; event=$eventName; index=$i; handler_index=$h; expected='command'; actual=$handler['type'] }) | Out-Null
        }
        if ("$($handler['shell'])" -ne 'powershell') {
          $issues.Add([ordered]@{ scope=$ScopeName; type='handler_shell'; event=$eventName; index=$i; handler_index=$h; expected='powershell'; actual=$handler['shell'] }) | Out-Null
        }
        $commandText = "$($handler['command'])"
        if ([string]::IsNullOrWhiteSpace($commandText)) {
          $issues.Add([ordered]@{ scope=$ScopeName; type='handler_command_missing'; event=$eventName; index=$i; handler_index=$h; message='handler command is empty' }) | Out-Null
        } else {
          $commands.Add([ordered]@{ scope=$ScopeName; event=$eventName; index=$i; handler_index=$h; command=$commandText }) | Out-Null
        }
      }
    }
  }
  return [ordered]@{ issues=$issues.ToArray(); commands=$commands.ToArray() }
}

function Get-JsonMapFromFile {
  param(
    [string]$PathValue,
    [string]$ScopeName
  )
  if (-not (Test-Path -LiteralPath $PathValue)) {
    return [ordered]@{ ok=$false; exists=$false; data=$null; error='file_not_found'; scope=$ScopeName; path=$PathValue }
  }
  try {
    $raw = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
      return [ordered]@{ ok=$true; exists=$true; data=[ordered]@{}; error=''; scope=$ScopeName; path=$PathValue }
    }
    if (-not $raw.TrimStart().StartsWith('{')) {
      return [ordered]@{ ok=$false; exists=$true; data=$null; error='json_root_not_object'; scope=$ScopeName; path=$PathValue }
    }
    $parsed = ConvertTo-NormalizedMap -InputObject ($raw | ConvertFrom-Json)
    if ($null -eq $parsed) { $parsed = [ordered]@{} }
    if (-not ($parsed -is [System.Collections.IDictionary])) {
      return [ordered]@{ ok=$false; exists=$true; data=$null; error='json_root_not_object'; scope=$ScopeName; path=$PathValue }
    }
    return [ordered]@{ ok=$true; exists=$true; data=$parsed; error=''; scope=$ScopeName; path=$PathValue }
  } catch {
    return [ordered]@{ ok=$false; exists=$true; data=$null; error=$_.Exception.Message; scope=$ScopeName; path=$PathValue }
  }
}

function Get-CodexManagedFileSpecs {
  param(
    [string]$SkillRoot,
    [string]$ManagedSkillName,
    [string]$SourcePrefix
  )
  $specs = New-Object System.Collections.Generic.List[object]
  if (-not (Test-Path -LiteralPath $SkillRoot)) {
    return $specs.ToArray()
  }
  Get-ChildItem -LiteralPath $SkillRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
    $relative = Get-RelativePathWithinRoot -RootPath $SkillRoot -PathValue $_.FullName
    $specs.Add([ordered]@{
      source = ("{0}/{1}" -f $SourcePrefix, $relative)
      target = ("{0}/{1}" -f $ManagedSkillName, $relative)
      sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
      path   = $_.FullName
    }) | Out-Null
  }
  return $specs.ToArray()
}

function Get-ReceiptManagedSkillNames {
  param([System.Collections.IDictionary]$ReceiptData)
  $skillNames = New-Object System.Collections.Generic.List[string]
  if ($null -eq $ReceiptData) {
    return @()
  }
  if (Test-MapHasKey -Map $ReceiptData -Key 'managed_skills') {
    foreach ($entry in @($ReceiptData['managed_skills'])) {
      if ($null -eq $entry) { continue }
      $name = ''
      if ($entry -is [System.Collections.IDictionary]) {
        $name = [string]$entry['name']
      } else {
        $name = [string]$entry
      }
      if ((-not [string]::IsNullOrWhiteSpace($name)) -and (-not $skillNames.Contains($name))) {
        $skillNames.Add($name) | Out-Null
      }
    }
  }
  if (($skillNames.Count -eq 0) -and (Test-MapHasKey -Map $ReceiptData -Key 'managed_skill_name')) {
    $legacyName = [string]$ReceiptData['managed_skill_name']
    if (-not [string]::IsNullOrWhiteSpace($legacyName)) {
      $skillNames.Add($legacyName) | Out-Null
    }
  }
  return @($skillNames | Sort-Object)
}

function Get-CodexSkillAudit {
  param(
    [string]$RepoRoot,
    [string]$CodexHomeValue,
    [string]$RuntimeRoot,
    [string]$ReceiptPath,
    [object]$ManagedSkillContract,
    [object]$ReceiptResult
  )
  $managedSkillName = [string]$ManagedSkillContract['name']
  $sourceDirRel = [string]$ManagedSkillContract['source_dir']
  if ([string]::IsNullOrWhiteSpace($sourceDirRel)) {
    $sourceDirRel = ("skills/{0}" -f $managedSkillName)
  }
  $sourceLabel = [string]$ManagedSkillContract['source_label']
  if ([string]::IsNullOrWhiteSpace($sourceLabel)) {
    $sourceLabel = ("skills/{0}" -f $managedSkillName)
  }
  $requiredFiles = @($ManagedSkillContract['required_files'])
  $sourceIssues = New-Object System.Collections.Generic.List[object]
  $runtimeIssues = New-Object System.Collections.Generic.List[object]
  $receiptIssues = New-Object System.Collections.Generic.List[object]

  $sourceSkillDir = Join-Path $RepoRoot ($sourceDirRel -replace '/', '\')
  $runtimeSkillDir = Join-Path $RuntimeRoot $managedSkillName

  $sourceSpecs = @()
  $expectedTargets = @{}
  if (-not (Test-Path -LiteralPath $sourceSkillDir)) {
    $sourceIssues.Add([ordered]@{ type='source_managed_skill_missing'; path=$sourceSkillDir; skill=$managedSkillName }) | Out-Null
  } else {
    try {
      $sourceSpecs = @(Get-CodexManagedFileSpecs -SkillRoot $sourceSkillDir -ManagedSkillName $managedSkillName -SourcePrefix $sourceLabel)
      foreach ($spec in $sourceSpecs) {
        $expectedTargets[[string]$spec['target']] = $spec
      }
      foreach ($requiredRel in $requiredFiles) {
        $requiredPath = Join-Path $sourceSkillDir ($requiredRel -replace '/', '\')
        if (-not (Test-Path -LiteralPath $requiredPath)) {
          $sourceIssues.Add([ordered]@{ type='source_required_file_missing'; path=$requiredPath; relative_path=$requiredRel; skill=$managedSkillName }) | Out-Null
        }
      }
    } catch {
      $sourceIssues.Add([ordered]@{ type='source_managed_skill_enumeration_failed'; path=$sourceSkillDir; error=$_.Exception.Message; skill=$managedSkillName }) | Out-Null
    }
  }

  $runtimeHashes = @{}
  if (-not (Test-Path -LiteralPath $runtimeSkillDir)) {
    $runtimeIssues.Add([ordered]@{ type='runtime_managed_skill_missing'; path=$runtimeSkillDir; skill=$managedSkillName }) | Out-Null
  } else {
    try {
      Get-ChildItem -LiteralPath $runtimeSkillDir -Recurse -File | Sort-Object FullName | ForEach-Object {
        $relative = Get-RelativePathWithinRoot -RootPath $runtimeSkillDir -PathValue $_.FullName
        $target = ("{0}/{1}" -f $managedSkillName, $relative)
        $runtimeHashes[$target] = [ordered]@{
          path = $_.FullName
          sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
      }
    } catch {
      $runtimeIssues.Add([ordered]@{ type='runtime_managed_skill_enumeration_failed'; path=$runtimeSkillDir; error=$_.Exception.Message; skill=$managedSkillName }) | Out-Null
    }
  }

  $receiptTargets = @{}
  $receiptHasManagedFiles = $false
  if (-not $ReceiptResult.exists) {
    $receiptIssues.Add([ordered]@{ type='receipt_missing'; path=$ReceiptPath; skill=$managedSkillName }) | Out-Null
  } elseif (-not $ReceiptResult.ok) {
    $receiptIssues.Add([ordered]@{ type='receipt_invalid'; path=$ReceiptPath; error=$ReceiptResult.error; skill=$managedSkillName }) | Out-Null
  } else {
    $receiptData = $ReceiptResult.data
    if ("$($receiptData['harness_root'])" -ne $RepoRoot) {
      $receiptIssues.Add([ordered]@{ type='receipt_harness_root_mismatch'; expected=$RepoRoot; actual=$receiptData['harness_root']; skill=$managedSkillName }) | Out-Null
    }
    if ("$($receiptData['codex_home'])" -ne $CodexHomeValue) {
      $receiptIssues.Add([ordered]@{ type='receipt_codex_home_mismatch'; expected=$CodexHomeValue; actual=$receiptData['codex_home']; skill=$managedSkillName }) | Out-Null
    }
    if ("$($receiptData['runtime_root'])" -ne $RuntimeRoot) {
      $receiptIssues.Add([ordered]@{ type='receipt_runtime_root_mismatch'; expected=$RuntimeRoot; actual=$receiptData['runtime_root']; skill=$managedSkillName }) | Out-Null
    }
    if (-not (Test-MapHasKey -Map $receiptData -Key 'managed_files')) {
      $receiptIssues.Add([ordered]@{ type='receipt_missing_managed_files'; path=$ReceiptPath; skill=$managedSkillName }) | Out-Null
    } else {
      $receiptHasManagedFiles = $true
      $managedFiles = @($receiptData['managed_files'])
      if ($managedFiles.Count -eq 0) {
        $receiptIssues.Add([ordered]@{ type='receipt_managed_files_empty'; path=$ReceiptPath; skill=$managedSkillName }) | Out-Null
      }
      foreach ($managed in $managedFiles) {
        if ($null -eq $managed -or -not ($managed -is [System.Collections.IDictionary])) {
          $receiptIssues.Add([ordered]@{ type='receipt_managed_file_type'; path=$ReceiptPath; message='managed_files item must be object'; skill=$managedSkillName }) | Out-Null
          continue
        }
        $targetRel = "$($managed['target'])".Replace('\','/').TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($targetRel)) {
          $receiptIssues.Add([ordered]@{ type='receipt_managed_file_missing_target'; path=$ReceiptPath; skill=$managedSkillName }) | Out-Null
          continue
        }
        if (($targetRel -ne $managedSkillName) -and (-not $targetRel.StartsWith(("{0}/" -f $managedSkillName)))) {
          continue
        }
        try {
          $resolvedTarget = Resolve-PathWithinRoot -RootPath $RuntimeRoot -RelativePath $targetRel
        } catch {
          $receiptIssues.Add([ordered]@{ type='receipt_target_out_of_runtime_root'; target=$targetRel; runtime_root=$RuntimeRoot; error=$_.Exception.Message; skill=$managedSkillName }) | Out-Null
          continue
        }
        $receiptTargets[$targetRel] = [ordered]@{
          entry = $managed
          resolved_path = $resolvedTarget
        }
        if (-not (Test-Path -LiteralPath $resolvedTarget)) {
          $receiptIssues.Add([ordered]@{ type='receipt_target_missing'; target=$targetRel; resolved_path=$resolvedTarget; skill=$managedSkillName }) | Out-Null
          continue
        }
        $expectedSha = "$($managed['sha256'])".ToLowerInvariant()
        if ([string]::IsNullOrWhiteSpace($expectedSha)) {
          $receiptIssues.Add([ordered]@{ type='receipt_target_sha256_missing'; target=$targetRel; resolved_path=$resolvedTarget; skill=$managedSkillName }) | Out-Null
          continue
        }
        $actualSha = (Get-FileHash -LiteralPath $resolvedTarget -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualSha -ne $expectedSha) {
          $receiptIssues.Add([ordered]@{ type='receipt_target_sha256_mismatch'; target=$targetRel; expected=$expectedSha; actual=$actualSha; resolved_path=$resolvedTarget; skill=$managedSkillName }) | Out-Null
        }
      }
    }
  }

  if (($runtimeHashes.Count -gt 0) -and (-not $ReceiptResult.exists)) {
    $runtimeIssues.Add([ordered]@{ type='runtime_unmanaged_conflict'; path=$runtimeSkillDir; receipt_path=$ReceiptPath; skill=$managedSkillName }) | Out-Null
  }

  foreach ($expectedTarget in $expectedTargets.Keys) {
    $spec = $expectedTargets[$expectedTarget]
    if (-not $runtimeHashes.ContainsKey($expectedTarget)) {
      $runtimeIssues.Add([ordered]@{ type='runtime_managed_file_missing'; target=$expectedTarget; expected_path=(Join-Path $RuntimeRoot ($expectedTarget -replace '/', '\')); skill=$managedSkillName }) | Out-Null
    } else {
      $runtimeEntry = $runtimeHashes[$expectedTarget]
      if ("$($runtimeEntry['sha256'])" -ne "$($spec['sha256'])") {
        $runtimeIssues.Add([ordered]@{ type='runtime_managed_file_drift'; target=$expectedTarget; source_path=$spec['path']; runtime_path=$runtimeEntry['path']; expected="$($spec['sha256'])"; actual="$($runtimeEntry['sha256'])"; skill=$managedSkillName }) | Out-Null
      }
    }
    if ($receiptHasManagedFiles) {
      if (-not $receiptTargets.ContainsKey($expectedTarget)) {
        $receiptIssues.Add([ordered]@{ type='receipt_missing_required_target'; target=$expectedTarget; skill=$managedSkillName }) | Out-Null
      } else {
        $receiptEntry = $receiptTargets[$expectedTarget]['entry']
        $receiptSource = "$($receiptEntry['source'])".Replace('\','/').TrimStart('/')
        $receiptSha = "$($receiptEntry['sha256'])".ToLowerInvariant()
        if ($receiptSource -ne "$($spec['source'])") {
          $receiptIssues.Add([ordered]@{ type='receipt_source_path_mismatch'; target=$expectedTarget; expected="$($spec['source'])"; actual=$receiptSource; skill=$managedSkillName }) | Out-Null
        }
        if ($receiptSha -ne "$($spec['sha256'])") {
          $receiptIssues.Add([ordered]@{ type='receipt_source_sha256_mismatch'; target=$expectedTarget; expected="$($spec['sha256'])"; actual=$receiptSha; skill=$managedSkillName }) | Out-Null
        }
      }
    }
  }

  foreach ($runtimeTarget in $runtimeHashes.Keys) {
    if (-not $expectedTargets.ContainsKey($runtimeTarget)) {
      $runtimeIssues.Add([ordered]@{ type='runtime_unexpected_managed_file'; target=$runtimeTarget; runtime_path=$runtimeHashes[$runtimeTarget]['path']; skill=$managedSkillName }) | Out-Null
    }
  }

  foreach ($receiptTarget in $receiptTargets.Keys) {
    if (-not $expectedTargets.ContainsKey($receiptTarget)) {
      $receiptIssues.Add([ordered]@{ type='receipt_unexpected_target'; target=$receiptTarget; resolved_path=$receiptTargets[$receiptTarget]['resolved_path']; skill=$managedSkillName }) | Out-Null
    }
  }

  return [ordered]@{
    managed_skill_name = $managedSkillName
    source = [ordered]@{
      harness_root = $RepoRoot
      managed_skill_path = $sourceSkillDir
    }
    runtime = [ordered]@{
      codex_home = $CodexHomeValue
      runtime_root = $RuntimeRoot
      managed_skill_path = $runtimeSkillDir
      receipt_path = $ReceiptPath
    }
    source_issues = $sourceIssues.ToArray()
    runtime_issues = $runtimeIssues.ToArray()
    receipt_issues = $receiptIssues.ToArray()
    ok = ($sourceIssues.Count -eq 0 -and $runtimeIssues.Count -eq 0 -and $receiptIssues.Count -eq 0)
  }
}

function Get-CodexAudit {
  param(
    [string]$RepoRoot,
    [string]$CodexHomeValue
  )
  $runtimeRoot = Join-Path $CodexHomeValue 'skills'
  $receiptPath = Join-Path $CodexHomeValue '.ai-harness\codex-sync.receipt.json'
  $receiptResult = Get-JsonMapFromFile -PathValue $receiptPath -ScopeName 'codex_receipt'
  $managedSkillNames = @($ManagedCodexSkillContracts | ForEach-Object { [string]$_['name'] } | Sort-Object)

  $skillAudits = New-Object System.Collections.Generic.List[object]
  $sourceIssues = New-Object System.Collections.Generic.List[object]
  $runtimeIssues = New-Object System.Collections.Generic.List[object]
  $receiptIssues = New-Object System.Collections.Generic.List[object]

  foreach ($managedSkillContract in @($ManagedCodexSkillContracts)) {
    $skillAudit = Get-CodexSkillAudit -RepoRoot $RepoRoot -CodexHomeValue $CodexHomeValue -RuntimeRoot $runtimeRoot -ReceiptPath $receiptPath -ManagedSkillContract $managedSkillContract -ReceiptResult $receiptResult
    $skillAudits.Add($skillAudit) | Out-Null
    foreach ($issue in @($skillAudit.source_issues)) {
      $sourceIssues.Add($issue) | Out-Null
    }
    foreach ($issue in @($skillAudit.runtime_issues)) {
      $runtimeIssues.Add($issue) | Out-Null
    }
    foreach ($issue in @($skillAudit.receipt_issues)) {
      $receiptIssues.Add($issue) | Out-Null
    }
  }

  if ($receiptResult.exists -and $receiptResult.ok) {
    $receiptData = $receiptResult.data
    $receiptManagedSkills = @(Get-ReceiptManagedSkillNames -ReceiptData $receiptData)
    if ($receiptManagedSkills.Count -eq 0) {
      $receiptIssues.Add([ordered]@{ type='receipt_missing_managed_skills'; path=$receiptPath }) | Out-Null
    } elseif ((($receiptManagedSkills | ConvertTo-Json -Compress) -ne ($managedSkillNames | ConvertTo-Json -Compress))) {
      $receiptIssues.Add([ordered]@{ type='receipt_managed_skills_mismatch'; expected=$managedSkillNames; actual=$receiptManagedSkills; path=$receiptPath }) | Out-Null
    }

    if (Test-MapHasKey -Map $receiptData -Key 'managed_files') {
      foreach ($managed in @($receiptData['managed_files'])) {
        if ($null -eq $managed -or -not ($managed -is [System.Collections.IDictionary])) {
          continue
        }
        $targetRel = "$($managed['target'])".Replace('\','/').TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($targetRel)) {
          continue
        }
        try {
          $null = Resolve-PathWithinRoot -RootPath $runtimeRoot -RelativePath $targetRel
        } catch {
          $receiptIssues.Add([ordered]@{ type='receipt_target_out_of_runtime_root'; target=$targetRel; runtime_root=$runtimeRoot; error=$_.Exception.Message; path=$receiptPath }) | Out-Null
          continue
        }
        $isManagedTarget = $false
        foreach ($managedSkillName in $managedSkillNames) {
          if (($targetRel -eq $managedSkillName) -or $targetRel.StartsWith(("{0}/" -f $managedSkillName))) {
            $isManagedTarget = $true
            break
          }
        }
        if (-not $isManagedTarget) {
          $receiptIssues.Add([ordered]@{ type='receipt_unmanaged_skill_target'; target=$targetRel; path=$receiptPath }) | Out-Null
        }
      }
    }
  }

  return [ordered]@{
    managed_skills = $managedSkillNames
    skills = $skillAudits.ToArray()
    source_issues = $sourceIssues.ToArray()
    runtime_issues = $runtimeIssues.ToArray()
    receipt_issues = $receiptIssues.ToArray()
    ok = ($sourceIssues.Count -eq 0 -and $runtimeIssues.Count -eq 0 -and $receiptIssues.Count -eq 0)
  }
}

function Get-ClaudeHooksAudit {
  param(
    [string]$RepoRoot,
    [string]$ClaudeHomeValue
  )
  $allowedEvents = $AllowedHookEvents
  $sourceIssues = New-Object System.Collections.Generic.List[object]
  $runtimeIssues = New-Object System.Collections.Generic.List[object]
  $receiptIssues = New-Object System.Collections.Generic.List[object]
  $commandPathIssues = New-Object System.Collections.Generic.List[object]
  $missingSourceScripts = New-Object System.Collections.Generic.List[object]

  $sourceManifestPath = Join-Path $RepoRoot 'hooks\claude\manifest.json'
  $sourceSettingsTemplatePath = Join-Path $RepoRoot 'hooks\claude\settings.json'
  $sourceScriptsDir = Join-Path $RepoRoot 'hooks\claude\scripts'

  $claudeHome = if ([string]::IsNullOrWhiteSpace($ClaudeHomeValue)) { Join-Path $env:USERPROFILE '.claude' } else { $ClaudeHomeValue }
  $runtimeRoot = Join-Path $claudeHome '.ai-harness\hooks\claude'
  $runtimeManifestPath = Join-Path $runtimeRoot 'manifest.json'
  $runtimeTemplatePath = Join-Path $runtimeRoot 'settings.template.json'
  $runtimeSettingsPath = Join-Path $runtimeRoot 'settings.runtime.json'
  $settingsPath = Join-Path $claudeHome 'settings.json'
  $receiptPath = Join-Path $claudeHome '.ai-harness\claude-hooks.receipt.json'

  $manifestResult = Get-JsonMapFromFile -PathValue $sourceManifestPath -ScopeName 'source_manifest'
  if (-not $manifestResult.ok) {
    $sourceIssues.Add([ordered]@{ type='source_manifest_invalid'; path=$sourceManifestPath; error=$manifestResult.error }) | Out-Null
  }

  $templateResult = Get-JsonMapFromFile -PathValue $sourceSettingsTemplatePath -ScopeName 'source_settings_template'
  if (-not $templateResult.ok) {
    $sourceIssues.Add([ordered]@{ type='source_template_invalid'; path=$sourceSettingsTemplatePath; error=$templateResult.error }) | Out-Null
  }

  $manifestItems = @()
  $manifestRuntimeTargets = [ordered]@{}
  if ($manifestResult.ok) {
    $manifestData = $manifestResult.data
    if ("$($manifestData['runtime'])" -ne $ExpectedManifestRuntime) {
      $sourceIssues.Add([ordered]@{ type='source_manifest_runtime_mismatch'; expected=$ExpectedManifestRuntime; actual=$manifestData['runtime']; path=$sourceManifestPath }) | Out-Null
    }
    if (-not (Test-MapHasKey -Map $manifestData -Key 'items')) {
      $sourceIssues.Add([ordered]@{ type='source_manifest_missing_items'; path=$sourceManifestPath }) | Out-Null
    } else {
      $manifestItems = @($manifestData['items'])
      $seenIds = New-Object System.Collections.Generic.HashSet[string]
      foreach ($item in $manifestItems) {
        if ($null -eq $item -or -not ($item -is [System.Collections.IDictionary])) {
          $sourceIssues.Add([ordered]@{ type='source_manifest_item_type'; path=$sourceManifestPath; message='manifest item must be object' }) | Out-Null
          continue
        }
        $itemId = "$($item['id'])"
        $itemSource = "$($item['source'])"
        if ([string]::IsNullOrWhiteSpace($itemId)) {
          $sourceIssues.Add([ordered]@{ type='source_manifest_item_missing_id'; source=$itemSource }) | Out-Null
        } else {
          if (-not $seenIds.Add($itemId)) {
            $sourceIssues.Add([ordered]@{ type='source_manifest_duplicate_id'; id=$itemId }) | Out-Null
          }
          if ($allowedEvents -notcontains $itemId) {
            $sourceIssues.Add([ordered]@{ type='source_manifest_out_of_scope_id'; id=$itemId }) | Out-Null
          }
        }
        if ([string]::IsNullOrWhiteSpace($itemSource)) {
          $sourceIssues.Add([ordered]@{ type='source_manifest_item_missing_source'; id=$itemId }) | Out-Null
        } else {
          try {
            $sourceScriptPath = Resolve-PathAgainstRoot -RootPath $RepoRoot -PathValue $itemSource -Description ("manifest source for {0}" -f $itemId)
            if (-not (Test-Path -LiteralPath $sourceScriptPath)) {
              $missingSourceScripts.Add([ordered]@{ id=$itemId; source=$itemSource; resolved_path=$sourceScriptPath }) | Out-Null
            }
          } catch {
            $sourceIssues.Add([ordered]@{ type='source_manifest_source_out_of_root'; id=$itemId; source=$itemSource; error=$_.Exception.Message }) | Out-Null
          }
        }
        if (-not [string]::IsNullOrWhiteSpace($itemId)) {
          try {
            $manifestRuntimeTargets[$itemId] = Get-ManifestScriptRuntimeRelativePath -ManifestItem $item
          } catch {
            $sourceIssues.Add([ordered]@{ type='source_manifest_invalid_target'; id=$itemId; error=$_.Exception.Message }) | Out-Null
          }
        }
      }
      foreach ($eventName in $allowedEvents) {
        if (-not $seenIds.Contains($eventName)) {
          $sourceIssues.Add([ordered]@{ type='source_manifest_missing_event'; event=$eventName }) | Out-Null
        }
      }
    }
  }

  foreach ($eventName in $allowedEvents) {
    $scriptPath = Join-Path $sourceScriptsDir ("{0}.ps1" -f $eventName)
    if (-not (Test-Path -LiteralPath $scriptPath)) {
      $missingSourceScripts.Add([ordered]@{ id=$eventName; source=("hooks/claude/scripts/{0}.ps1" -f $eventName); resolved_path=$scriptPath }) | Out-Null
    }
  }
  $hookCommonPath = Join-Path $sourceScriptsDir 'HookCommon.ps1'
  if (-not (Test-Path -LiteralPath $hookCommonPath)) {
    $missingSourceScripts.Add([ordered]@{ id='HookCommon'; source='hooks/claude/scripts/HookCommon.ps1'; resolved_path=$hookCommonPath }) | Out-Null
  }
  $preToolUseScriptPath = Join-Path $sourceScriptsDir 'PreToolUse.ps1'
  if (Test-Path -LiteralPath $preToolUseScriptPath) {
    try {
      $preToolUseContent = Get-Content -LiteralPath $preToolUseScriptPath -Raw -Encoding UTF8
      $hookCommonContent = ""
      if (Test-Path -LiteralPath $hookCommonPath) {
        $hookCommonContent = Get-Content -LiteralPath $hookCommonPath -Raw -Encoding UTF8
      }
      if (-not $preToolUseContent.Contains('tool_not_allowed')) {
        $sourceIssues.Add([ordered]@{ type='pre_tool_use_guard_marker_missing'; path=$preToolUseScriptPath; marker='tool_not_allowed' }) | Out-Null
      }
      if (-not $preToolUseContent.Contains('allowedTools.Contains')) {
        $sourceIssues.Add([ordered]@{ type='pre_tool_use_allowlist_check_missing'; path=$preToolUseScriptPath; marker='allowedTools.Contains' }) | Out-Null
      }
      if ((-not $preToolUseContent.Contains('Resolve-ToolName')) -and (-not $hookCommonContent.Contains('function Resolve-ToolName'))) {
        $sourceIssues.Add([ordered]@{ type='pre_tool_use_tool_name_resolver_missing'; path=$preToolUseScriptPath; marker='Resolve-ToolName' }) | Out-Null
      }
    } catch {
      $sourceIssues.Add([ordered]@{ type='pre_tool_use_read_failed'; path=$preToolUseScriptPath; error=$_.Exception.Message }) | Out-Null
    }
  }

  $sourceHooksCommands = @()
  if ($templateResult.ok) {
    $templateData = $templateResult.data
    if (-not (Test-MapHasKey -Map $templateData -Key 'hooks')) {
      $sourceIssues.Add([ordered]@{ type='source_template_missing_hooks'; path=$sourceSettingsTemplatePath }) | Out-Null
    } else {
      $sourceHooksValidation = Test-HooksStructure -HooksMap $templateData['hooks'] -ScopeName 'source_template'
      foreach ($issue in $sourceHooksValidation.issues) { $sourceIssues.Add($issue) | Out-Null }
      $sourceHooksCommands = @($sourceHooksValidation.commands)
    }
  }

  foreach ($commandEntry in $sourceHooksCommands) {
    $commandPath = Resolve-CommandFilePath -CommandText $commandEntry.command -BaseRoot $RepoRoot
    if ($null -eq $commandPath) {
      $commandPathIssues.Add([ordered]@{ scope='source_template'; event=$commandEntry.event; command=$commandEntry.command; issue='cannot_resolve_file_path' }) | Out-Null
      continue
    }
    if (-not (Test-Path -LiteralPath $commandPath)) {
      $commandPathIssues.Add([ordered]@{ scope='source_template'; event=$commandEntry.event; command=$commandEntry.command; resolved_path=$commandPath; issue='command_file_missing' }) | Out-Null
    }
  }

  if (-not (Test-Path -LiteralPath $runtimeRoot)) {
    $runtimeIssues.Add([ordered]@{ type='runtime_root_missing'; path=$runtimeRoot }) | Out-Null
  }

  $runtimeRequired = @(
    [ordered]@{ id='runtime_manifest'; path=$runtimeManifestPath; rel='manifest.json' },
    [ordered]@{ id='runtime_template'; path=$runtimeTemplatePath; rel='settings.template.json' },
    [ordered]@{ id='runtime_settings'; path=$runtimeSettingsPath; rel='settings.runtime.json' },
    [ordered]@{ id='hook_common'; path=(Join-Path $runtimeRoot 'scripts\HookCommon.ps1'); rel='scripts/HookCommon.ps1' }
  )
  foreach ($eventName in $allowedEvents) {
    if ($manifestRuntimeTargets.Contains($eventName)) {
      $relativeTarget = $manifestRuntimeTargets[$eventName]
      try {
        $runtimeRequired += [ordered]@{ id=("script_" + $eventName); path=(Resolve-PathWithinRoot -RootPath $runtimeRoot -RelativePath $relativeTarget); rel=$relativeTarget }
      } catch {
        $sourceIssues.Add([ordered]@{ type='source_manifest_runtime_target_out_of_root'; event=$eventName; target=$relativeTarget; error=$_.Exception.Message }) | Out-Null
      }
    }
  }
  foreach ($required in $runtimeRequired) {
    if (-not (Test-Path -LiteralPath $required.path)) {
      $runtimeIssues.Add([ordered]@{ type='runtime_file_missing'; id=$required.id; path=$required.path }) | Out-Null
    }
  }

  if ((Test-Path -LiteralPath $sourceManifestPath) -and (Test-Path -LiteralPath $runtimeManifestPath)) {
    if ((Get-FileHash -LiteralPath $sourceManifestPath -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $runtimeManifestPath -Algorithm SHA256).Hash) {
      $runtimeIssues.Add([ordered]@{ type='runtime_manifest_drift'; source=$sourceManifestPath; runtime=$runtimeManifestPath }) | Out-Null
    }
  }
  if ((Test-Path -LiteralPath $sourceSettingsTemplatePath) -and (Test-Path -LiteralPath $runtimeTemplatePath)) {
    if ((Get-FileHash -LiteralPath $sourceSettingsTemplatePath -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $runtimeTemplatePath -Algorithm SHA256).Hash) {
      $runtimeIssues.Add([ordered]@{ type='runtime_template_drift'; source=$sourceSettingsTemplatePath; runtime=$runtimeTemplatePath }) | Out-Null
    }
  }
  foreach ($eventName in $allowedEvents) {
    $srcScript = Join-Path $sourceScriptsDir ("{0}.ps1" -f $eventName)
    if (-not $manifestRuntimeTargets.Contains($eventName)) {
      continue
    }
    try {
      $rtScript = Resolve-PathWithinRoot -RootPath $runtimeRoot -RelativePath $manifestRuntimeTargets[$eventName]
    } catch {
      $runtimeIssues.Add([ordered]@{ type='runtime_script_path_invalid'; event=$eventName; target=$manifestRuntimeTargets[$eventName]; error=$_.Exception.Message }) | Out-Null
      continue
    }
    if ((Test-Path -LiteralPath $srcScript) -and (Test-Path -LiteralPath $rtScript)) {
      if ((Get-FileHash -LiteralPath $srcScript -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $rtScript -Algorithm SHA256).Hash) {
        $runtimeIssues.Add([ordered]@{ type='runtime_script_drift'; event=$eventName; source=$srcScript; runtime=$rtScript }) | Out-Null
      }
    }
  }
  $runtimeHookCommonPath = Join-Path $runtimeRoot 'scripts\HookCommon.ps1'
  if ((Test-Path -LiteralPath $hookCommonPath) -and (Test-Path -LiteralPath $runtimeHookCommonPath)) {
    if ((Get-FileHash -LiteralPath $hookCommonPath -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $runtimeHookCommonPath -Algorithm SHA256).Hash) {
      $runtimeIssues.Add([ordered]@{ type='runtime_script_drift'; event='HookCommon'; source=$hookCommonPath; runtime=$runtimeHookCommonPath }) | Out-Null
    }
  }

  $receiptResult = Get-JsonMapFromFile -PathValue $receiptPath -ScopeName 'runtime_receipt'
  if (-not $receiptResult.ok) {
    $receiptIssues.Add([ordered]@{ type='receipt_invalid'; path=$receiptPath; error=$receiptResult.error }) | Out-Null
  } else {
    $receiptData = $receiptResult.data
    if ("$($receiptData['harness_root'])" -ne $RepoRoot) {
      $receiptIssues.Add([ordered]@{ type='receipt_harness_root_mismatch'; expected=$RepoRoot; actual=$receiptData['harness_root'] }) | Out-Null
    }
    if ("$($receiptData['runtime_root'])" -ne $runtimeRoot) {
      $receiptIssues.Add([ordered]@{ type='receipt_runtime_root_mismatch'; expected=$runtimeRoot; actual=$receiptData['runtime_root'] }) | Out-Null
    }
    if (-not (Test-MapHasKey -Map $receiptData -Key 'managed_files')) {
      $receiptIssues.Add([ordered]@{ type='receipt_missing_managed_files'; path=$receiptPath }) | Out-Null
    } else {
      $receiptTargets = New-Object System.Collections.Generic.HashSet[string]
      foreach ($managed in @($receiptData['managed_files'])) {
        if ($null -eq $managed -or -not ($managed -is [System.Collections.IDictionary])) {
          $receiptIssues.Add([ordered]@{ type='receipt_managed_file_type'; path=$receiptPath; message='managed_files item must be object' }) | Out-Null
          continue
        }
        $targetRel = "$($managed['target'])".Replace('\','/').TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($targetRel)) {
          $receiptIssues.Add([ordered]@{ type='receipt_managed_file_missing_target'; path=$receiptPath }) | Out-Null
          continue
        }
        $null = $receiptTargets.Add($targetRel)
        try {
          $resolved = Resolve-PathWithinRoot -RootPath $runtimeRoot -RelativePath $targetRel
        } catch {
          $receiptIssues.Add([ordered]@{ type='receipt_target_out_of_runtime_root'; target=$targetRel; error=$_.Exception.Message; runtime_root=$runtimeRoot }) | Out-Null
          continue
        }
        if (-not (Test-Path -LiteralPath $resolved)) {
          $receiptIssues.Add([ordered]@{ type='receipt_target_missing'; target=$targetRel; resolved=$resolved }) | Out-Null
          continue
        }
        $expectedSha = "$($managed['sha256'])".ToLowerInvariant()
        if ([string]::IsNullOrWhiteSpace($expectedSha)) {
          $receiptIssues.Add([ordered]@{ type='receipt_target_sha256_missing'; target=$targetRel; resolved=$resolved }) | Out-Null
        } else {
          $actualSha = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
          if ($actualSha -ne $expectedSha) {
            $receiptIssues.Add([ordered]@{ type='receipt_target_sha256_mismatch'; target=$targetRel; expected=$expectedSha; actual=$actualSha; resolved=$resolved }) | Out-Null
          }
        }
      }
      foreach ($required in $runtimeRequired) {
        if (-not $receiptTargets.Contains($required.rel)) {
          $receiptIssues.Add([ordered]@{ type='receipt_missing_required_target'; target=$required.rel }) | Out-Null
        }
      }
    }
    if (-not (Test-MapHasKey -Map $receiptData -Key 'settings')) {
      $receiptIssues.Add([ordered]@{ type='receipt_missing_settings_section'; path=$receiptPath }) | Out-Null
    } else {
      $settingsSection = $receiptData['settings']
      if (-not ($settingsSection -is [System.Collections.IDictionary])) {
        $receiptIssues.Add([ordered]@{ type='receipt_settings_section_type'; path=$receiptPath; message='settings section must be object' }) | Out-Null
      } else {
        if ("$($settingsSection['path'])" -ne $settingsPath) {
          $receiptIssues.Add([ordered]@{ type='receipt_settings_path_mismatch'; expected=$settingsPath; actual=$settingsSection['path'] }) | Out-Null
        }
        if ("$($settingsSection['managed_top_level'])" -ne 'hooks') {
          $receiptIssues.Add([ordered]@{ type='receipt_managed_top_level_mismatch'; expected='hooks'; actual=$settingsSection['managed_top_level'] }) | Out-Null
        }
        $fragmentRel = "$($settingsSection['runtime_fragment_path'])".Replace('\','/').TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($fragmentRel)) {
          $receiptIssues.Add([ordered]@{ type='receipt_runtime_fragment_missing'; path=$receiptPath }) | Out-Null
        } else {
          try {
            $fragmentPath = Resolve-PathWithinRoot -RootPath $runtimeRoot -RelativePath $fragmentRel
          } catch {
            $receiptIssues.Add([ordered]@{ type='receipt_runtime_fragment_out_of_runtime_root'; fragment=$fragmentRel; error=$_.Exception.Message; runtime_root=$runtimeRoot }) | Out-Null
            $fragmentPath = $null
          }
          if (($null -ne $fragmentPath) -and (-not (Test-Path -LiteralPath $fragmentPath))) {
            $receiptIssues.Add([ordered]@{ type='receipt_runtime_fragment_not_found'; fragment=$fragmentRel; path=$fragmentPath }) | Out-Null
          }
        }
      }
    }
  }

  $runtimeHooks = $null
  $runtimeSettingsResult = Get-JsonMapFromFile -PathValue $runtimeSettingsPath -ScopeName 'runtime_settings'
  if (-not $runtimeSettingsResult.ok) {
    $runtimeIssues.Add([ordered]@{ type='runtime_settings_invalid'; path=$runtimeSettingsPath; error=$runtimeSettingsResult.error }) | Out-Null
  } else {
    if (-not (Test-MapHasKey -Map $runtimeSettingsResult.data -Key 'hooks')) {
      $runtimeIssues.Add([ordered]@{ type='runtime_settings_missing_hooks'; path=$runtimeSettingsPath }) | Out-Null
    } else {
      $runtimeHooks = $runtimeSettingsResult.data['hooks']
      $runtimeHooksValidation = Test-HooksStructure -HooksMap $runtimeHooks -ScopeName 'runtime_settings'
      foreach ($issue in $runtimeHooksValidation.issues) { $runtimeIssues.Add($issue) | Out-Null }
      foreach ($commandEntry in @($runtimeHooksValidation.commands)) {
        $commandPath = Resolve-CommandFilePath -CommandText $commandEntry.command -BaseRoot $runtimeRoot
        if ($null -eq $commandPath) {
          $commandPathIssues.Add([ordered]@{ scope='runtime_settings'; event=$commandEntry.event; command=$commandEntry.command; issue='cannot_resolve_file_path' }) | Out-Null
          continue
        }
        if (-not (Test-PathWithinRoot -RootPath $runtimeRoot -CandidatePath $commandPath)) {
          $commandPathIssues.Add([ordered]@{ scope='runtime_settings'; event=$commandEntry.event; command=$commandEntry.command; resolved_path=$commandPath; issue='command_file_outside_runtime_root' }) | Out-Null
          continue
        }
        if (-not (Test-Path -LiteralPath $commandPath)) {
          $commandPathIssues.Add([ordered]@{ scope='runtime_settings'; event=$commandEntry.event; command=$commandEntry.command; resolved_path=$commandPath; issue='command_file_missing' }) | Out-Null
          continue
        }
        if (-not $manifestRuntimeTargets.Contains($commandEntry.event)) {
          $commandPathIssues.Add([ordered]@{ scope='runtime_settings'; event=$commandEntry.event; command=$commandEntry.command; resolved_path=$commandPath; issue='missing_manifest_runtime_target' }) | Out-Null
          continue
        }
        $expectedRuntimeScriptPath = Resolve-PathWithinRoot -RootPath $runtimeRoot -RelativePath $manifestRuntimeTargets[$commandEntry.event]
        $resolvedCommandPath = Get-CanonicalPath -PathValue $commandPath
        $resolvedExpectedRuntimeScriptPath = Get-CanonicalPath -PathValue $expectedRuntimeScriptPath
        if ($resolvedCommandPath -ne $resolvedExpectedRuntimeScriptPath) {
          $commandPathIssues.Add([ordered]@{ scope='runtime_settings'; event=$commandEntry.event; command=$commandEntry.command; resolved_path=$resolvedCommandPath; expected_path=$resolvedExpectedRuntimeScriptPath; issue='command_file_path_mismatch' }) | Out-Null
        }
      }
    }
  }
  if ($receiptResult.ok -and (Test-MapHasKey -Map $receiptResult.data -Key 'settings') -and ($null -ne $runtimeHooks)) {
    $settingsSection = $receiptResult.data['settings']
    if (($settingsSection -is [System.Collections.IDictionary]) -and (-not [string]::IsNullOrWhiteSpace("$($settingsSection['managed_hooks_sha256'])"))) {
      $expectedHooksSha = "$($settingsSection['managed_hooks_sha256'])".ToLowerInvariant()
      $actualHooksSha = Get-StringSha256 -Content ($runtimeHooks | ConvertTo-Json -Depth 64 -Compress)
      if ($actualHooksSha -ne $expectedHooksSha) {
        $receiptIssues.Add([ordered]@{ type='receipt_managed_hooks_sha256_mismatch'; expected=$expectedHooksSha; actual=$actualHooksSha; runtime_settings_path=$runtimeSettingsPath }) | Out-Null
      }
    } elseif ($settingsSection -is [System.Collections.IDictionary]) {
      $receiptIssues.Add([ordered]@{ type='receipt_managed_hooks_sha256_missing'; path=$receiptPath }) | Out-Null
    }
  }

  $settingsResult = Get-JsonMapFromFile -PathValue $settingsPath -ScopeName 'user_settings'
  if (-not $settingsResult.ok) {
    $runtimeIssues.Add([ordered]@{ type='user_settings_invalid'; path=$settingsPath; error=$settingsResult.error }) | Out-Null
  } else {
    if (-not (Test-MapHasKey -Map $settingsResult.data -Key 'hooks')) {
      $runtimeIssues.Add([ordered]@{ type='user_settings_missing_top_level_hooks'; path=$settingsPath }) | Out-Null
    } elseif ($null -ne $runtimeHooks) {
      $userHooks = $settingsResult.data['hooks']
      $userHooksJson = $userHooks | ConvertTo-Json -Depth 64 -Compress
      $runtimeHooksJson = $runtimeHooks | ConvertTo-Json -Depth 64 -Compress
      if ($userHooksJson -ne $runtimeHooksJson) {
        $runtimeIssues.Add([ordered]@{ type='settings_hooks_not_equal_runtime_fragment'; settings_path=$settingsPath; runtime_settings_path=$runtimeSettingsPath }) | Out-Null
      }
    }
  }

  return [ordered]@{
    source = [ordered]@{
      manifest_path = $sourceManifestPath
      settings_template_path = $sourceSettingsTemplatePath
      scripts_dir = $sourceScriptsDir
    }
    runtime = [ordered]@{
      claude_home = $claudeHome
      runtime_root = $runtimeRoot
      runtime_manifest_path = $runtimeManifestPath
      runtime_template_path = $runtimeTemplatePath
      runtime_settings_path = $runtimeSettingsPath
      settings_path = $settingsPath
      receipt_path = $receiptPath
    }
    missing_source_scripts = $missingSourceScripts.ToArray()
    source_issues = $sourceIssues.ToArray()
    runtime_issues = $runtimeIssues.ToArray()
    receipt_issues = $receiptIssues.ToArray()
    command_path_issues = $commandPathIssues.ToArray()
    ok = ($missingSourceScripts.Count -eq 0 -and $sourceIssues.Count -eq 0 -and $runtimeIssues.Count -eq 0 -and $receiptIssues.Count -eq 0 -and $commandPathIssues.Count -eq 0)
  }
}

function Get-RepoAudit {
  param(
    [string]$RepoRoot,
    [string[]]$RequiredPathsValue,
    [string[]]$LegacyMarkersValue,
    [string[]]$TextRootsValue
  )
  $pathStatuses = Get-PathStatuses -RepoRoot $RepoRoot -Paths $RequiredPathsValue
  $missing = @($pathStatuses | Where-Object { -not $_.exists } | ForEach-Object { $_.path })
  $legacyCounts = Get-LegacyMarkerCounts -RepoRoot $RepoRoot -Markers $LegacyMarkersValue -Roots $TextRootsValue
  $sessionAudit = Get-SessionAudit -RepoRoot $RepoRoot
  $workOrderAudit = Get-WorkOrderAudit -RepoRoot $RepoRoot
  $sessionOk = ($sessionAudit.missing_documents.Count -eq 0 -and $sessionAudit.missing_meta_fields.Count -eq 0 -and $sessionAudit.invalid_doc_types.Count -eq 0 -and $sessionAudit.invalid_task_ids.Count -eq 0 -and $sessionAudit.invalid_statuses.Count -eq 0 -and $sessionAudit.step_id_mismatches.Count -eq 0 -and $sessionAudit.missing_path_references.Count -eq 0)
  $workOrderOk = ($workOrderAudit.missing_fields.Count -eq 0 -and $workOrderAudit.missing_dispatch_packets.Count -eq 0 -and $workOrderAudit.missing_dispatch_message_raw.Count -eq 0 -and $workOrderAudit.invalid_work_orders.Count -eq 0)
  return [ordered]@{
    missing_paths = $missing
    path_statuses = $pathStatuses
    legacy_marker_counts = $legacyCounts
    session_audit = $sessionAudit
    work_order_audit = $workOrderAudit
    ok = ($missing.Count -eq 0 -and $sessionOk -and $workOrderOk)
  }
}

$repoRoot = Get-RepoRoot -ScriptPath $MyInvocation.MyCommand.Path
$result = $null
if ($AuditTarget -eq 'codex_minimal') {
  $resolvedCodexHome = if ([string]::IsNullOrWhiteSpace($CodexHome)) { Join-Path $env:USERPROFILE '.codex' } else { Normalize-UserPath -PathValue $CodexHome }
  $codexAudit = Get-CodexAudit -RepoRoot $repoRoot -CodexHomeValue $resolvedCodexHome
  $result = [ordered]@{
    root = $repoRoot
    mode = 'codex_minimal'
    codex_audit = $codexAudit
    ok = $codexAudit.ok
  }
} else {
  $resolvedClaudeHome = if ([string]::IsNullOrWhiteSpace($ClaudeHome)) { Join-Path $env:USERPROFILE '.claude' } else { Normalize-UserPath -PathValue $ClaudeHome }
  $claudeHooksAudit = Get-ClaudeHooksAudit -RepoRoot $repoRoot -ClaudeHomeValue $resolvedClaudeHome
  $result = [ordered]@{
    root = $repoRoot
    mode = 'claude_hooks'
    claude_hooks_audit = $claudeHooksAudit
    ok = $claudeHooksAudit.ok
  }
}
if ($IncludeRepoAudit) {
  $repoAudit = Get-RepoAudit -RepoRoot $repoRoot -RequiredPathsValue $RequiredPaths -LegacyMarkersValue $LegacyMarkers -TextRootsValue $TextRoots
  $result['repo_audit'] = $repoAudit
  $result['ok'] = ($result['ok'] -and $repoAudit.ok)
}
if ($Json) { $result | ConvertTo-Json -Depth 8 } else { $result }
if ($Strict -and -not $result.ok) { exit 1 }
exit 0
