param()

$ErrorActionPreference = 'Stop'

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw 'This control-plane integration suite requires Windows.'
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$TempRoot = Join-Path $env:TEMP ('ai-harness-control-plane-v3-tests-' + [guid]::NewGuid().ToString('N'))
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

function Assert-ContainsText {
    param([string]$Text, [string]$Expected, [string]$Message)
    if ([string]::IsNullOrWhiteSpace($Text) -or (-not $Text.Contains($Expected))) {
        throw ("{0} (missing: {1})" -f $Message, $Expected)
    }
}

function Read-Json {
    param([string]$PathValue)
    return (Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-Json {
    param([string]$PathValue, [object]$Data)
    Set-Content -LiteralPath $PathValue -Value ($Data | ConvertTo-Json -Depth 100) -Encoding UTF8
}

function Invoke-PowerShellFile {
    param(
        [string]$FilePath,
        [object[]]$Arguments = @()
    )

    $stdoutPath = Join-Path $TempRoot ('stdout-' + [guid]::NewGuid().ToString('N') + '.log')
    $stderrPath = Join-Path $TempRoot ('stderr-' + [guid]::NewGuid().ToString('N') + '.log')
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $FilePath) + $Arguments
    $process = Start-Process -FilePath (Get-Command pwsh).Source -ArgumentList $argList -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($capturePath in @($stdoutPath, $stderrPath)) {
        if (Test-Path -LiteralPath $capturePath) {
            Get-Content -LiteralPath $capturePath -Encoding UTF8 | ForEach-Object { $lines.Add([string]$_) | Out-Null }
            Remove-Item -LiteralPath $capturePath -Force
        }
    }

    return [PSCustomObject]@{
        ExitCode = $process.ExitCode
        Text     = ($lines.ToArray() -join "`n")
        Lines    = $lines.ToArray()
    }
}

function Convert-ResultToJson {
    param([object]$Result)

    $json = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($Result.Text)) {
            $json = ($Result.Text | ConvertFrom-Json)
        }
    } catch {
        $json = $null
    }

    return [PSCustomObject]@{
        ExitCode = $Result.ExitCode
        Text     = $Result.Text
        Json     = $json
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

function New-StateObject {
    param([string]$TaskId)

    return [ordered]@{
        task_id         = $TaskId
        title           = 'Control-plane v3 integration fixture'
        status          = 'active'
        owner           = 'main-coordinator'
        objective       = 'Exercise the task state control-plane contract.'
        scope_in        = @(
            'tests/README.md',
            'tests/harness/README.md',
            'tests/harness/control-plane.integration.ps1'
        )
        scope_out       = @(
            'skills/global-task-orchestrator/**'
        )
        acceptance      = @(
            'state.json remains the only source of truth',
            'task.md can be regenerated from state.json'
        )
        stop_conditions = @(
            'validation reports schema or contract drift'
        )
        decisions       = @(
            'task.md is a human-readable summary',
            'events.jsonl is optional append-only telemetry'
        )
        current_phase   = 'test_sync'
        subtasks        = @(
            [ordered]@{
                subtask_id    = 'ST-control-plane-tests'
                title         = 'Rewrite control-plane integration suite'
                role          = 'test-verifier'
                status        = 'pending'
                dependencies  = @()
                read_paths    = @(
                    'tests/README.md',
                    'tests/harness/README.md'
                )
                write_paths   = @(
                    'tests/harness/control-plane.integration.ps1'
                )
                assignment    = [ordered]@{
                    goal         = 'Cover init-task, sync-task-md, append-event, build-subtask-brief, and validate.'
                    must_include = @(
                        'happy path coverage',
                        'bad path coverage'
                    )
                    verification = @(
                        'validate succeeds on the happy path'
                    )
                }
            }
        )
        updated_at      = '2026-05-29T00:00:00+08:00'
        version         = 1
    }
}

function New-VerificationContractFixture {
    return [ordered]@{
        minimal_repro    = 'Run validate with current_phase=code_impl and no verification_contract.'
        hit_proof        = 'The failure or pass outcome must prove the verification_contract gate is active.'
        diagnostic_checks = @(
            'validate fails before verification_contract is filled'
        )
        acceptance_checks = @(
            'validate passes after verification_contract is filled'
        )
        non_goals        = @(
            'Do not add new phases'
        )
        review_evidence  = @(
            'repro_before_fix',
            'pass_after_fix',
            'hit_proof_observed',
            'relevant_regression_ok'
        )
    }
}

function New-Scenario {
    param([string]$Name)

    $scenarioRoot = Join-Path $TempRoot $Name
    $repoRoot = Join-Path $scenarioRoot 'repo'
    New-Item -ItemType Directory -Path $repoRoot -Force | Out-Null

    $skillSource = Join-Path $HarnessRoot 'skills/global-task-orchestrator'
    $skillsRoot = Join-Path $repoRoot 'skills'
    New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null
    Copy-Item -LiteralPath $skillSource -Destination $skillsRoot -Recurse -Force

    $agentsRoot = Join-Path $repoRoot 'agents'
    New-Item -ItemType Directory -Path $agentsRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $HarnessRoot 'agents/codex-role-map.json') -Destination (Join-Path $agentsRoot 'codex-role-map.json') -Force
    Copy-Item -LiteralPath (Join-Path $HarnessRoot 'agents/manifest.json') -Destination (Join-Path $agentsRoot 'manifest.json') -Force

    return [PSCustomObject]@{
        Name            = $Name
        RepoRoot        = $repoRoot
        TaskId          = ('task-' + $Name)
        OrchestratorPath = Join-Path $repoRoot 'skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1'
    }
}

