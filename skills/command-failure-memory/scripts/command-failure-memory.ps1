param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('record-failure', 'query-before-retry', 'record-success', 'inspect')]
  [string]$Action,
  [string]$CodexHome = '',
  [string]$ProjectId = '',
  [string]$CommandText = '',
  [string]$ErrorText = '',
  [string]$Resolution = '',
  [string]$ScopeKind = '',
  [double]$ScopeConfidence = [double]::NaN,
  [string]$ScopeReason = '',
  [switch]$ProjectSpecific,
  [switch]$Json
)

$ErrorActionPreference = 'Stop'
$script:MaxSignatureSourceLength = 4096
$script:MaxStoredSignatureLength = 512
$script:MaxStoredCommandLength = 512
$script:MaxStoredErrorLength = 512
$script:MaxStoredResolutionLength = 768
$script:MaxStoredReasonLength = 256
$script:MaxProjectsSeen = 32
$script:MaxPendingFailureEvents = 128
$script:MaxCaseCount = 1024
$script:MemoryLockTimeoutMs = 15000

function Normalize-UserPath {
  param([string]$PathValue)
  if ([string]::IsNullOrWhiteSpace($PathValue)) {
    return $null
  }
  $expanded = [Environment]::ExpandEnvironmentVariables($PathValue)
  if ($expanded.StartsWith('~')) {
    $expanded = Join-Path $env:USERPROFILE $expanded.Substring(1).TrimStart('\', '/')
  }
  return [System.IO.Path]::GetFullPath($expanded)
}

function Get-DefaultCodexHome {
  $envCodexHome = Normalize-UserPath -PathValue $env:CODEX_HOME
  if (-not [string]::IsNullOrWhiteSpace($envCodexHome)) {
    return $envCodexHome
  }
  return (Join-Path $env:USERPROFILE '.codex')
}

function Limit-StringLength {
  param(
    [string]$Text,
    [int]$MaxLength,
    [string]$Suffix = ' <truncated>'
  )
  if ($null -eq $Text) {
    return ''
  }
  $value = [string]$Text
  if ($value.Length -le $MaxLength) {
    return $value
  }
  if ($MaxLength -le 0) {
    return ''
  }
  $safeSuffix = if ([string]::IsNullOrEmpty($Suffix) -or ($Suffix.Length -ge $MaxLength)) { '' } else { $Suffix }
  return ($value.Substring(0, $MaxLength - $safeSuffix.Length) + $safeSuffix)
}

$script:PathNativeAvailable = $false
$script:PathNativeFailureReason = ''
$script:WindowsPathSafetyRequired = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
if ($script:WindowsPathSafetyRequired) {
  if ($env:AI_HARNESS_DISABLE_NATIVE_PATH -eq '1') {
    $script:PathNativeAvailable = $false
    $script:PathNativeFailureReason = 'disabled by AI_HARNESS_DISABLE_NATIVE_PATH'
  } elseif (-not ('AiHarness.PathNative' -as [type])) {
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
    throw 'Path is empty'
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
    Assert-NoReparsePointTraversal -RootPath $RootPath -CandidatePath $CandidatePath -Description 'memory root path'
  }
  return $withinRoot
}

function Resolve-PathWithinRoot {
  param(
    [string]$RootPath,
    [string]$RelativePath
  )
  $candidate = [System.IO.Path]::GetFullPath((Join-Path $RootPath ($RelativePath -replace '/', '\')))
  $textualRootPrefix = [System.IO.Path]::GetFullPath($RootPath).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if ($candidate.StartsWith($textualRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    Assert-NoReparsePointTraversal -RootPath $RootPath -CandidatePath $candidate -Description 'memory root path'
  }
  if (-not (Test-PathWithinRoot -RootPath $RootPath -CandidatePath $candidate)) {
    throw ("Resolved path escapes memory root: {0}" -f $RelativePath)
  }
  return $candidate
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

function Read-JsonObject {
  param([string]$PathValue, [object]$DefaultValue)
  if (-not (Test-Path -LiteralPath $PathValue)) {
    return $DefaultValue
  }
  $raw = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return $DefaultValue
  }
  return (ConvertTo-NormalizedMap -InputObject ($raw | ConvertFrom-Json))
}

function Write-JsonObject {
  param([string]$PathValue, [object]$Data)
  $parent = Split-Path -Parent $PathValue
  if (-not [string]::IsNullOrWhiteSpace($parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  $tempPath = Join-Path $parent ([guid]::NewGuid().ToString('N') + '.tmp')
  $backupPath = Join-Path $parent ([guid]::NewGuid().ToString('N') + '.bak')
  try {
    Set-Content -LiteralPath $tempPath -Value ($Data | ConvertTo-Json -Depth 64) -Encoding UTF8
    if (Test-Path -LiteralPath $PathValue) {
      [System.IO.File]::Replace($tempPath, $PathValue, $backupPath, $true)
    } else {
      [System.IO.File]::Move($tempPath, $PathValue)
    }
  } finally {
    foreach ($cleanupPath in @($tempPath, $backupPath)) {
      if (Test-Path -LiteralPath $cleanupPath) {
        Remove-Item -LiteralPath $cleanupPath -Force
      }
    }
  }
}

function Get-StringSha256 {
  param([string]$Content)
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
  $hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
  return ([System.BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant())
}

function Get-IsoTimestamp {
  return (Get-Date).ToString('o')
}

function Convert-ToValidatedDouble {
  param(
    [object]$Value,
    [string]$FieldName
  )
  try {
    $number = [double]$Value
  } catch {
    throw ("{0} must be numeric." -f $FieldName)
  }
  if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
    throw ("{0} must be a finite number." -f $FieldName)
  }
  return $number
}

function Get-NormalizedScopeConfidence {
  param(
    [object]$Value,
    [string]$FieldName = 'scope_confidence'
  )
  $number = Convert-ToValidatedDouble -Value $Value -FieldName $FieldName
  if (($number -lt 0.0) -or ($number -gt 1.0)) {
    throw ("{0} must be between 0 and 1." -f $FieldName)
  }
  return [Math]::Round($number, 2)
}

function Redact-SensitiveText {
  param([string]$Text)
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }
  $value = $Text
  $value = [regex]::Replace($value, '(?s)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '<redacted-private-key>')
  $value = [regex]::Replace($value, '(?im)\b(authorization)\b\s*:\s*[A-Za-z]+\s+[^\s''"`,;]+', '$1: <redacted>')
  $value = [regex]::Replace($value, '(?im)(https?://)([^\s/@:]+):([^\s/@]+)@', '$1<redacted>@')
  $value = [regex]::Replace($value, '(?im)\b([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASS(?:PHRASE)?|API[_\-]?KEY|ACCESS[_\-]?KEY|PRIVATE[_\-]?KEY|CLIENT[_\-]?SECRET)[A-Z0-9_]*)\b\s*[:=]\s*([^\r\n]+)', '$1=<redacted>')
  $value = [regex]::Replace($value, '(?im)\b(api[_\-]?key|token|password|passphrase|secret|client[_\-]?secret|access[_\-]?token|refresh[_\-]?token|session[_\-]?token)\b\s*[:=]\s*([^\r\n]+)', '$1=<redacted>')
  $value = [regex]::Replace($value, '(?<![A-Za-z0-9])(github_pat_[A-Za-z0-9_]{20,})(?![A-Za-z0-9])', '<redacted-github-token>')
  $value = [regex]::Replace($value, '(?<![A-Za-z0-9])(gh[pousr]_[A-Za-z0-9]{20,})(?![A-Za-z0-9])', '<redacted-github-token>')
  $value = [regex]::Replace($value, '(?<![A-Za-z0-9])(xox[baprs]-[A-Za-z0-9\-]{10,})(?![A-Za-z0-9])', '<redacted-slack-token>')
  $value = [regex]::Replace($value, '(?<![A-Za-z0-9])(sk-[A-Za-z0-9]{20,})(?![A-Za-z0-9])', '<redacted-api-key>')
  $value = [regex]::Replace($value, '(?<![A-Za-z0-9])(AKIA[0-9A-Z]{16})(?![A-Za-z0-9])', '<redacted-aws-key>')
  $value = [regex]::Replace($value, '(?<![A-Za-z0-9])(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})(?![A-Za-z0-9])', '<redacted-jwt>')
  $value = [regex]::Replace($value, '(?<![A-Za-z0-9])([A-Za-z0-9+/]{48,}={0,2}|[A-Fa-f0-9]{48,})(?![A-Za-z0-9])', '<redacted-secret>')
  return $value
}

function Get-SanitizedStoredText {
  param(
    [string]$Text,
    [int]$MaxLength
  )
  $value = Redact-SensitiveText -Text (Limit-StringLength -Text $Text -MaxLength ([Math]::Max($MaxLength * 4, $MaxLength)))
  return (Limit-StringLength -Text $value.Trim() -MaxLength $MaxLength)
}

function Normalize-SignatureText {
  param(
    [string]$Text,
    [switch]$PreserveLineBreaks
  )
  $limited = Limit-StringLength -Text $Text -MaxLength $script:MaxSignatureSourceLength -Suffix ''
  $normalized = (Redact-SensitiveText -Text $limited).Trim().ToLowerInvariant()
  if ($PreserveLineBreaks) {
    $normalized = ($normalized -replace '\r\n?', "`n")
    $normalized = ($normalized -replace '[\t\f\v ]+', ' ')
    $normalized = ($normalized -replace "`n+", "`n")
    return $normalized
  }
  return ($normalized -replace '\s+', ' ')
}

function Get-ErrorSignatureLine {
  param([string]$ErrorValue)
  $normalized = Normalize-SignatureText -Text $ErrorValue -PreserveLineBreaks
  if ([string]::IsNullOrWhiteSpace($normalized)) {
    return ''
  }
  return (($normalized -split "`n")[0]).Trim()
}

function Get-CaseSignature {
  param(
    [string]$CommandValue,
    [string]$ErrorValue
  )
  $normalizedCommand = Normalize-SignatureText -Text $CommandValue
  $normalizedError = Get-ErrorSignatureLine -ErrorValue $ErrorValue
  if ([string]::IsNullOrWhiteSpace($normalizedCommand) -or [string]::IsNullOrWhiteSpace($normalizedError)) {
    throw 'command/error cannot be empty when computing failure signature.'
  }
  return [ordered]@{
    signature = Get-StringSha256 -Content ("{0}|{1}" -f $normalizedCommand, $normalizedError)
    command_signature = $normalizedCommand
    error_signature = $normalizedError
  }
}

function Get-CanonicalProjectId {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return 'unknown-project'
  }
  return (($Value.Trim().ToLowerInvariant()) -replace '[^a-z0-9\.\-_]', '-')
}

function Get-DefaultScopeReason {
  param([string]$ScopeKindValue)
  switch ($ScopeKindValue) {
    'candidate_global' { return 'Fix looks like an environment-wide issue; keep candidate_global first.' }
    'candidate_project' { return 'Fix depends on project-specific context; keep candidate_project first.' }
    'global' { return 'Validated across projects as a stable global solution.' }
    'project' { return 'Only validated in project-specific context.' }
    default { return '' }
  }
}

function Test-ValidScopeKind {
  param([string]$ScopeKindValue)
  return @('candidate_global', 'candidate_project', 'global', 'project') -contains $ScopeKindValue
}

function Ensure-ArrayContains {
  param(
    [object[]]$Items,
    [string]$Value
  )
  $list = New-Object System.Collections.Generic.List[string]
  foreach ($item in @($Items)) {
    $text = [string]$item
    if (-not [string]::IsNullOrWhiteSpace($text) -and (-not $list.Contains($text))) {
      $list.Add($text) | Out-Null
    }
  }
  if (-not $list.Contains($Value)) {
    $list.Add($Value) | Out-Null
  }
  while ($list.Count -gt $script:MaxProjectsSeen) {
    $list.RemoveAt(0)
  }
  return $list.ToArray()
}

function Get-TimestampSortKey {
  param([string]$Timestamp)
  try {
    return ([DateTimeOffset]::Parse($Timestamp)).UtcDateTime.Ticks
  } catch {
    return 0L
  }
}

function Limit-FailureEvents {
  param([object[]]$Events)
  $filtered = @($Events | Where-Object { $null -ne $_ })
  if (@($filtered).Count -le $script:MaxPendingFailureEvents) {
    return $filtered
  }
  return @(
    $filtered |
      Sort-Object -Property @{ Expression = {
        if ([string]::IsNullOrWhiteSpace([string]$_.last_failed_at)) {
          Get-TimestampSortKey -Timestamp ([string]$_.first_failed_at)
        } else {
          Get-TimestampSortKey -Timestamp ([string]$_.last_failed_at)
        }
      }; Descending = $true } |
      Select-Object -First $script:MaxPendingFailureEvents
  )
}

function Assert-CaseCapacity {
  param([hashtable]$CaseById)
  if ($CaseById.Count -ge $script:MaxCaseCount) {
    throw ("case capacity limit reached: {0}" -f $script:MaxCaseCount)
  }
}

function Assert-ValidCaseData {
  param([object]$CaseData)
  if ($null -eq $CaseData) {
    throw 'case data is null'
  }
  if ([string]::IsNullOrWhiteSpace([string]$CaseData.schema_version)) {
    $CaseData.schema_version = '1.0'
  }
  if (([string]$CaseData.case_id) -notmatch '^CASE-[a-f0-9]{16}$') {
    throw ("case is missing a valid case_id: {0}" -f [string]$CaseData.case_id)
  }
  if (([string]$CaseData.signature) -notmatch '^[a-f0-9]{64}$') {
    throw ("case is missing a valid signature: {0}" -f [string]$CaseData.case_id)
  }
  if (-not (Test-ValidScopeKind -ScopeKindValue ([string]$CaseData.scope_kind))) {
    throw ("case is missing a valid scope_kind: {0}" -f [string]$CaseData.case_id)
  }
  $CaseData.scope_confidence = Get-NormalizedScopeConfidence -Value $CaseData.scope_confidence -FieldName ("scope_confidence for {0}" -f [string]$CaseData.case_id)
  $CaseData.command_signature = Limit-StringLength -Text ([string]$CaseData.command_signature) -MaxLength $script:MaxStoredSignatureLength
  $CaseData.error_signature = Limit-StringLength -Text ([string]$CaseData.error_signature) -MaxLength $script:MaxStoredSignatureLength
  if ([string]::IsNullOrWhiteSpace($CaseData.command_signature) -or [string]::IsNullOrWhiteSpace($CaseData.error_signature)) {
    throw ("case is missing signature text: {0}" -f [string]$CaseData.case_id)
  }
  $CaseData.command_excerpt = Get-SanitizedStoredText -Text ([string]$CaseData.command_excerpt) -MaxLength $script:MaxStoredCommandLength
  $CaseData.error_excerpt = Get-SanitizedStoredText -Text ([string]$CaseData.error_excerpt) -MaxLength $script:MaxStoredErrorLength
  $CaseData.solution = Get-SanitizedStoredText -Text ([string]$CaseData.solution) -MaxLength $script:MaxStoredResolutionLength
  $CaseData.scope_reason = Get-SanitizedStoredText -Text ([string]$CaseData.scope_reason) -MaxLength $script:MaxStoredReasonLength
  if ([string]::IsNullOrWhiteSpace([string]$CaseData.scope_reason)) {
    throw ("case is missing scope_reason: {0}" -f [string]$CaseData.case_id)
  }
  $normalizedProjects = New-Object System.Collections.Generic.List[string]
  foreach ($projectId in @($CaseData.projects_seen)) {
    $canonicalProjectId = Get-CanonicalProjectId -Value ([string]$projectId)
    if (-not $normalizedProjects.Contains($canonicalProjectId)) {
      $normalizedProjects.Add($canonicalProjectId) | Out-Null
    }
  }
  while ($normalizedProjects.Count -gt $script:MaxProjectsSeen) {
    $normalizedProjects.RemoveAt(0)
  }
  if ($normalizedProjects.Count -eq 0) {
    throw ("case is missing projects_seen: {0}" -f [string]$CaseData.case_id)
  }
  $CaseData.projects_seen = $normalizedProjects.ToArray()
  if ($null -eq $CaseData.stats) {
    $CaseData.stats = [ordered]@{ hit_count = 0; verify_count = 0; incident_count = 0 }
  }
  foreach ($field in @('hit_count', 'verify_count', 'incident_count')) {
    $value = [int]$CaseData.stats.$field
    if ($value -lt 0) {
      throw ("case stat must be non-negative: {0}.{1}" -f [string]$CaseData.case_id, $field)
    }
    $CaseData.stats.$field = $value
  }
  foreach ($field in @('created_at', 'updated_at')) {
    if ([string]::IsNullOrWhiteSpace([string]$CaseData.$field)) {
      throw ("case is missing {0}: {1}" -f $field, [string]$CaseData.case_id)
    }
  }
}

function Get-MemoryLockName {
  param([string]$MemoryRoot)
  $lockIdentity = Normalize-UserPath -PathValue $MemoryRoot
  if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    $lockIdentity = $lockIdentity.ToLowerInvariant()
  }
  return ('Local\AiHarness.CommandFailureMemory.{0}' -f (Get-StringSha256 -Content $lockIdentity).Substring(0, 24))
}

function Invoke-WithMemoryLock {
  param(
    [string]$MemoryRoot,
    [scriptblock]$ScriptBlock
  )
  $mutex = New-Object System.Threading.Mutex($false, (Get-MemoryLockName -MemoryRoot $MemoryRoot))
  $lockAcquired = $false
  try {
    try {
      $lockAcquired = $mutex.WaitOne($script:MemoryLockTimeoutMs)
    } catch [System.Threading.AbandonedMutexException] {
      $lockAcquired = $true
    }
    if (-not $lockAcquired) {
      throw ("timed out waiting for failure-memory lock after {0} ms." -f $script:MemoryLockTimeoutMs)
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

function New-MemoryStorage {
  param([string]$MemoryRoot)
  $casesRoot = Resolve-PathWithinRoot -RootPath $MemoryRoot -RelativePath 'cases'
  $runtimeRoot = Resolve-PathWithinRoot -RootPath $MemoryRoot -RelativePath 'runtime'
  New-Item -ItemType Directory -Path $casesRoot -Force | Out-Null
  New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
  $indexPath = Resolve-PathWithinRoot -RootPath $MemoryRoot -RelativePath 'index.json'
  $failureEventsPath = Resolve-PathWithinRoot -RootPath $MemoryRoot -RelativePath 'runtime/failure-events.json'
  return [ordered]@{
    memory_root = $MemoryRoot
    cases_root = $casesRoot
    runtime_root = $runtimeRoot
    index_path = $indexPath
    failure_events_path = $failureEventsPath
  }
}

function Get-EmptyIndexData {
  return [ordered]@{
    schema_version = '1.0'
    updated_at = ''
    cases = @()
  }
}

function Get-EmptyFailureData {
  return [ordered]@{
    schema_version = '1.0'
    updated_at = ''
    events = @()
  }
}

function Resolve-CaseFilePath {
  param(
    [string]$CasesRoot,
    [string]$CaseId
  )
  if ([string]::IsNullOrWhiteSpace($CaseId) -or ($CaseId -notmatch '^CASE-[a-f0-9]{16}$')) {
    throw ("invalid case_id rejected: {0}" -f $CaseId)
  }
  return (Resolve-PathWithinRoot -RootPath $CasesRoot -RelativePath ("{0}.json" -f $CaseId))
}

function New-CaseId {
  param(
    [string]$Signature,
    [hashtable]$CaseById
  )
  $prefix = $Signature.Substring(0, [Math]::Min(16, $Signature.Length))
  $caseId = ("CASE-{0}" -f $prefix)
  if (-not $CaseById.ContainsKey($caseId)) {
    return $caseId
  }
  while ($true) {
    $suffix = ([guid]::NewGuid().ToString('N')).Substring(0, 16)
    $candidate = ("CASE-{0}" -f $suffix)
    if (-not $CaseById.ContainsKey($candidate)) {
      return $candidate
    }
  }
}

function Get-CaseMaps {
  param(
    [object]$Storage
  )
  $indexData = Read-JsonObject -PathValue $Storage.index_path -DefaultValue (Get-EmptyIndexData)
  if ($null -eq $indexData.cases) {
    $indexData.cases = @()
  }
  $caseById = @{}
  $caseBySignature = @{}
  foreach ($entry in @($indexData.cases)) {
    if ($null -eq $entry) {
      continue
    }
    $caseId = [string]$entry.case_id
    if ([string]::IsNullOrWhiteSpace($caseId)) {
      continue
    }
    $casePath = Resolve-CaseFilePath -CasesRoot $Storage.cases_root -CaseId $caseId
    $caseData = Read-JsonObject -PathValue $casePath -DefaultValue $null
    if ($null -eq $caseData) {
      continue
    }
    $signature = [string]$caseData.signature
    if ([string]::IsNullOrWhiteSpace($signature)) {
      continue
    }
    Assert-ValidCaseData -CaseData $caseData
    $caseById[$caseId] = $caseData
    if (-not $caseBySignature.ContainsKey($signature)) {
      $caseBySignature[$signature] = @()
    }
    $caseBySignature[$signature] = @($caseBySignature[$signature]) + @($caseData)
  }
  return [ordered]@{
    index_data = $indexData
    by_id = $caseById
    by_signature = $caseBySignature
  }
}

function Save-CaseMaps {
  param(
    [object]$Storage,
    [hashtable]$CaseById
  )
  $caseEntries = New-Object System.Collections.Generic.List[object]
  foreach ($caseId in ($CaseById.Keys | Sort-Object)) {
    $caseData = $CaseById[$caseId]
    Assert-ValidCaseData -CaseData $caseData
    $casePath = Resolve-CaseFilePath -CasesRoot $Storage.cases_root -CaseId $caseId
    Write-JsonObject -PathValue $casePath -Data $caseData
    $caseEntries.Add([ordered]@{
      case_id = $caseData.case_id
      signature = $caseData.signature
      scope_kind = $caseData.scope_kind
      scope_confidence = $caseData.scope_confidence
      scope_reason = $caseData.scope_reason
      projects_seen = @($caseData.projects_seen)
      stats = $caseData.stats
      created_at = $caseData.created_at
      updated_at = $caseData.updated_at
    }) | Out-Null
  }
  $indexData = [ordered]@{
    schema_version = '1.0'
    updated_at = Get-IsoTimestamp
    cases = $caseEntries.ToArray()
  }
  Write-JsonObject -PathValue $Storage.index_path -Data $indexData
}

function Get-FailureEventsData {
  param([object]$Storage)
  $data = Read-JsonObject -PathValue $Storage.failure_events_path -DefaultValue (Get-EmptyFailureData)
  if ($null -eq $data.events) {
    $data.events = @()
  }
  $data.events = Limit-FailureEvents -Events @($data.events)
  return $data
}

function Save-FailureEventsData {
  param(
    [object]$Storage,
    [object]$Data
  )
  $Data.schema_version = '1.0'
  $Data.updated_at = Get-IsoTimestamp
  $Data.events = Limit-FailureEvents -Events @($Data.events)
  Write-JsonObject -PathValue $Storage.failure_events_path -Data $Data
}

function Update-CaseScopeConvergence {
  param(
    [object]$CaseData,
    [string]$CurrentProjectId,
    [bool]$ProjectSpecificEvidence
  )
    $CaseData.projects_seen = Ensure-ArrayContains -Items @($CaseData.projects_seen) -Value $CurrentProjectId
  $projectCount = @($CaseData.projects_seen).Count
  if ($CaseData.scope_kind -eq 'candidate_project' -and $projectCount -ge 2) {
    $CaseData.scope_kind = 'global'
    if ((Convert-ToValidatedDouble -Value $CaseData.scope_confidence -FieldName 'scope_confidence') -lt 0.85) {
      $CaseData.scope_confidence = Get-NormalizedScopeConfidence -Value 0.85
    }
    if ([string]::IsNullOrWhiteSpace([string]$CaseData.scope_reason)) {
      $CaseData.scope_reason = 'candidate_project converged to global after multi-project verification.'
    }
  } elseif ($CaseData.scope_kind -eq 'candidate_global' -and $projectCount -le 1 -and $ProjectSpecificEvidence) {
    $CaseData.scope_kind = 'project'
    if ((Convert-ToValidatedDouble -Value $CaseData.scope_confidence -FieldName 'scope_confidence') -gt 0.70) {
      $CaseData.scope_confidence = Get-NormalizedScopeConfidence -Value 0.70
    }
    if ([string]::IsNullOrWhiteSpace([string]$CaseData.scope_reason)) {
      $CaseData.scope_reason = 'candidate_global converged to project due to project-specific evidence.'
    }
  }
}

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
  $CodexHome = Get-DefaultCodexHome
}
$CodexHome = Normalize-UserPath -PathValue $CodexHome
$memoryRoot = [System.IO.Path]::GetFullPath((Join-Path $CodexHome 'memories\command-failure-memory'))
if (-not (Test-PathWithinRoot -RootPath $CodexHome -CandidatePath $memoryRoot)) {
  throw ("memory root must stay under codex_home: codex_home={0}, memory_root={1}" -f $CodexHome, $memoryRoot)
}
$storage = New-MemoryStorage -MemoryRoot $memoryRoot
$project = Get-CanonicalProjectId -Value $ProjectId
$now = Get-IsoTimestamp

$payload = Invoke-WithMemoryLock -MemoryRoot $memoryRoot -ScriptBlock {
switch ($Action) {
  'record-failure' {
    $sig = Get-CaseSignature -CommandValue $CommandText -ErrorValue $ErrorText
    $eventsData = Get-FailureEventsData -Storage $storage
    $events = New-Object System.Collections.Generic.List[object]
    $matched = $null
    foreach ($entry in @($eventsData.events)) {
      if ($null -eq $entry) { continue }
      if (([string]$entry.signature -eq $sig.signature) -and ([string]$entry.project_id -eq $project)) {
        $matched = $entry
      }
      $events.Add($entry) | Out-Null
    }

    if ($null -eq $matched) {
      $matched = [ordered]@{
        signature = $sig.signature
        command_signature = Limit-StringLength -Text $sig.command_signature -MaxLength $script:MaxStoredSignatureLength
        error_signature = Limit-StringLength -Text $sig.error_signature -MaxLength $script:MaxStoredSignatureLength
        project_id = $project
        first_failed_at = $now
        last_failed_at = $now
        failure_count = 1
        last_query_at = ''
      }
      $events.Add($matched) | Out-Null
    } else {
      $matched.last_failed_at = $now
      $matched.failure_count = ([int]$matched.failure_count + 1)
    }
    $eventsData.events = $events.ToArray()
    Save-FailureEventsData -Storage $storage -Data $eventsData

    $payload = [ordered]@{
      ok = $true
      action = $Action
      signature = $sig.signature
      project_id = $project
      failure_count = [int]$matched.failure_count
      query_performed = $false
      query_should_happen_before_retry = $true
      memory_root = $memoryRoot
    }
  }
  'query-before-retry' {
    $sig = Get-CaseSignature -CommandValue $CommandText -ErrorValue $ErrorText
    $eventsData = Get-FailureEventsData -Storage $storage
    $event = $null
    foreach ($entry in @($eventsData.events)) {
      if (($null -ne $entry) -and ([string]$entry.signature -eq $sig.signature) -and ([string]$entry.project_id -eq $project)) {
        $event = $entry
        break
      }
    }

    if ($null -eq $event) {
      $payload = [ordered]@{
        ok = $true
        action = $Action
        signature = $sig.signature
        project_id = $project
        query_permitted = $false
        reason = 'retry_gate_not_met'
        suggestions = @()
        memory_root = $memoryRoot
      }
      break
    }

    $event.last_query_at = $now
    Save-FailureEventsData -Storage $storage -Data $eventsData
    $maps = Get-CaseMaps -Storage $storage
    $suggestions = New-Object System.Collections.Generic.List[object]
    if ($maps.by_signature.ContainsKey($sig.signature)) {
      foreach ($caseData in @($maps.by_signature[$sig.signature])) {
        $caseData.updated_at = $now
        if ($null -eq $caseData.stats) {
          $caseData.stats = [ordered]@{ hit_count = 0; verify_count = 0; incident_count = 0 }
        }
        $caseData.stats.hit_count = ([int]$caseData.stats.hit_count + 1)
        $caseData.last_hit_at = $now
        $suggestions.Add([ordered]@{
          case_id = $caseData.case_id
          scope_kind = $caseData.scope_kind
          scope_confidence = $caseData.scope_confidence
          scope_reason = $caseData.scope_reason
          solution = $caseData.solution
          stats = $caseData.stats
          projects_seen = @($caseData.projects_seen)
        }) | Out-Null
      }
      Save-CaseMaps -Storage $storage -CaseById $maps.by_id
    }

    $payload = [ordered]@{
      ok = $true
      action = $Action
      signature = $sig.signature
      project_id = $project
      query_permitted = $true
      reason = 'retry_gate_passed'
      suggestions = $suggestions.ToArray()
      memory_root = $memoryRoot
    }
  }
  'record-success' {
    $sig = Get-CaseSignature -CommandValue $CommandText -ErrorValue $ErrorText
      $maps = Get-CaseMaps -Storage $storage
      $caseData = $null
      if ($maps.by_signature.ContainsKey($sig.signature)) {
        $caseData = @($maps.by_signature[$sig.signature])[0]
      }

    $createdNewCase = $false
    if ($null -eq $caseData) {
      Assert-CaseCapacity -CaseById $maps.by_id
      if ([string]::IsNullOrWhiteSpace($ScopeKind)) {
        throw 'scope_kind is required when no equivalent case exists.'
      }
      if (-not (Test-ValidScopeKind -ScopeKindValue $ScopeKind)) {
        throw ("invalid scope_kind: {0}" -f $ScopeKind)
      }
      $caseId = New-CaseId -Signature $sig.signature -CaseById $maps.by_id
      $confidence = if (-not [double]::IsNaN($ScopeConfidence)) { Get-NormalizedScopeConfidence -Value $ScopeConfidence } else { if ($ScopeKind.StartsWith('candidate_')) { 0.60 } else { 0.80 } }
      $caseData = [ordered]@{
        schema_version = '1.0'
        case_id = $caseId
        signature = $sig.signature
        command_signature = Limit-StringLength -Text $sig.command_signature -MaxLength $script:MaxStoredSignatureLength
        error_signature = Limit-StringLength -Text $sig.error_signature -MaxLength $script:MaxStoredSignatureLength
        command_excerpt = (Get-SanitizedStoredText -Text $CommandText -MaxLength $script:MaxStoredCommandLength)
        error_excerpt = (Get-SanitizedStoredText -Text $ErrorText -MaxLength $script:MaxStoredErrorLength)
        scope_kind = $ScopeKind
        scope_confidence = $confidence
        scope_reason = if ([string]::IsNullOrWhiteSpace($ScopeReason)) { Get-SanitizedStoredText -Text (Get-DefaultScopeReason -ScopeKindValue $ScopeKind) -MaxLength $script:MaxStoredReasonLength } else { (Get-SanitizedStoredText -Text $ScopeReason -MaxLength $script:MaxStoredReasonLength) }
        projects_seen = @($project)
        solution = (Get-SanitizedStoredText -Text $Resolution -MaxLength $script:MaxStoredResolutionLength)
        stats = [ordered]@{
          hit_count = 0
          verify_count = 0
          incident_count = 1
        }
        created_at = $now
        updated_at = $now
        last_verified_at = ''
        last_hit_at = ''
      }
      $maps.by_id[$caseData.case_id] = $caseData
      $createdNewCase = $true
    }

    if (-not (Test-ValidScopeKind -ScopeKindValue ([string]$caseData.scope_kind))) {
      throw ("case is missing a valid scope_kind: {0}" -f $caseData.case_id)
    }

    if ($null -eq $caseData.stats) {
      $caseData.stats = [ordered]@{ hit_count = 0; verify_count = 0; incident_count = 0 }
    }

    if ([string]::IsNullOrWhiteSpace([string]$caseData.solution) -and (-not [string]::IsNullOrWhiteSpace($Resolution))) {
      $caseData.solution = (Get-SanitizedStoredText -Text $Resolution -MaxLength $script:MaxStoredResolutionLength)
    }

    $caseData.stats.verify_count = ([int]$caseData.stats.verify_count + 1)
    $caseData.last_verified_at = $now
    $caseData.updated_at = $now
    Update-CaseScopeConvergence -CaseData $caseData -CurrentProjectId $project -ProjectSpecificEvidence:$ProjectSpecific.IsPresent

    Save-CaseMaps -Storage $storage -CaseById $maps.by_id

    $eventsData = Get-FailureEventsData -Storage $storage
    $remainingEvents = New-Object System.Collections.Generic.List[object]
    foreach ($entry in @($eventsData.events)) {
      if (($null -ne $entry) -and ([string]$entry.signature -eq $sig.signature) -and ([string]$entry.project_id -eq $project)) {
        continue
      }
      $remainingEvents.Add($entry) | Out-Null
    }
    $eventsData.events = $remainingEvents.ToArray()
    Save-FailureEventsData -Storage $storage -Data $eventsData

    $payload = [ordered]@{
      ok = $true
      action = $Action
      signature = $sig.signature
      project_id = $project
      created_new_case = $createdNewCase
      case_id = $caseData.case_id
      scope_kind = $caseData.scope_kind
      scope_confidence = $caseData.scope_confidence
      scope_reason = $caseData.scope_reason
      stats = $caseData.stats
      projects_seen = @($caseData.projects_seen)
      memory_root = $memoryRoot
    }
  }
  'inspect' {
    $maps = Get-CaseMaps -Storage $storage
    $eventsData = Get-FailureEventsData -Storage $storage
    $payload = [ordered]@{
      ok = $true
      action = $Action
      memory_root = $memoryRoot
      index_path = $storage.index_path
      failure_events_path = $storage.failure_events_path
      case_count = $maps.by_id.Count
      pending_failure_count = @($eventsData.events).Count
      cases = @($maps.index_data.cases)
    }
  }
}
return $payload
}

if ($Json) {
  $payload | ConvertTo-Json -Depth 64
} else {
  $payload
}
exit 0
