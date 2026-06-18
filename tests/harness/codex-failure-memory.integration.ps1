param()

$ErrorActionPreference = 'Stop'

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
  throw 'This Codex failure-memory suite requires Windows.'
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$TempRoot = Join-Path $env:TEMP ('ai-harness-codex-memory-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$null = Register-EngineEvent PowerShell.Exiting -Action {
  if (-not [string]::IsNullOrWhiteSpace($event.MessageData) -and (Test-Path -LiteralPath $event.MessageData)) {
    Remove-Item -LiteralPath $event.MessageData -Recurse -Force -ErrorAction SilentlyContinue
  }
} -MessageData $TempRoot

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

function Cleanup-TempRoot {
  if (Test-Path -LiteralPath $TempRoot) {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}

function Assert-True {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) { throw $Message }
}

function Assert-Equal {
  param([object]$Expected, [object]$Actual, [string]$Message)
  if ($Expected -ne $Actual) {
    throw ("{0} (expected: {1}; actual: {2})" -f $Message, $Expected, $Actual)
  }
}

function Assert-ContainsText {
  param([string]$Text, [string]$Expected, [string]$Message)
  if ([string]::IsNullOrWhiteSpace($Text) -or (-not $Text.Contains($Expected))) {
    throw ("{0} (missing: {1})" -f $Message, $Expected)
  }
}

function Assert-NotContainsText {
  param([string]$Text, [string]$Unexpected, [string]$Message)
  if (-not [string]::IsNullOrWhiteSpace($Text) -and $Text.Contains($Unexpected)) {
    throw ("{0} (unexpected: {1})" -f $Message, $Unexpected)
  }
}

function Read-Json {
  param([string]$PathValue)
  return (Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-Json {
  param([string]$PathValue, [object]$Data)
  Set-Content -LiteralPath $PathValue -Value ($Data | ConvertTo-Json -Depth 64) -Encoding UTF8
}

function Import-ScriptPrefix {
  param(
    [string]$ScriptPath,
    [string]$CutMarker
  )
  $content = Get-Content -LiteralPath $ScriptPath -Raw -Encoding UTF8
  $cutIndex = $content.IndexOf($CutMarker)
  if ($cutIndex -lt 0) {
    throw ("cut marker not found in script: {0}" -f $ScriptPath)
  }
  $prefix = $content.Substring(0, $cutIndex)
  return [scriptblock]::Create($prefix)
}

function Get-MemoryLockNameForTest {
  param(
    [string]$ScriptPath,
    [string]$MemoryRoot
  )
  . (Import-ScriptPrefix -ScriptPath $ScriptPath -CutMarker "if ([string]::IsNullOrWhiteSpace(`$CodexHome)) {") -Action 'inspect'
  return (Get-MemoryLockName -MemoryRoot $MemoryRoot)
}

function Invoke-PowerShellFile {
  param(
    [string]$FilePath,
    [object[]]$Arguments = @(),
    [hashtable]$Environment = @{}
  )
  $stdoutPath = Join-Path $TempRoot ([guid]::NewGuid().ToString('N') + '.stdout.log')
  $stderrPath = Join-Path $TempRoot ([guid]::NewGuid().ToString('N') + '.stderr.log')
  $argumentLine = (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $FilePath) + $Arguments | ForEach-Object {
    $value = [string]$_
    if ($value -match '[\s"]') { '"' + ($value -replace '"', '\"') + '"' } else { $value }
  }) -join ' '
  $envBackup = @{}
  try {
    foreach ($key in @($Environment.Keys)) {
      $envBackup[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
      [Environment]::SetEnvironmentVariable($key, [string]$Environment[$key], 'Process')
    }
    $process = Start-Process -FilePath (Get-Command pwsh).Source -ArgumentList $argumentLine -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $lines = @()
    if (Test-Path -LiteralPath $stdoutPath) { $lines += @(Get-Content -LiteralPath $stdoutPath -Encoding UTF8) }
    if (Test-Path -LiteralPath $stderrPath) { $lines += @(Get-Content -LiteralPath $stderrPath -Encoding UTF8) }
    return [PSCustomObject]@{
      ExitCode = $process.ExitCode
      Text = ($lines -join "`n")
      Json = $null
    }
  } finally {
    foreach ($key in @($Environment.Keys)) {
      [Environment]::SetEnvironmentVariable($key, $envBackup[$key], 'Process')
    }
    foreach ($path in @($stdoutPath, $stderrPath)) {
      if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
      }
    }
  }
}

function Run-TestCase {
  param([string]$Name, [scriptblock]$Body)
  try {
    & $Body
    $script:PassCount += 1
    Write-Host ("PASS {0}" -f $Name)
  } catch {
    $script:Failures.Add(("{0}: {1}" -f $Name, $_.Exception.Message)) | Out-Null
    Write-Host ("FAIL {0}" -f $Name)
    Write-Host ("  {0}" -f $_.Exception.Message)
  }
}

function Copy-HarnessRoot {
  param(
    [string]$SourceRoot,
    [string]$DestinationRoot
  )
  New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
  foreach ($relative in @('skills\command-failure-memory')) {
    $sourcePath = Join-Path $SourceRoot $relative
    $destinationPath = Join-Path $DestinationRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destinationPath) -Force | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Recurse -Force
  }
}