function Get-TaskDir {
    param([object]$Scenario)
    return (Join-Path $Scenario.RepoRoot ("docs/ai/tasks/{0}" -f $Scenario.TaskId))
}

function Get-StatePath {
    param([object]$Scenario)
    return (Join-Path (Get-TaskDir -Scenario $Scenario) 'state.json')
}

function Get-TaskMdPath {
    param([object]$Scenario)
    return (Join-Path (Get-TaskDir -Scenario $Scenario) 'task.md')
}

function Get-EventsPath {
    param([object]$Scenario)
    return (Join-Path (Get-TaskDir -Scenario $Scenario) 'events.jsonl')
}

function Get-ManifestPath {
    param([object]$Scenario)
    return (Join-Path $Scenario.RepoRoot 'agents/manifest.json')
}

function Get-RoleMapPath {
    param([object]$Scenario)
    return (Join-Path $Scenario.RepoRoot 'agents/codex-role-map.json')
}

function Write-StateFixture {
    param(
        [object]$Scenario,
        [object]$State
    )

    $taskDir = Get-TaskDir -Scenario $Scenario
    New-Item -ItemType Directory -Path $taskDir -Force | Out-Null
    Write-Json -PathValue (Get-StatePath -Scenario $Scenario) -Data $State
}

function Write-TaskMdFixture {
    param(
        [object]$Scenario,
        [string]$Content = "# Task Summary`n"
    )

    Set-Content -LiteralPath (Get-TaskMdPath -Scenario $Scenario) -Value $Content -Encoding UTF8
}

function Write-EventsFixture {
    param(
        [object]$Scenario,
        [string[]]$Lines = @()
    )

    $eventsPath = Get-EventsPath -Scenario $Scenario
    if ($Lines.Count -eq 0) {
        [System.IO.File]::WriteAllText($eventsPath, '')
        return
    }
    Set-Content -LiteralPath $eventsPath -Value $Lines -Encoding UTF8
}

function Invoke-OrchestratorAction {
    param(
        [object]$Scenario,
        [string]$Action,
        [object[]]$Arguments = @()
    )

    $baseArgs = @('-Action', $Action, '-RepoRoot', $Scenario.RepoRoot)
    $result = Invoke-PowerShellFile -FilePath $Scenario.OrchestratorPath -Arguments ($baseArgs + $Arguments + @('-Json'))
    return (Convert-ResultToJson -Result $result)
}

function Invoke-NewTask {
    param(
        [object]$Scenario,
        [string]$Topic
    )

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'new-task' -Arguments @(
        '-Topic', $Topic
    ))
}

function Invoke-InitTask {
    param([object]$Scenario)

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'init-task' -Arguments @(
        '-TaskId', $Scenario.TaskId,
        '-Title', 'control-plane-v3-integration-fixture',
        '-Owner', 'main-coordinator',
        '-Objective', 'exercise-task-state-contract'
    ))
}

function Invoke-SyncTaskMd {
    param([object]$Scenario)

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'sync-task-md' -Arguments @(
        '-TaskId', $Scenario.TaskId
    ))
}

function Invoke-AppendEvent {
    param([object]$Scenario)

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'append-event' -Arguments @(
        '-TaskId', $Scenario.TaskId,
        '-Actor', 'test-verifier',
        '-Type', 'note_added',
        '-Summary', 'appended-event-for-integration-coverage'
    ))
}

function Invoke-BuildSubtaskBrief {
    param(
        [object]$Scenario,
        [string]$SubtaskId
    )

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'build-subtask-brief' -Arguments @(
        '-TaskId', $Scenario.TaskId,
        '-SubtaskId', $SubtaskId
    ))
}

function Invoke-BuildExecuteHandoff {
    param([object]$Scenario)

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'build-execute-handoff' -Arguments @(
        '-TaskId', $Scenario.TaskId
    ))
}

function Invoke-Validate {
    param([object]$Scenario)

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'validate' -Arguments @(
        '-TaskId', $Scenario.TaskId
    ))
}

function Invoke-ValidateWithoutTaskId {
    param([object]$Scenario)

    return (Invoke-OrchestratorAction -Scenario $Scenario -Action 'validate')
}

