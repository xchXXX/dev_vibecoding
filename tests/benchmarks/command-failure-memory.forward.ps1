param(
  [string]$RepoRoot = '',
  [string]$UserCodexHome = '',
  [string]$CasesPath = '',
  [string]$TempRoot = '',
  [int]$CaseTimeoutSec = 60,
  [double]$MinPassRate = 0.90,
  [int]$MaxCases = 0,
  [switch]$Json
)

$ErrorActionPreference = 'Stop'

function Assert-True {
  param(
    [bool]$Condition,
    [string]$Message
  )
  if (-not $Condition) {
    throw $Message
  }
}

function Get-CodexExePath {
  $candidate = Join-Path $env:APPDATA 'npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\codex\codex.exe'
  if (-not (Test-Path -LiteralPath $candidate)) {
    throw "Codex executable not found: $candidate"
  }
  return $candidate
}

function Remove-PathIfExists {
  param([string]$PathValue)
  if (Test-Path -LiteralPath $PathValue) {
    Remove-Item -LiteralPath $PathValue -Recurse -Force
  }
}

function Register-TestTempCleanup {
  param([string]$PathValue)
  if (-not [string]::IsNullOrWhiteSpace($PathValue)) {
    $null = Register-EngineEvent PowerShell.Exiting -Action {
      if (-not [string]::IsNullOrWhiteSpace($event.MessageData) -and (Test-Path -LiteralPath $event.MessageData)) {
        Remove-Item -LiteralPath $event.MessageData -Recurse -Force -ErrorAction SilentlyContinue
      }
    } -MessageData $PathValue
  }
}

function Write-Utf8NoBomFile {
  param(
    [string]$PathValue,
    [string]$Content
  )
  $directory = Split-Path -Parent $PathValue
  if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
  }
  $encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($PathValue, $Content, $encoding)
}

function Get-RelativePathFromRoot {
  param(
    [string]$RootPath,
    [string]$TargetPath
  )
  $rootUri = [System.Uri]((Resolve-Path -LiteralPath $RootPath).Path.TrimEnd('\') + '\')
  $targetUri = [System.Uri]((Resolve-Path -LiteralPath $TargetPath).Path)
  $relativeUri = $rootUri.MakeRelativeUri($targetUri)
  return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace('/', '\')
}

function Initialize-BaseCodexHome {
  param(
    [string]$RepoRootValue,
    [string]$UserCodexHomeValue,
    [string]$BaseCodexHomeValue
  )

  Remove-PathIfExists -PathValue $BaseCodexHomeValue
  New-Item -ItemType Directory -Path $BaseCodexHomeValue -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $UserCodexHomeValue 'skills') -Destination (Join-Path $BaseCodexHomeValue 'skills') -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $UserCodexHomeValue 'config.toml') -Destination (Join-Path $BaseCodexHomeValue 'config.toml') -Force
  Remove-PathIfExists -PathValue (Join-Path $BaseCodexHomeValue 'skills\command-failure-memory')
  Copy-Item -LiteralPath (Join-Path $RepoRootValue 'skills\command-failure-memory') -Destination (Join-Path $BaseCodexHomeValue 'skills') -Recurse -Force
  foreach ($relative in @('sessions', 'tmp', 'memories')) {
    New-Item -ItemType Directory -Path (Join-Path $BaseCodexHomeValue $relative) -Force | Out-Null
  }
}

function Initialize-CaseCodexHome {
  param(
    [string]$BaseCodexHomeValue,
    [string]$CaseCodexHomeValue
  )

  Remove-PathIfExists -PathValue $CaseCodexHomeValue
  New-Item -ItemType Directory -Path $CaseCodexHomeValue -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $BaseCodexHomeValue 'skills') -Destination (Join-Path $CaseCodexHomeValue 'skills') -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $BaseCodexHomeValue 'config.toml') -Destination (Join-Path $CaseCodexHomeValue 'config.toml') -Force
  foreach ($relative in @('sessions', 'tmp', 'memories')) {
    New-Item -ItemType Directory -Path (Join-Path $CaseCodexHomeValue $relative) -Force | Out-Null
  }
}

function Get-ProcessTreeIds {
  param([int]$RootProcessId)
  $ids = New-Object System.Collections.Generic.HashSet[int]
  $queue = New-Object System.Collections.Queue
  $queue.Enqueue($RootProcessId)
  while ($queue.Count -gt 0) {
    $current = [int]$queue.Dequeue()
    if (-not $ids.Add($current)) {
      continue
    }
    $children = @(Get-CimInstance Win32_Process -Filter ("ParentProcessId = {0}" -f $current) -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessId)
    foreach ($child in $children) {
      $queue.Enqueue([int]$child)
    }
  }
  return @($ids | Sort-Object -Descending)
}