function New-Scenario {
  param([string]$Name)
  $scenarioRoot = Join-Path $TempRoot $Name
  $scenarioHarness = Join-Path $scenarioRoot 'harness'
  Copy-HarnessRoot -SourceRoot $HarnessRoot -DestinationRoot $scenarioHarness
  $codexHome = Join-Path $scenarioRoot 'codex-home'
  return [PSCustomObject]@{
    Root = $scenarioRoot
    Harness = $scenarioHarness
    CodexHome = $codexHome
    MemoryRoot = Join-Path $codexHome 'memories\command-failure-memory'
  }
}

function Get-MemoryScriptPath {
  param([object]$Scenario)
  return (Join-Path $Scenario.Harness 'skills\command-failure-memory\scripts\command-failure-memory.ps1')
}

function Invoke-MemoryAction {
  param(
    [object]$Scenario,
    [string]$Action,
    [string]$ProjectId = '',
    [string]$CommandText = '',
    [string]$ErrorText = '',
    [string]$Resolution = '',
    [string]$ScopeKind = '',
    [double]$ScopeConfidence = [double]::NaN,
    [string]$ScopeReason = '',
    [switch]$ProjectSpecific,
    [hashtable]$Environment = @{}
  )

  $args = @(
    '-Action', $Action,
    '-CodexHome', $Scenario.CodexHome,
    '-Json'
  )
  if (-not [string]::IsNullOrWhiteSpace($ProjectId)) {
    $args += @('-ProjectId', $ProjectId)
  }
  if (-not [string]::IsNullOrWhiteSpace($CommandText)) {
    $args += @('-CommandText', $CommandText)
  }
  if (-not [string]::IsNullOrWhiteSpace($ErrorText)) {
    $args += @('-ErrorText', $ErrorText)
  }
  if (-not [string]::IsNullOrWhiteSpace($Resolution)) {
    $args += @('-Resolution', $Resolution)
  }
  if (-not [string]::IsNullOrWhiteSpace($ScopeKind)) {
    $args += @('-ScopeKind', $ScopeKind)
  }
  if (-not [double]::IsNaN($ScopeConfidence)) {
    $args += @('-ScopeConfidence', [string]$ScopeConfidence)
  }
  if (-not [string]::IsNullOrWhiteSpace($ScopeReason)) {
    $args += @('-ScopeReason', $ScopeReason)
  }
  if ($ProjectSpecific) {
    $args += '-ProjectSpecific'
  }

  $result = Invoke-PowerShellFile -FilePath (Get-MemoryScriptPath -Scenario $Scenario) -Arguments $args -Environment $Environment
  if (-not [string]::IsNullOrWhiteSpace($result.Text)) {
    try {
      $result.Json = ($result.Text | ConvertFrom-Json)
    } catch {
      $result.Json = $null
    }
  }
  return $result
}

function Read-Index {
  param([object]$Scenario)
  return (Read-Json -PathValue (Join-Path $Scenario.MemoryRoot 'index.json'))
}