function Test-InitTaskHappyPath {
    $scenario = New-Scenario -Name 'init-task-happy-path'
    $result = Invoke-InitTask -Scenario $scenario

    Assert-True ($result.ExitCode -eq 0) 'init-task should return exit code 0'
    Assert-True ($null -ne $result.Json) 'init-task should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'init-task should return ok=true'
    Assert-True (Test-Path -LiteralPath (Get-StatePath -Scenario $scenario)) 'init-task should create state.json'
    Assert-True (Test-Path -LiteralPath (Get-TaskMdPath -Scenario $scenario)) 'init-task should create task.md'
    Assert-True (Test-Path -LiteralPath (Get-EventsPath -Scenario $scenario)) 'init-task should create events.jsonl'

    $validate = Invoke-Validate -Scenario $scenario
    Assert-True ($validate.ExitCode -eq 0) 'validate should pass after init-task'
    Assert-True ($null -ne $validate.Json) 'validate happy path should emit parseable JSON'
    Assert-True ([bool]$validate.Json.ok) 'validate should return ok=true after init-task'
}

function Test-NewTaskGeneratesUniqueIds {
    $scenario = New-Scenario -Name 'new-task-unique-ids'

    $first = Invoke-NewTask -Scenario $scenario -Topic 'shared-task-topic'
    $second = Invoke-NewTask -Scenario $scenario -Topic 'shared-task-topic'

    Assert-True ($first.ExitCode -eq 0) 'first new-task should return exit code 0'
    Assert-True ($second.ExitCode -eq 0) 'second new-task should return exit code 0'
    Assert-True ($null -ne $first.Json) 'first new-task should emit parseable JSON'
    Assert-True ($null -ne $second.Json) 'second new-task should emit parseable JSON'
    Assert-True ([bool]$first.Json.ok) 'first new-task should return ok=true'
    Assert-True ([bool]$second.Json.ok) 'second new-task should return ok=true'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$first.Json.task_id)) 'first new-task should return a task_id'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$second.Json.task_id)) 'second new-task should return a task_id'
    Assert-True ([string]$first.Json.task_id -ne [string]$second.Json.task_id) 'same-topic new-task calls should produce different task_id values'
}

function Test-SyncTaskMdHappyPath {
    $scenario = New-Scenario -Name 'sync-task-md-happy-path'
    $init = Invoke-InitTask -Scenario $scenario
    Assert-True ($init.ExitCode -eq 0) 'sync-task-md happy path requires init-task to succeed'

    $statePath = Get-StatePath -Scenario $scenario
    $state = Read-Json -PathValue $statePath
    $state.title = 'Control-plane summary rewritten'
    $state.current_phase = 'review'
    $state.decisions = @(
        'state.json remains authoritative',
        'task.md summary was regenerated'
    )
    Write-Json -PathValue $statePath -Data $state

    $result = Invoke-SyncTaskMd -Scenario $scenario
    Assert-True ($result.ExitCode -eq 0) 'sync-task-md should return exit code 0'
    Assert-True ($null -ne $result.Json) 'sync-task-md should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'sync-task-md should return ok=true'

    $taskMd = Get-Content -LiteralPath (Get-TaskMdPath -Scenario $scenario) -Raw -Encoding UTF8
    Assert-ContainsText -Text $taskMd -Expected 'Control-plane summary rewritten' -Message 'task.md should reflect the rewritten title'
    Assert-ContainsText -Text $taskMd -Expected 'review' -Message 'task.md should reflect the rewritten current phase'
    foreach ($section in @('## 目标', '## 关键决定', '## 当前阶段', '## 子任务')) {
        Assert-ContainsText -Text $taskMd -Expected $section -Message ("task.md should include structured section {0}" -f $section)
    }
}

function Test-AppendEventHappyPath {
    $scenario = New-Scenario -Name 'append-event-happy-path'
    $init = Invoke-InitTask -Scenario $scenario
    Assert-True ($init.ExitCode -eq 0) 'append-event happy path requires init-task to succeed'

    $result = Invoke-AppendEvent -Scenario $scenario
    Assert-True ($result.ExitCode -eq 0) 'append-event should return exit code 0'
    Assert-True ($null -ne $result.Json) 'append-event should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'append-event should return ok=true'

    $lines = Get-Content -LiteralPath (Get-EventsPath -Scenario $scenario) -Encoding UTF8
    Assert-True ($lines.Count -ge 1) 'append-event should append at least one JSONL line'
    Assert-ContainsText -Text ($lines -join "`n") -Expected 'note_added' -Message 'events.jsonl should contain the appended event type'

    $validate = Invoke-Validate -Scenario $scenario
    Assert-True ($validate.ExitCode -eq 0) 'validate should still pass after append-event'
    Assert-True ([bool]$validate.Json.ok) 'validate should remain ok after append-event'
}