function Stop-ProcessTree {
  param([int]$RootProcessId)
  foreach ($id in Get-ProcessTreeIds -RootProcessId $RootProcessId) {
    try {
      Stop-Process -Id $id -Force -ErrorAction Stop
    } catch {
    }
  }
}

function Invoke-ExternalProcess {
  param(
    [string]$FilePath,
    [string]$Arguments = '',
    [string]$WorkingDirectory = '',
    [string]$StdinText = '',
    [int]$TimeoutSec = 180,
    [hashtable]$Environment = @{}
  )

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = $Arguments
  $psi.UseShellExecute = $false
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
    $psi.WorkingDirectory = $WorkingDirectory
  }
  foreach ($key in @($Environment.Keys)) {
    $psi.EnvironmentVariables[$key] = [string]$Environment[$key]
  }

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $psi
  $null = $process.Start()
  $stdoutTask = $process.StandardOutput.ReadToEndAsync()
  $stderrTask = $process.StandardError.ReadToEndAsync()

  if (-not [string]::IsNullOrEmpty($StdinText)) {
    $process.StandardInput.WriteLine($StdinText)
  }
  $process.StandardInput.Close()

  $timedOut = -not $process.WaitForExit($TimeoutSec * 1000)
  if ($timedOut) {
    Stop-ProcessTree -RootProcessId $process.Id
    $process.WaitForExit()
  } else {
    $process.WaitForExit()
  }

  return [PSCustomObject]@{
    ExitCode = if ($timedOut) { -1 } else { $process.ExitCode }
    TimedOut = $timedOut
    StdOut = $stdoutTask.GetAwaiter().GetResult()
    StdErr = $stderrTask.GetAwaiter().GetResult()
  }
}