function Read-Case {
  param([object]$Scenario, [string]$CaseId)
  return (Read-Json -PathValue (Join-Path $Scenario.MemoryRoot ("cases/{0}.json" -f $CaseId)))
}

function Read-FailureEvents {
  param([object]$Scenario)
  return (Read-Json -PathValue (Join-Path $Scenario.MemoryRoot 'runtime/failure-events.json'))
}

Run-TestCase -Name 'Gate: query-before-retry requires prior failure record' -Body {
  $scenario = New-Scenario -Name 'query-gate-before-failure'
  $query = Invoke-MemoryAction -Scenario $scenario -Action 'query-before-retry' -ProjectId 'proj-a' -CommandText 'npm test' -ErrorText 'command not found'
  Assert-Equal 0 $query.ExitCode 'query should return exit code 0 when gate not met'
  Assert-True ($null -ne $query.Json) 'query should emit parseable JSON'
  Assert-True (-not [bool]$query.Json.query_permitted) 'query should be blocked before first failure record'
  Assert-Equal 'retry_gate_not_met' ([string]$query.Json.reason) 'query should report retry gate reason'
}

Run-TestCase -Name 'Rule R1: failure record then retry query returns historical suggestion' -Body {
  $scenario = New-Scenario -Name 'record-then-query'
  $seed = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'npm test' -ErrorText 'command not found' -Resolution 'install node' -ScopeKind 'candidate_global' -ScopeReason 'missing environment tool'
  Assert-Equal 0 $seed.ExitCode 'seed case should succeed'
  Assert-True ([bool]$seed.Json.created_new_case) 'seed should create new case'

  $recordFailure = Invoke-MemoryAction -Scenario $scenario -Action 'record-failure' -ProjectId 'proj-a' -CommandText 'npm test' -ErrorText 'command not found'
  Assert-Equal 0 $recordFailure.ExitCode 'record-failure should succeed'
  Assert-True ([bool]$recordFailure.Json.query_should_happen_before_retry) 'record-failure should indicate retry query gate'

  $query = Invoke-MemoryAction -Scenario $scenario -Action 'query-before-retry' -ProjectId 'proj-a' -CommandText 'npm test' -ErrorText 'command not found'
  Assert-Equal 0 $query.ExitCode 'query-after-failure should succeed'
  Assert-True ([bool]$query.Json.query_permitted) 'query should be permitted after failure record'
  Assert-Equal 1 ([int]@($query.Json.suggestions).Count) 'query should return one matching suggestion'
  Assert-Equal ([string]$seed.Json.case_id) ([string]$query.Json.suggestions[0].case_id) 'query suggestion should point to seeded case'

  $case = Read-Case -Scenario $scenario -CaseId ([string]$seed.Json.case_id)
  Assert-Equal 1 ([int]$case.stats.hit_count) 'query should increase hit_count'
}

Run-TestCase -Name 'Rule R2/R3: equivalent success updates stats without creating new case' -Body {
  $scenario = New-Scenario -Name 'equivalent-success-no-new-case'
  $seed = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'pip install -r requirements.txt' -ErrorText 'ssl error' -Resolution 'set TLS env' -ScopeKind 'candidate_project' -ScopeReason 'project mirror config'
  Assert-Equal 0 $seed.ExitCode 'seed should succeed'
  Assert-True ([bool]$seed.Json.created_new_case) 'first success should create case'

  $second = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'pip install -r requirements.txt' -ErrorText 'ssl error' -Resolution 'set TLS env again'
  Assert-Equal 0 $second.ExitCode 'second equivalent success should succeed'
  Assert-True (-not [bool]$second.Json.created_new_case) 'equivalent success must not create a new case'

  $index = Read-Index -Scenario $scenario
  Assert-Equal 1 ([int]@($index.cases).Count) 'index should still keep a single case for equivalent signature'
  $case = Read-Case -Scenario $scenario -CaseId ([string]$seed.Json.case_id)
  Assert-Equal 2 ([int]$case.stats.verify_count) 'verify_count should increase on equivalent success'
  Assert-Equal 1 ([int]$case.stats.incident_count) 'incident_count should not increase on equivalent success'
}

