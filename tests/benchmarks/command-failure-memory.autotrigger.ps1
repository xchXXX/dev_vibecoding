param(
  [string]$RepoRoot = '',
  [string]$UserCodexHome = '',
  [string]$CasesPath = '',
  [string]$TempCodexHome = '',
  [string]$Workdir = '',
  [int]$TriggerToleranceTokens = 200,
  [int]$MinSkillLoadDelta = 1000,
  [double]$MinPassRate = 0.90,
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

function Initialize-BenchmarkCodexHome {
  param(
    [string]$RepoRootValue,
    [string]$UserCodexHomeValue,
    [string]$TempCodexHomeValue
  )

  if (Test-Path -LiteralPath $TempCodexHomeValue) {
    Remove-Item -LiteralPath $TempCodexHomeValue -Recurse -Force
  }

  New-Item -ItemType Directory -Path $TempCodexHomeValue -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $UserCodexHomeValue 'skills') -Destination (Join-Path $TempCodexHomeValue 'skills') -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $UserCodexHomeValue 'config.toml') -Destination (Join-Path $TempCodexHomeValue 'config.toml') -Force
  Copy-Item -LiteralPath (Join-Path $RepoRootValue 'skills\command-failure-memory') -Destination (Join-Path $TempCodexHomeValue 'skills\command-failure-memory') -Recurse -Force

  foreach ($relative in @('sessions', 'tmp', 'memories')) {
    New-Item -ItemType Directory -Path (Join-Path $TempCodexHomeValue $relative) -Force | Out-Null
  }
}

function Invoke-CodexExec {
  param(
    [string]$CodexExePath,
    [string]$PromptText,
    [string]$TempCodexHomeValue
  )

  $env:CODEX_HOME = $TempCodexHomeValue
  $output = $PromptText | & $CodexExePath exec --json --ephemeral --skip-git-repo-check --sandbox read-only -
  $turnCompleted = $output | Where-Object { $_ -like '{"type":"turn.completed"*' } | Select-Object -Last 1
  $turnFailed = $output | Where-Object { $_ -like '{"type":"turn.failed"*' } | Select-Object -Last 1

  if ($turnFailed) {
    $failedObject = $turnFailed | ConvertFrom-Json
    throw ("Codex exec failed: {0}" -f $failedObject.error.message)
  }
  if (-not $turnCompleted) {
    throw ("Missing turn.completed event. Raw output: {0}" -f ($output -join "`n"))
  }

  $completedObject = $turnCompleted | ConvertFrom-Json
  return [ordered]@{
    input_tokens = [int]$completedObject.usage.input_tokens
    cached_input_tokens = [int]$completedObject.usage.cached_input_tokens
    output_tokens = [int]$completedObject.usage.output_tokens
  }
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
}
if ([string]::IsNullOrWhiteSpace($UserCodexHome)) {
  $UserCodexHome = Join-Path $env:USERPROFILE '.codex'
}
if ([string]::IsNullOrWhiteSpace($CasesPath)) {
  $CasesPath = Join-Path $RepoRoot 'tests\fixtures\command-failure-memory.autotrigger.cases.json'
}
if ([string]::IsNullOrWhiteSpace($TempCodexHome)) {
  $TempCodexHome = Join-Path $RepoRoot '.tmp\command-failure-memory-autotrigger-bench'
}
Register-TestTempCleanup -PathValue $TempCodexHome
if ([string]::IsNullOrWhiteSpace($Workdir)) {
  $Workdir = Split-Path -Parent $RepoRoot
}

Assert-True (Test-Path -LiteralPath $CasesPath) "Benchmark cases file missing: $CasesPath"
Assert-True (Test-Path -LiteralPath (Join-Path $UserCodexHome 'skills')) "User Codex skills missing under: $UserCodexHome"
Assert-True (Test-Path -LiteralPath (Join-Path $UserCodexHome 'config.toml')) "User Codex config missing under: $UserCodexHome"
Assert-True (Test-Path -LiteralPath $Workdir) "Benchmark workdir missing: $Workdir"

$codexExe = Get-CodexExePath
Initialize-BenchmarkCodexHome -RepoRootValue $RepoRoot -UserCodexHomeValue $UserCodexHome -TempCodexHomeValue $TempCodexHome
$cases = Get-Content -LiteralPath $CasesPath -Raw -Encoding UTF8 | ConvertFrom-Json
$exitCode = 0

Push-Location $Workdir
try {
  $baselineUsage = Invoke-CodexExec -CodexExePath $codexExe -PromptText '内部 benchmark：只回复 OK。' -TempCodexHomeValue $TempCodexHome
  $calibrationPrompt = '$command-failure-memory 场景：pnpm install 报错 ERR_PNPM_FETCH_500，准备重试。现在先不要解决问题，只回复 OK。'
  $calibrationUsage = Invoke-CodexExec -CodexExePath $codexExe -PromptText $calibrationPrompt -TempCodexHomeValue $TempCodexHome
  $calibrationDelta = [int]$calibrationUsage.input_tokens - [int]$baselineUsage.input_tokens

  Assert-True ($calibrationDelta -ge $MinSkillLoadDelta) ("Calibration failed: explicit skill load delta too small ({0} < {1})" -f $calibrationDelta, $MinSkillLoadDelta)

  $results = @()
  foreach ($case in @($cases)) {
    $autoUsage = Invoke-CodexExec -CodexExePath $codexExe -PromptText ([string]$case.prompt) -TempCodexHomeValue $TempCodexHome
    $explicitUsage = Invoke-CodexExec -CodexExePath $codexExe -PromptText ('$command-failure-memory ' + [string]$case.prompt) -TempCodexHomeValue $TempCodexHome
    $tokenGap = [int]$explicitUsage.input_tokens - [int]$autoUsage.input_tokens
    $triggered = ($tokenGap -le $TriggerToleranceTokens)
    $results += [ordered]@{
      id = [string]$case.id
      triggered = $triggered
      token_gap = $tokenGap
      auto_input_tokens = [int]$autoUsage.input_tokens
      explicit_input_tokens = [int]$explicitUsage.input_tokens
      cached_input_tokens = [int]$autoUsage.cached_input_tokens
    }
  }

  $triggeredCount = @($results | Where-Object { $_.triggered }).Count
  $totalCount = @($results).Count
  $passRate = if ($totalCount -eq 0) { 0.0 } else { [Math]::Round(($triggeredCount / $totalCount), 4) }
  $summary = [ordered]@{
    ok = ($passRate -ge $MinPassRate)
    min_pass_rate = $MinPassRate
    actual_pass_rate = $passRate
    triggered_cases = $triggeredCount
    total_cases = $totalCount
    trigger_tolerance_tokens = $TriggerToleranceTokens
    calibration = [ordered]@{
      baseline_input_tokens = [int]$baselineUsage.input_tokens
      explicit_input_tokens = [int]$calibrationUsage.input_tokens
      skill_load_delta = $calibrationDelta
      min_skill_load_delta = $MinSkillLoadDelta
    }
    cases = $results
  }

  if ($Json) {
    $summary | ConvertTo-Json -Depth 8
  } else {
    $summary
  }

  if (-not [bool]$summary.ok) {
    $exitCode = 1
  }
} finally {
  Pop-Location
  if (Test-Path -LiteralPath $TempCodexHome) {
    Remove-Item -LiteralPath $TempCodexHome -Recurse -Force -ErrorAction SilentlyContinue
  }
}

exit $exitCode