function Test-BuildSubtaskBriefHappyPath {
    $scenario = New-Scenario -Name 'build-subtask-brief-happy-path'
    $init = Invoke-InitTask -Scenario $scenario
    Assert-True ($init.ExitCode -eq 0) 'build-subtask-brief happy path requires init-task to succeed'

    $state = New-StateObject -TaskId $scenario.TaskId
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario

    $result = Invoke-BuildSubtaskBrief -Scenario $scenario -SubtaskId 'ST-control-plane-tests'
    Assert-True ($result.ExitCode -eq 0) 'build-subtask-brief should return exit code 0'
    Assert-True (($null -ne $result.Json) -or (-not [string]::IsNullOrWhiteSpace($result.Text))) 'build-subtask-brief should emit JSON or text'
    Assert-ContainsText -Text $result.Text -Expected 'ST-control-plane-tests' -Message 'subtask brief should include subtask_id'
    Assert-ContainsText -Text $result.Text -Expected 'tests/harness/control-plane.integration.ps1' -Message 'subtask brief should include write scope'
    Assert-ContainsText -Text $result.Text -Expected 'test-verifier' -Message 'subtask brief should include role'
}

function Test-BuildExecuteHandoffHappyPath {
    $scenario = New-Scenario -Name 'build-execute-handoff-happy-path'
    $init = Invoke-InitTask -Scenario $scenario
    Assert-True ($init.ExitCode -eq 0) 'build-execute-handoff happy path requires init-task to succeed'

    $state = New-StateObject -TaskId $scenario.TaskId
    $state.objective = '定稿 Execute Window 的起步合同。'
    $state.scope_in = @('docs/ARCHITECTURE.md', 'tests/README.md')
    $state.scope_out = @('hooks/**')
    $state.acceptance = @('handoff 明确首批子任务', '执行窗口不需要猜范围')
    $state.stop_conditions = @('发现已定稿合同与代码现实冲突')
    $state.current_phase = 'planning'
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario -Content "# 任务摘要`n`n当前任务合同已定稿。`n"

    $result = Invoke-BuildExecuteHandoff -Scenario $scenario
    Assert-True ($result.ExitCode -eq 0) 'build-execute-handoff should return exit code 0'
    Assert-True (($null -ne $result.Json) -or (-not [string]::IsNullOrWhiteSpace($result.Text))) 'build-execute-handoff should emit JSON or text'
    Assert-ContainsText -Text $result.Text -Expected $scenario.TaskId -Message 'execute handoff should include task_id'
    Assert-ContainsText -Text $result.Text -Expected 'planning' -Message 'execute handoff should include current_phase'
    Assert-ContainsText -Text $result.Text -Expected '定稿 Execute Window 的起步合同。' -Message 'execute handoff should include objective'
    Assert-ContainsText -Text $result.Text -Expected 'docs/ARCHITECTURE.md' -Message 'execute handoff should include scope_in'
    Assert-ContainsText -Text $result.Text -Expected 'hooks/**' -Message 'execute handoff should include scope_out'
    Assert-ContainsText -Text $result.Text -Expected 'handoff 明确首批子任务' -Message 'execute handoff should include acceptance'
    Assert-ContainsText -Text $result.Text -Expected '发现已定稿合同与代码现实冲突' -Message 'execute handoff should include stop conditions'
    Assert-ContainsText -Text $result.Text -Expected 'task.md' -Message 'execute handoff should include task.md read path'
    Assert-ContainsText -Text $result.Text -Expected 'ST-control-plane-tests' -Message 'execute handoff should include first subtask summary'
    Assert-ContainsText -Text $result.Text -Expected '先委派子代理' -Message 'execute handoff should require delegation before execution'
    Assert-ContainsText -Text $result.Text -Expected '若 `current_phase` 仍为 `planning`' -Message 'execute handoff should explain how to start from planning'
    Assert-ContainsText -Text $result.Text -Expected '不要重新 `init-task`' -Message 'execute handoff should include re-init prohibition'
    Assert-ContainsText -Text $result.Text -Expected '不要把新开执行窗口误判成新任务' -Message 'execute handoff should include task identity prohibition'
    Assert-ContainsText -Text $result.Text -Expected '不要跳过子代理直接收口' -Message 'execute handoff should include delegation prohibition'
}

function Test-MissingTaskIdFails {
    $scenario = New-Scenario -Name 'missing-taskid'
    $result = Invoke-ValidateWithoutTaskId -Scenario $scenario

    Assert-True ($null -ne $result.Json) 'missing TaskId should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing TaskId should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'TaskId' -Message 'validate should mention the missing TaskId'
}

function Test-StateMissingRequiredFieldsFails {
    $scenario = New-Scenario -Name 'state-missing-required-fields'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.Remove('current_phase')
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing required state field should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing required state field should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'current_phase' -Message 'validate should mention the missing state field'
}