Run-TestCase -Name 'Rule R4: new case must provide scope_kind' -Body {
  $scenario = New-Scenario -Name 'missing-scope-kind'
  $result = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'pnpm install' -ErrorText 'permission denied' -Resolution 'fix ACL'
  Assert-True ($result.ExitCode -ne 0) 'record-success without scope_kind should fail when case does not exist'
  Assert-ContainsText -Text $result.Text -Expected 'scope_kind' -Message 'failure output should mention scope_kind gate'
}

Run-TestCase -Name 'Scope convergence: candidate_project upgrades to global after multi-project verification' -Body {
  $scenario = New-Scenario -Name 'scope-upgrade-global'
  $seed = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'go test ./...' -ErrorText 'toolchain missing' -Resolution 'install go' -ScopeKind 'candidate_project' -ScopeReason 'initial project candidate'
  Assert-Equal 0 $seed.ExitCode 'seed candidate_project should succeed'

  $second = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-b' -CommandText 'go test ./...' -ErrorText 'toolchain missing' -Resolution 'install go'
  Assert-Equal 0 $second.ExitCode 'second project verification should succeed'
  Assert-Equal 'global' ([string]$second.Json.scope_kind) 'candidate_project should converge to global after two projects'
  Assert-Equal 2 ([int]@($second.Json.projects_seen).Count) 'projects_seen should include two projects'
}

Run-TestCase -Name 'Scope convergence: candidate_global downgrades to project with project-specific evidence' -Body {
  $scenario = New-Scenario -Name 'scope-downgrade-project'
  $seed = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'python manage.py migrate' -ErrorText 'module not found' -Resolution 'fix venv path' -ScopeKind 'candidate_global' -ScopeReason 'initial global candidate'
  Assert-Equal 0 $seed.ExitCode 'seed candidate_global should succeed'

  $second = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'python manage.py migrate' -ErrorText 'module not found' -Resolution 'fix venv path' -ProjectSpecific
  Assert-Equal 0 $second.ExitCode 'project-specific verification should succeed'
  Assert-Equal 'project' ([string]$second.Json.scope_kind) 'candidate_global should downgrade to project with project-specific evidence'
}

Run-TestCase -Name 'Bad path: invalid case_id in index is rejected to block out-of-root writes' -Body {
  $scenario = New-Scenario -Name 'invalid-case-id-guard'
  $seed = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'npm ci' -ErrorText 'network timeout' -Resolution 'retry with mirror' -ScopeKind 'candidate_global'
  Assert-Equal 0 $seed.ExitCode 'seed should succeed'
  $recordFailure = Invoke-MemoryAction -Scenario $scenario -Action 'record-failure' -ProjectId 'proj-a' -CommandText 'npm ci' -ErrorText 'network timeout'
  Assert-Equal 0 $recordFailure.ExitCode 'record-failure should succeed before tampering'

  $indexPath = Join-Path $scenario.MemoryRoot 'index.json'
  $index = Read-Json -PathValue $indexPath
  $index.cases[0].case_id = '../outside'
  Write-Json -PathValue $indexPath -Data $index

  $query = Invoke-MemoryAction -Scenario $scenario -Action 'query-before-retry' -ProjectId 'proj-a' -CommandText 'npm ci' -ErrorText 'network timeout'
  Assert-True ($query.ExitCode -ne 0) 'query should fail when index contains invalid case_id'
  Assert-ContainsText -Text $query.Text -Expected 'invalid case_id' -Message 'failure should explicitly reject invalid case_id traversal'
}

Run-TestCase -Name 'Bad path: case storage junction escaping memory root is rejected' -Body {
  $scenario = New-Scenario -Name 'memory-root-junction-guard'
  $outsideCases = Join-Path $scenario.Root 'outside-cases'
  New-Item -ItemType Directory -Path $outsideCases -Force | Out-Null
  New-Item -ItemType Directory -Path $scenario.MemoryRoot -Force | Out-Null
  New-Item -ItemType Junction -Path (Join-Path $scenario.MemoryRoot 'cases') -Target $outsideCases | Out-Null

  $result = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'npm run build' -ErrorText 'ENOENT' -Resolution 'install node' -ScopeKind 'candidate_global'
  Assert-True ($result.ExitCode -ne 0) 'record-success should fail when cases path escapes via junction'
  Assert-ContainsText -Text $result.Text -Expected 'reparse point traversal' -Message 'guard should reject junction-based escape'
}