function New-CaseWorkspace {
  param(
    [string]$RepoRootValue,
    [string]$CasesRootValue,
    [object]$Case
  )

  $caseRoot = Join-Path $CasesRootValue ([string]$Case.id)
  Remove-PathIfExists -PathValue $caseRoot
  New-Item -ItemType Directory -Path $caseRoot -Force | Out-Null
  $scriptPath = Join-Path $caseRoot (([string]$Case.id) + '.cmd')
  $relativeCaseRoot = Get-RelativePathFromRoot -RootPath $RepoRootValue -TargetPath $caseRoot
  $scriptContent = ([string]$Case.initial_content).Replace('__CASE_ROOT_REL__', ('.\' + $relativeCaseRoot.Replace('/', '\')))
  Write-Utf8NoBomFile -PathValue $scriptPath -Content $scriptContent
  $relativeScriptPath = Get-RelativePathFromRoot -RootPath $RepoRootValue -TargetPath $scriptPath
  return [PSCustomObject]@{
    Root = $caseRoot
    ScriptPath = $scriptPath
    RelativeCaseRoot = $relativeCaseRoot
    RelativeScriptPath = $relativeScriptPath
    CommandText = ('cmd /c .\' + $relativeScriptPath.Replace('/', '\'))
  }
}

function Get-LatestSessionPath {
  param([string]$CaseCodexHomeValue)
  $sessionsRoot = Join-Path $CaseCodexHomeValue 'sessions'
  $sessionFile = Get-ChildItem -LiteralPath $sessionsRoot -Recurse -Filter *.jsonl -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
  if ($null -eq $sessionFile) {
    return ''
  }
  return $sessionFile.FullName
}

function Get-SessionActionStatus {
  param([string]$SessionPath)
  $result = [ordered]@{
    runner_used = $false
    record_failure = $false
    query_before_retry = $false
    record_success = $false
  }
  if ([string]::IsNullOrWhiteSpace($SessionPath) -or (-not (Test-Path -LiteralPath $SessionPath))) {
    return $result
  }

  foreach ($line in Get-Content -LiteralPath $SessionPath -Encoding UTF8) {
    try {
      $entry = $line | ConvertFrom-Json -ErrorAction Stop
    } catch {
      continue
    }
    if ([string]$entry.type -ne 'response_item') {
      continue
    }
    $payload = $entry.payload
    if ($null -eq $payload -or [string]$payload.type -ne 'function_call' -or [string]$payload.name -ne 'shell_command') {
      continue
    }
    $argumentsJson = [string]$payload.arguments
    if ([string]::IsNullOrWhiteSpace($argumentsJson)) {
      continue
    }
    try {
      $toolArguments = $argumentsJson | ConvertFrom-Json -ErrorAction Stop
    } catch {
      continue
    }
    $commandText = [string]$toolArguments.command
    if ($commandText -notmatch 'command-failure-memory\.cmd') {
      continue
    }
    $result.runner_used = $true
    if ($commandText -match '(?i)-Action\s+record-failure') {
      $result.record_failure = $true
    }
    if ($commandText -match '(?i)-Action\s+query-before-retry') {
      $result.query_before_retry = $true
    }
    if ($commandText -match '(?i)-Action\s+record-success') {
      $result.record_success = $true
    }
  }

  return $result
}

function Test-MemoryContains {
  param(
    [string]$MemoryRoot,
    [string]$Needle
  )
  if ([string]::IsNullOrWhiteSpace($Needle) -or (-not (Test-Path -LiteralPath $MemoryRoot))) {
    return $false
  }
  foreach ($file in Get-ChildItem -LiteralPath $MemoryRoot -Recurse -Filter *.json -File -ErrorAction SilentlyContinue) {
    if (Select-String -LiteralPath $file.FullName -Pattern $Needle -SimpleMatch -Quiet) {
      return $true
    }
  }
  return $false
}

function New-CasePrompt {
  param(
    [string]$CommandText,
    [string]$PassMarker
  )
  return ("Run the failing command '{0}'. If the process returns 0 but the output still clearly shows failure, treat it as a failed run. Make the task pass by editing the script so it exits 0 and prints {1}, rerun to verify success, and then stop. Do not mention any skill names." -f $CommandText, $PassMarker)
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
}
if ([string]::IsNullOrWhiteSpace($UserCodexHome)) {
  $UserCodexHome = Join-Path $env:USERPROFILE '.codex'
}
if ([string]::IsNullOrWhiteSpace($CasesPath)) {
  $CasesPath = Join-Path $RepoRoot 'tests\fixtures\command-failure-memory.forward.cases.json'
}
if ([string]::IsNullOrWhiteSpace($TempRoot)) {
  $TempRoot = Join-Path $RepoRoot '.tmp\command-failure-memory-forward-bench'
}
Register-TestTempCleanup -PathValue $TempRoot

Assert-True (Test-Path -LiteralPath $RepoRoot) "Repo root missing: $RepoRoot"
Assert-True (Test-Path -LiteralPath $CasesPath) "Benchmark cases file missing: $CasesPath"
Assert-True (Test-Path -LiteralPath (Join-Path $UserCodexHome 'skills')) "User Codex skills missing under: $UserCodexHome"
Assert-True (Test-Path -LiteralPath (Join-Path $UserCodexHome 'config.toml')) "User Codex config missing under: $UserCodexHome"
Assert-True ([System.IO.Path]::GetFullPath($TempRoot).StartsWith(([System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\') + '\'), [System.StringComparison]::OrdinalIgnoreCase)) "TempRoot must stay under RepoRoot for relative benchmark commands."

$codexExe = Get-CodexExePath
$allCases = @(Get-Content -LiteralPath $CasesPath -Raw -Encoding UTF8 | ConvertFrom-Json | ForEach-Object { $_ })
$cases = if ($MaxCases -gt 0) { @($allCases | Select-Object -First $MaxCases) } else { $allCases }

Remove-PathIfExists -PathValue $TempRoot
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$casesRoot = Join-Path $TempRoot 'cases'
$homesRoot = Join-Path $TempRoot 'codex-homes'
$logsRoot = Join-Path $TempRoot 'logs'
$baseHome = Join-Path $homesRoot '_base'
foreach ($path in @($casesRoot, $homesRoot, $logsRoot)) {
  New-Item -ItemType Directory -Path $path -Force | Out-Null
}
Initialize-BaseCodexHome -RepoRootValue $RepoRoot -UserCodexHomeValue $UserCodexHome -BaseCodexHomeValue $baseHome

$powershellExe = (Get-Command pwsh).Source
$results = @()

foreach ($case in $cases) {
  $workspace = New-CaseWorkspace -RepoRootValue $RepoRoot -CasesRootValue $casesRoot -Case $case
  $caseCodexHome = Join-Path $homesRoot ([string]$case.id)
  Initialize-CaseCodexHome -BaseCodexHomeValue $baseHome -CaseCodexHomeValue $caseCodexHome

  $caseLogDir = Join-Path $logsRoot ([string]$case.id)
  New-Item -ItemType Directory -Path $caseLogDir -Force | Out-Null
  $lastMessagePath = Join-Path $caseLogDir 'last-message.txt'
  $stdoutPath = Join-Path $caseLogDir 'codex.stdout.log'
  $stderrPath = Join-Path $caseLogDir 'codex.stderr.log'
  $verifyStdoutPath = Join-Path $caseLogDir 'verify.stdout.log'
  $verifyStderrPath = Join-Path $caseLogDir 'verify.stderr.log'

  $prompt = New-CasePrompt -CommandText $workspace.CommandText -PassMarker ([string]$case.pass_marker)
  $execResult = Invoke-ExternalProcess `
    -FilePath $codexExe `
    -Arguments ('exec --full-auto --skip-git-repo-check -C "' + $RepoRoot + '" --output-last-message "' + $lastMessagePath + '" -') `
    -WorkingDirectory $RepoRoot `
    -StdinText $prompt `
    -TimeoutSec $CaseTimeoutSec `
    -Environment @{ CODEX_HOME = $caseCodexHome }

  Write-Utf8NoBomFile -PathValue $stdoutPath -Content ([string]$execResult.StdOut)
  Write-Utf8NoBomFile -PathValue $stderrPath -Content ([string]$execResult.StdErr)

  $verifyResult = Invoke-ExternalProcess `
    -FilePath $powershellExe `
    -Arguments ('-NoProfile -Command "' + $workspace.CommandText.Replace('"', '\"') + '"') `
    -WorkingDirectory $RepoRoot `
    -TimeoutSec 30

  Write-Utf8NoBomFile -PathValue $verifyStdoutPath -Content ([string]$verifyResult.StdOut)
  Write-Utf8NoBomFile -PathValue $verifyStderrPath -Content ([string]$verifyResult.StdErr)

  $sessionPath = Get-LatestSessionPath -CaseCodexHomeValue $caseCodexHome
  $actionStatus = Get-SessionActionStatus -SessionPath $sessionPath
  $memoryRoot = Join-Path $caseCodexHome 'memories\command-failure-memory'
  $memoryHit = Test-MemoryContains -MemoryRoot $memoryRoot -Needle ([string]$case.memory_match)
  $verifyText = ([string]$verifyResult.StdOut + "`n" + [string]$verifyResult.StdErr)
  $commandPassed = ($verifyResult.ExitCode -eq 0 -and $verifyText.Contains([string]$case.pass_marker))
  $sessionPassed = ($actionStatus.runner_used -and $actionStatus.record_failure -and $actionStatus.query_before_retry -and $actionStatus.record_success)
  $casePassed = (-not $execResult.TimedOut) -and ($execResult.ExitCode -eq 0) -and $commandPassed -and $memoryHit -and $sessionPassed

  $results += [ordered]@{
    id = [string]$case.id
    passed = $casePassed
    codex_exit_code = [int]$execResult.ExitCode
    codex_timed_out = [bool]$execResult.TimedOut
    command_passed = [bool]$commandPassed
    memory_hit = [bool]$memoryHit
    session_runner_used = [bool]$actionStatus.runner_used
    record_failure = [bool]$actionStatus.record_failure
    query_before_retry = [bool]$actionStatus.query_before_retry
    record_success = [bool]$actionStatus.record_success
    session_path = $sessionPath
    memory_root = $memoryRoot
    command_text = $workspace.CommandText
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
    verify_stdout_log = $verifyStdoutPath
    verify_stderr_log = $verifyStderrPath
  }
}

$passedCount = @($results | Where-Object { $_.passed }).Count
$totalCount = @($results).Count
$passRate = if ($totalCount -eq 0) { 0.0 } else { [Math]::Round(($passedCount / $totalCount), 4) }
$summary = [ordered]@{
  ok = ($passRate -ge $MinPassRate)
  min_pass_rate = $MinPassRate
  actual_pass_rate = $passRate
  passed_cases = $passedCount
  total_cases = $totalCount
  case_timeout_sec = $CaseTimeoutSec
  temp_root = $TempRoot
  cases = $results
}

if ($Json) {
  $summary | ConvertTo-Json -Depth 8
} else {
  $summary
}

if (-not [bool]$summary.ok) {
  Remove-PathIfExists -PathValue $TempRoot
  exit 1
}

Remove-PathIfExists -PathValue $TempRoot
exit 0