function Test-InvalidCurrentPhaseFails {
    $scenario = New-Scenario -Name 'invalid-current-phase'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.current_phase = 'freeform-phase'
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'invalid current_phase should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'invalid current_phase should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'current_phase' -Message 'validate should mention current_phase'
    Assert-ContainsText -Text $result.Text -Expected 'planning' -Message 'validate should mention the allowed current_phase values'
}

function Test-CodeImplMissingVerificationContractFails {
    $scenario = New-Scenario -Name 'code-impl-missing-verification-contract'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.current_phase = 'code_impl'
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'code_impl without verification_contract should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'code_impl without verification_contract should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'verification_contract' -Message 'validate should mention verification_contract'
    Assert-ContainsText -Text $result.Text -Expected 'code_impl' -Message 'validate should mention the code_impl gate'
}

function Test-ReviewMissingEvidenceCoverageFails {
    $scenario = New-Scenario -Name 'review-missing-evidence-coverage'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.current_phase = 'review'
    $state.verification_contract = New-VerificationContractFixture
    $state.subtasks[0].status = 'completed'
    $state.subtasks[0].result = [ordered]@{
        status                    = 'completed'
        written_by                = 'test-verifier'
        written_role              = 'test-verifier'
        summary                   = 'Completed with partial review evidence.'
        changed_files             = @(
            'tests/harness/control-plane.integration.ps1'
        )
        planned_files_not_changed = @()
        verification              = [ordered]@{
            commands = @(
                'pwsh -NoProfile -ExecutionPolicy Bypass -File tests/harness/control-plane.integration.ps1'
            )
            result   = 'failed as expected'
        }
        deviations                = @()
        blocked_by                = @()
        risks                     = @()
        follow_up                 = @()
        review_evidence           = [ordered]@{
            repro_before_fix = 'validate failed before the contract was filled.'
        }
    }
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'review missing evidence coverage should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'review missing evidence coverage should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'review_evidence' -Message 'validate should mention review_evidence coverage'
    Assert-ContainsText -Text $result.Text -Expected 'pass_after_fix' -Message 'validate should mention an uncovered evidence slot'
}

function Test-CompletedTaskWithOpenSubtasksFails {
    $scenario = New-Scenario -Name 'completed-task-with-open-subtasks'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.status = 'completed'
    $state.current_phase = 'review'
    $state.verification_contract = New-VerificationContractFixture
    $state.subtasks[0].status = 'pending'
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'completed task with open subtasks should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'completed task with open subtasks should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'state.json.status=completed' -Message 'validate should mention the completed-task closure gate'
    Assert-ContainsText -Text $result.Text -Expected 'ST-control-plane-tests' -Message 'validate should mention the unfinished subtask id'
}

function Test-ReinitExistingTaskFails {
    $scenario = New-Scenario -Name 'reinit-existing-task-fails'
    $first = Invoke-InitTask -Scenario $scenario
    Assert-True ($first.ExitCode -eq 0) 'first init-task should succeed before duplicate init check'

    $second = Invoke-InitTask -Scenario $scenario
    Assert-True ($second.ExitCode -ne 0) 'second init-task should fail for the same task_id'
    Assert-ContainsText -Text $second.Text -Expected 'already exists' -Message 'duplicate init-task should mention existing task_id'
}

function Test-DuplicateSubtaskIdFails {
    $scenario = New-Scenario -Name 'duplicate-subtask-id'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.subtasks += $state.subtasks[0]
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'duplicate subtask_id should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'duplicate subtask_id should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'subtask_id' -Message 'validate should mention duplicate subtask_id'
}

function Test-PendingSubtaskMissingPathsFails {
    foreach ($status in @('pending', 'in_progress')) {
        $scenario = New-Scenario -Name ("{0}-subtask-missing-paths" -f $status)
        $state = New-StateObject -TaskId $scenario.TaskId
        $state.subtasks[0].status = $status
        $state.subtasks[0].read_paths = @()
        $state.subtasks[0].write_paths = @()
        Write-StateFixture -Scenario $scenario -State $state
        Write-TaskMdFixture -Scenario $scenario
        Write-EventsFixture -Scenario $scenario

        $result = Invoke-Validate -Scenario $scenario
        Assert-True ($null -ne $result.Json) ("{0} subtask missing path fields should emit parseable JSON" -f $status)
        Assert-True (-not [bool]$result.Json.ok) ("{0} subtask missing path fields should fail validate" -f $status)
        Assert-ContainsText -Text $result.Text -Expected 'read_paths' -Message ("validate should mention missing read_paths for {0}" -f $status)
        Assert-ContainsText -Text $result.Text -Expected 'write_paths' -Message ("validate should mention missing write_paths for {0}" -f $status)
    }
}