Run-TestCase -Name 'Validation: scope_confidence must stay within schema range' -Body {
  $scenario = New-Scenario -Name 'scope-confidence-range'
  $result = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'cargo test' -ErrorText 'toolchain missing' -Resolution 'install rustup' -ScopeKind 'candidate_global' -ScopeConfidence 1.5
  Assert-True ($result.ExitCode -ne 0) 'record-success should reject scope_confidence greater than 1'
  Assert-ContainsText -Text $result.Text -Expected 'between 0 and 1' -Message 'failure should mention scope_confidence range'
}

Run-TestCase -Name 'Redaction: secrets are scrubbed before persistence' -Body {
  $scenario = New-Scenario -Name 'secret-redaction'
  $commandText = 'curl -H "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz123456" https://alice:supersecret@example.com/api AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
  $errorText = "request failed password=hunter2`n-----BEGIN PRIVATE KEY-----`nSECRET-DATA`n-----END PRIVATE KEY-----"
  $resolution = 'set token=github_pat_abcdefghijklmnopqrstuvwxyz123456 and rotate password=swordfish'

  $result = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText $commandText -ErrorText $errorText -Resolution $resolution -ScopeKind 'candidate_global'
  Assert-Equal 0 $result.ExitCode 'record-success should succeed with redaction scenario'

  $casePath = Join-Path $scenario.MemoryRoot ("cases/{0}.json" -f [string]$result.Json.case_id)
  $raw = Get-Content -LiteralPath $casePath -Raw -Encoding UTF8
  Assert-NotContainsText -Text $raw -Unexpected 'supersecret' -Message 'case file must not persist URI credentials'
  Assert-NotContainsText -Text $raw -Unexpected 'hunter2' -Message 'case file must not persist password literal'
  Assert-NotContainsText -Text $raw -Unexpected 'SECRET-DATA' -Message 'case file must not persist private key content'
  Assert-NotContainsText -Text $raw -Unexpected 'github_pat_' -Message 'case file must not persist github token literal'
  Assert-NotContainsText -Text $raw -Unexpected 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' -Message 'case file must not persist env-style secret literal'
}

Run-TestCase -Name 'Capacity: pending failure events are capped' -Body {
  $scenario = New-Scenario -Name 'pending-event-cap'
  for ($i = 1; $i -le 140; $i++) {
    $result = Invoke-MemoryAction -Scenario $scenario -Action 'record-failure' -ProjectId ("proj-{0}" -f $i) -CommandText ("cmd-{0}" -f $i) -ErrorText ("err-{0}" -f $i)
    Assert-Equal 0 $result.ExitCode ("record-failure should succeed for event {0}" -f $i)
  }

  $events = Read-FailureEvents -Scenario $scenario
  Assert-Equal 128 ([int]@($events.events).Count) 'failure-events should be capped at 128 entries'
  Assert-True ((@($events.events | ForEach-Object { $_.project_id }) -contains 'proj-140')) 'latest pending event should be retained after cap'
}

Run-TestCase -Name 'Concurrency: parallel record-failure updates preserve all increments' -Body {
  $scenario = New-Scenario -Name 'parallel-record-failure'
  $scriptPath = Get-MemoryScriptPath -Scenario $scenario
  $jobs = @()
  try {
    foreach ($index in 1..8) {
      $jobs += Start-Job -ScriptBlock {
        param($InnerScriptPath, $InnerCodexHome)
        & pwsh -NoProfile -ExecutionPolicy Bypass -File $InnerScriptPath -Action record-failure -CodexHome $InnerCodexHome -ProjectId 'proj-a' -CommandText 'npm ci' -ErrorText 'network timeout' -Json | Out-Null
        if ($LASTEXITCODE -ne 0) {
          throw ("record-failure worker exited with code {0}" -f $LASTEXITCODE)
        }
      } -ArgumentList $scriptPath, $scenario.CodexHome
    }
    $null = Wait-Job -Job $jobs -Timeout 120
    foreach ($job in $jobs) {
      Assert-Equal 'Completed' ([string]$job.State) 'parallel record-failure worker should succeed'
    }
  } finally {
    foreach ($job in $jobs) {
      if ($null -ne $job) {
        try {
          Receive-Job -Job $job -Keep | Out-Null
        } catch {
        }
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
      }
    }
  }

  $events = Read-FailureEvents -Scenario $scenario
  Assert-Equal 1 ([int]@($events.events).Count) 'parallel updates should still keep a single event per project/signature'
  Assert-Equal 8 ([int]$events.events[0].failure_count) 'parallel updates should preserve every increment under lock'
}