function Test-CompletedSubtaskMissingResultFieldsFails {
    $scenario = New-Scenario -Name 'completed-subtask-missing-result-fields'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.subtasks[0].status = 'completed'
    $state.subtasks[0].result = [ordered]@{
        status                 = 'completed'
        changed_files          = @()
        planned_files_not_changed = @()
        deviations             = @()
        blocked_by             = @()
        risks                  = @()
        follow_up              = @()
        written_by             = 'test-verifier'
    }
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'completed subtask missing result fields should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'completed subtask missing result fields should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'result.summary' -Message 'validate should mention missing result.summary'
    Assert-ContainsText -Text $result.Text -Expected 'written_role' -Message 'validate should mention missing written_role'
    Assert-ContainsText -Text $result.Text -Expected 'verification' -Message 'validate should mention missing verification'
}

function Test-BlockedSubtaskMissingResultFails {
    $scenario = New-Scenario -Name 'blocked-subtask-missing-result'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.subtasks[0].status = 'blocked'
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'blocked subtask missing result should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'blocked subtask missing result should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'result' -Message 'validate should mention missing result for blocked subtask'
}

function Test-CompletedSubtaskChangedFilesOutsideWritePathsFails {
    $scenario = New-Scenario -Name 'completed-subtask-changed-files-outside-write-paths'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.subtasks[0].status = 'completed'
    $state.subtasks[0].result = [ordered]@{
        status                   = 'completed'
        written_by               = 'test-verifier'
        written_role             = 'test-verifier'
        summary                  = 'Completed with unauthorized file mutation.'
        changed_files            = @(
            'tests/harness/control-plane.integration.ps1',
            'skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1'
        )
        planned_files_not_changed = @()
        verification             = [ordered]@{
            commands = @(
                'pwsh -NoProfile -ExecutionPolicy Bypass -File tests/harness/control-plane.integration.ps1'
            )
            result   = 'failed as expected'
        }
        deviations               = @()
        blocked_by               = @()
        risks                    = @()
        follow_up                = @()
    }
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'completed subtask changed_files outside write_paths should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'completed subtask changed_files outside write_paths should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'changed_files' -Message 'validate should mention changed_files scope mismatch'
    Assert-ContainsText -Text $result.Text -Expected 'write_paths' -Message 'validate should mention write_paths scope mismatch'
}

function Test-WrittenRoleMismatchFails {
    $scenario = New-Scenario -Name 'written-role-mismatch'
    $state = New-StateObject -TaskId $scenario.TaskId
    $state.subtasks[0].status = 'completed'
    $state.subtasks[0].result = [ordered]@{
        status                   = 'completed'
        written_by               = 'reviewer'
        written_role             = 'reviewer'
        summary                  = 'Completed by an unexpected role.'
        changed_files            = @(
            'tests/harness/control-plane.integration.ps1'
        )
        planned_files_not_changed = @()
        verification             = [ordered]@{
            commands = @(
                'pwsh -NoProfile -ExecutionPolicy Bypass -File tests/harness/control-plane.integration.ps1'
            )
            result   = 'failed as expected'
        }
        deviations               = @()
        blocked_by               = @()
        risks                    = @()
        follow_up                = @()
    }
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'written_role mismatch should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'written_role mismatch should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'written_role' -Message 'validate should mention written_role mismatch'
    Assert-ContainsText -Text $result.Text -Expected 'subtask.role' -Message 'validate should bind written_role to subtask.role'
}

function Test-ManifestOrRoleMapExtraRoleFails {
    foreach ($fixtureKind in @('manifest', 'role-map')) {
        $scenario = New-Scenario -Name ("{0}-extra-role" -f $fixtureKind)
        $state = New-StateObject -TaskId $scenario.TaskId
        Write-StateFixture -Scenario $scenario -State $state
        Write-TaskMdFixture -Scenario $scenario
        Write-EventsFixture -Scenario $scenario

        if ($fixtureKind -eq 'manifest') {
            $manifest = Read-Json -PathValue (Get-ManifestPath -Scenario $scenario)
            $items = @($manifest.items)
            $items += [PSCustomObject]@{
                id          = 'unmapped-reviewer'
                source      = 'agents/unmapped-reviewer.md'
                target      = 'unmapped-reviewer.md'
                description = 'Unmapped reviewer'
                tools       = @('Read')
                model       = 'inherit'
            }
            $manifest.items = $items
            Write-Json -PathValue (Get-ManifestPath -Scenario $scenario) -Data $manifest
        } else {
            $roleMap = Read-Json -PathValue (Get-RoleMapPath -Scenario $scenario)
            $roleMap.roles | Add-Member -NotePropertyName 'unmapped-reviewer' -NotePropertyValue ([PSCustomObject]@{
                agent_type = 'default'
                label = 'Unmapped Reviewer'
                allow_write = $false
                allow_shell = $false
            })
            Write-Json -PathValue (Get-RoleMapPath -Scenario $scenario) -Data $roleMap
        }

        $result = Invoke-Validate -Scenario $scenario
        Assert-True ($null -ne $result.Json) ("{0} extra role should emit parseable JSON" -f $fixtureKind)
        Assert-True (-not [bool]$result.Json.ok) ("{0} extra role should fail validate" -f $fixtureKind)
        Assert-ContainsText -Text $result.Text -Expected 'role' -Message ("validate should mention role alignment for {0}" -f $fixtureKind)
        if ($fixtureKind -eq 'manifest') {
            Assert-ContainsText -Text $result.Text -Expected 'manifest' -Message 'validate should mention manifest alignment'
        } else {
            Assert-ContainsText -Text $result.Text -Expected 'role-map' -Message 'validate should mention role-map alignment'
        }
    }
}