Run-TestCase -Name 'Memory lock name normalizes memory root case on Windows' -Body {
  $scriptPath = Join-Path $HarnessRoot 'skills\command-failure-memory\scripts\command-failure-memory.ps1'
  $pathLower = (Join-Path $TempRoot 'lock-case\memory-root').ToLowerInvariant()
  $pathUpper = $pathLower.ToUpperInvariant()
  $lowerLock = Get-MemoryLockNameForTest -ScriptPath $scriptPath -MemoryRoot $pathLower
  $upperLock = Get-MemoryLockNameForTest -ScriptPath $scriptPath -MemoryRoot $pathUpper
  Assert-Equal $lowerLock $upperLock 'memory lock name should stay stable across path casing differences on Windows'
}

Run-TestCase -Name 'Schema: missing schema_version is normalized before rewrite' -Body {
  $scenario = New-Scenario -Name 'schema-version-normalized'
  $seed = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'npm test' -ErrorText 'command not found' -Resolution 'install node' -ScopeKind 'candidate_global'
  Assert-Equal 0 $seed.ExitCode 'seed should succeed before schema tamper'

  $casePath = Join-Path $scenario.MemoryRoot ("cases/{0}.json" -f [string]$seed.Json.case_id)
  $case = Read-Json -PathValue $casePath
  $case.PSObject.Properties.Remove('schema_version')
  Write-Json -PathValue $casePath -Data $case

  $recordFailure = Invoke-MemoryAction -Scenario $scenario -Action 'record-failure' -ProjectId 'proj-a' -CommandText 'npm test' -ErrorText 'command not found'
  Assert-Equal 0 $recordFailure.ExitCode 'record-failure should succeed after schema tamper'
  $query = Invoke-MemoryAction -Scenario $scenario -Action 'query-before-retry' -ProjectId 'proj-a' -CommandText 'npm test' -ErrorText 'command not found'
  Assert-Equal 0 $query.ExitCode 'query should rewrite case metadata after schema tamper'

  $rewrittenCase = Read-Json -PathValue $casePath
  Assert-Equal '1.0' ([string]$rewrittenCase.schema_version) 'case rewrite should restore schema_version'
}

Run-TestCase -Name 'Signature: multi-line errors dedupe by first line' -Body {
  $scenario = New-Scenario -Name 'error-first-line-signature'
  $first = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'pnpm test' -ErrorText "fatal: tool missing`nstack line a" -Resolution 'install tool' -ScopeKind 'candidate_global'
  Assert-Equal 0 $first.ExitCode 'first case should succeed'

  $second = Invoke-MemoryAction -Scenario $scenario -Action 'record-success' -ProjectId 'proj-a' -CommandText 'pnpm test' -ErrorText "fatal: tool missing`nstack line b" -Resolution 'install tool again'
  Assert-Equal 0 $second.ExitCode 'second case should succeed'
  Assert-True (-not [bool]$second.Json.created_new_case) 'same first-line error should reuse existing case'

  $index = Read-Index -Scenario $scenario
  Assert-Equal 1 ([int]@($index.cases).Count) 'same first-line error should keep a single case'
}

Write-Host ("TOTAL PASS {0}" -f $script:PassCount)
if ($script:Failures.Count -gt 0) {
  Write-Host ("TOTAL FAIL {0}" -f $script:Failures.Count)
  foreach ($failure in $script:Failures) {
    Write-Host ("  {0}" -f $failure)
  }
  Cleanup-TempRoot
  exit 1
}

Write-Host 'ALL TESTS PASSED'
Cleanup-TempRoot
exit 0