function Test-RootArrayFieldStringFails {
    foreach ($fieldName in @('scope_in', 'acceptance')) {
        $scenario = New-Scenario -Name ("root-array-field-string-{0}" -f $fieldName)
        $state = New-StateObject -TaskId $scenario.TaskId
        $state.$fieldName = 'tests/harness/control-plane.integration.ps1'
        Write-StateFixture -Scenario $scenario -State $state
        Write-TaskMdFixture -Scenario $scenario
        Write-EventsFixture -Scenario $scenario

        $result = Invoke-Validate -Scenario $scenario
        Assert-True ($null -ne $result.Json) ("root array field {0} type mismatch should emit parseable JSON" -f $fieldName)
        Assert-True (-not [bool]$result.Json.ok) ("root array field {0} type mismatch should fail validate" -f $fieldName)
        Assert-ContainsText -Text $result.Text -Expected $fieldName -Message ("validate should mention root array field {0}" -f $fieldName)
        Assert-ContainsText -Text $result.Text -Expected 'array' -Message ("validate should mention array type for root field {0}" -f $fieldName)
    }
}

function Test-SubtaskArrayFieldStringFails {
    $cases = @(
        @{ Field = 'read_paths'; Value = 'tests/README.md' },
        @{ Field = 'write_paths'; Value = 'tests/harness/control-plane.integration.ps1' },
        @{ Field = 'must_include'; Value = 'happy path coverage'; Parent = 'assignment' }
    )

    foreach ($case in $cases) {
        $scenario = New-Scenario -Name ("subtask-array-field-string-{0}" -f $case.Field)
        $state = New-StateObject -TaskId $scenario.TaskId
        if ($case.ContainsKey('Parent')) {
            $state.subtasks[0].assignment.($case.Field) = $case.Value
        } else {
            $state.subtasks[0].($case.Field) = $case.Value
        }
        Write-StateFixture -Scenario $scenario -State $state
        Write-TaskMdFixture -Scenario $scenario
        Write-EventsFixture -Scenario $scenario

        $result = Invoke-Validate -Scenario $scenario
        Assert-True ($null -ne $result.Json) ("subtask array field {0} type mismatch should emit parseable JSON" -f $case.Field)
        Assert-True (-not [bool]$result.Json.ok) ("subtask array field {0} type mismatch should fail validate" -f $case.Field)
        if ($case.ContainsKey('Parent')) {
            Assert-ContainsText -Text $result.Text -Expected ("assignment.{0}" -f $case.Field) -Message ("validate should mention assignment array field {0}" -f $case.Field)
        } else {
            Assert-ContainsText -Text $result.Text -Expected $case.Field -Message ("validate should mention subtask array field {0}" -f $case.Field)
        }
        Assert-ContainsText -Text $result.Text -Expected 'array' -Message ("validate should mention array type for subtask field {0}" -f $case.Field)
    }
}

function Test-ResultArrayFieldStringFails {
    $cases = @(
        @{ Name = 'result.verification.commands'; Mutate = {
                param($subtask)
                $subtask.status = 'completed'
                $subtask.result = [ordered]@{
                    status        = 'completed'
                    written_role  = 'test-verifier'
                    summary       = 'Completed with malformed verification commands.'
                    changed_files = @('tests/harness/control-plane.integration.ps1')
                    verification  = [ordered]@{
                        commands = 'powershell -File tests/harness/control-plane.integration.ps1'
                    }
                    risks         = @()
                    follow_up     = @()
                }
            }
        },
        @{ Name = 'blocked_by'; Mutate = {
                param($subtask)
                $subtask.status = 'blocked'
                $subtask.result = [ordered]@{
                    status        = 'blocked'
                    summary       = 'Blocked with malformed blocked_by.'
                    blocked_by    = 'missing-runtime-support'
                    changed_files = @()
                    verification  = @(
                        'validate should reject blocked_by string'
                    )
                    risks         = @()
                    follow_up     = @()
                }
            }
        }
    )

    foreach ($case in $cases) {
        $scenario = New-Scenario -Name (($case.Name -replace '[^a-zA-Z0-9]+', '-').ToLowerInvariant())
        $state = New-StateObject -TaskId $scenario.TaskId
        & $case.Mutate $state.subtasks[0]
        Write-StateFixture -Scenario $scenario -State $state
        Write-TaskMdFixture -Scenario $scenario
        Write-EventsFixture -Scenario $scenario

        $result = Invoke-Validate -Scenario $scenario
        Assert-True ($null -ne $result.Json) ("result array field {0} type mismatch should emit parseable JSON" -f $case.Name)
        Assert-True (-not [bool]$result.Json.ok) ("result array field {0} type mismatch should fail validate" -f $case.Name)
        Assert-ContainsText -Text $result.Text -Expected $case.Name -Message ("validate should mention result array field {0}" -f $case.Name)
        Assert-ContainsText -Text $result.Text -Expected 'array' -Message ("validate should mention array type for result field {0}" -f $case.Name)
    }
}

function Test-InvalidEventJsonLineFails {
    $scenario = New-Scenario -Name 'invalid-event-json-line'
    $state = New-StateObject -TaskId $scenario.TaskId
    Write-StateFixture -Scenario $scenario -State $state
    Write-TaskMdFixture -Scenario $scenario
    Write-EventsFixture -Scenario $scenario -Lines @(
        '{"ts":"2026-05-29T00:00:00+08:00","actor":"main-coordinator","type":"task_created","summary":"valid line","refs":["docs/ai/tasks/task-invalid-event-json-line/state.json"]}',
        '{"ts":"2026-05-29T00:00:01+08:00","actor":"main-coordinator",'
    )

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'invalid JSONL line should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'invalid JSONL line should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'events.jsonl' -Message 'validate should mention events.jsonl'
    Assert-ContainsText -Text $result.Text -Expected 'JSON' -Message 'validate should mention invalid JSON line'
}

Run-TestCase -Name 'Happy path: init-task creates state/task/events and validate passes' -Body { Test-InitTaskHappyPath }
Run-TestCase -Name 'Happy path: new-task produces unique task_id values for the same topic' -Body { Test-NewTaskGeneratesUniqueIds }
Run-TestCase -Name 'Happy path: sync-task-md rewrites summary' -Body { Test-SyncTaskMdHappyPath }
Run-TestCase -Name 'Happy path: append-event keeps validate green' -Body { Test-AppendEventHappyPath }
Run-TestCase -Name 'Happy path: build-subtask-brief outputs a subtask brief' -Body { Test-BuildSubtaskBriefHappyPath }
Run-TestCase -Name 'Happy path: build-execute-handoff outputs Execute Window handoff text' -Body { Test-BuildExecuteHandoffHappyPath }
Run-TestCase -Name 'Bad path: missing TaskId should fail validate' -Body { Test-MissingTaskIdFails }
Run-TestCase -Name 'Bad path: duplicate init-task for an existing task_id should fail' -Body { Test-ReinitExistingTaskFails }
Run-TestCase -Name 'Bad path: state.json missing required fields should fail validate' -Body { Test-StateMissingRequiredFieldsFails }
Run-TestCase -Name 'Bad path: invalid current_phase should fail validate' -Body { Test-InvalidCurrentPhaseFails }
Run-TestCase -Name 'Bad path: code_impl without verification_contract should fail validate' -Body { Test-CodeImplMissingVerificationContractFails }
Run-TestCase -Name 'Bad path: review without evidence slot coverage should fail validate' -Body { Test-ReviewMissingEvidenceCoverageFails }
Run-TestCase -Name 'Bad path: completed task with unfinished subtasks should fail validate' -Body { Test-CompletedTaskWithOpenSubtasksFails }
Run-TestCase -Name 'Bad path: duplicate subtask_id should fail validate' -Body { Test-DuplicateSubtaskIdFails }
Run-TestCase -Name 'Bad path: pending or in_progress subtask missing read_paths/write_paths should fail validate' -Body { Test-PendingSubtaskMissingPathsFails }
Run-TestCase -Name 'Bad path: completed subtask missing result.summary/changed_files/verification should fail validate' -Body { Test-CompletedSubtaskMissingResultFieldsFails }
Run-TestCase -Name 'Bad path: blocked subtask missing result should fail validate' -Body { Test-BlockedSubtaskMissingResultFails }
Run-TestCase -Name 'Bad path: completed subtask changed_files outside write_paths should fail validate' -Body { Test-CompletedSubtaskChangedFilesOutsideWritePathsFails }
Run-TestCase -Name 'Bad path: written_role mismatch with subtask.role should fail validate' -Body { Test-WrittenRoleMismatchFails }
Run-TestCase -Name 'Bad path: manifest or role-map extra role should fail validate' -Body { Test-ManifestOrRoleMapExtraRoleFails }
Run-TestCase -Name 'Bad path: root array field written as string should fail validate' -Body { Test-RootArrayFieldStringFails }
Run-TestCase -Name 'Bad path: subtask array field written as string should fail validate' -Body { Test-SubtaskArrayFieldStringFails }
Run-TestCase -Name 'Bad path: result array field written as string should fail validate' -Body { Test-ResultArrayFieldStringFails }
Run-TestCase -Name 'Bad path: invalid JSON line in events.jsonl should fail validate' -Body { Test-InvalidEventJsonLineFails }

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

