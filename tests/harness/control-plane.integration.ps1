param()

$ErrorActionPreference = 'Stop'

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw 'This control-plane integration suite requires Windows.'
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$TemplateTaskId = 'contract-first-dispatch-batch3-4-20260403-153206-gtm2'
$TemplateRunDir = Join-Path $HarnessRoot ("docs/ai/runs/{0}" -f $TemplateTaskId)
$TemplatePlanDoc = Join-Path $HarnessRoot 'docs/plans/contract-first-dispatch.md'
$TemplatePlanJson = Join-Path $HarnessRoot 'docs/plans/contract-first-dispatch-batch3-4-20260403-153206-gtm2.plan.json'
$TemplateRoleMapPath = Join-Path $HarnessRoot 'agents/codex-role-map.json'
$TemplateManifestPath = Join-Path $HarnessRoot 'agents/manifest.json'
$TempRoot = Join-Path $env:TEMP ('ai-harness-control-plane-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

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

function Set-ObjectProperty {
    param([object]$Object, [string]$Name, $Value)

    if ($null -eq $Object.PSObject.Properties[$Name]) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    } else {
        $Object.$Name = $Value
    }
}

function Invoke-PowerShellFile {
    param(
        [string]$FilePath,
        [object[]]$Arguments = @()
    )

    $stdoutPath = Join-Path $TempRoot ('stdout-' + [guid]::NewGuid().ToString('N') + '.log')
    $stderrPath = Join-Path $TempRoot ('stderr-' + [guid]::NewGuid().ToString('N') + '.log')
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $FilePath) + $Arguments
    $process = Start-Process -FilePath (Get-Command powershell.exe).Source -ArgumentList $argList -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

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

function New-Scenario {
    param([string]$Name)

    $scenarioRoot = Join-Path $TempRoot $Name
    $repoRoot = Join-Path $scenarioRoot 'repo'
    New-Item -ItemType Directory -Path $repoRoot -Force | Out-Null

    $skillTargetRoot = Join-Path $repoRoot 'skills/global-task-orchestrator'
    New-Item -ItemType Directory -Path $skillTargetRoot -Force | Out-Null
    Copy-Item -Path (Join-Path $HarnessRoot 'skills/global-task-orchestrator/scripts') -Destination $skillTargetRoot -Recurse -Force

    $planTargetDir = Join-Path $repoRoot 'docs/plans'
    New-Item -ItemType Directory -Path $planTargetDir -Force | Out-Null
    Copy-Item -LiteralPath $TemplatePlanDoc -Destination (Join-Path $planTargetDir 'contract-first-dispatch.md') -Force
    Copy-Item -LiteralPath $TemplatePlanJson -Destination (Join-Path $planTargetDir 'contract-first-dispatch-batch3-4-20260403-153206-gtm2.plan.json') -Force

    $runParent = Join-Path $repoRoot 'docs/ai/runs'
    $runDir = Join-Path $runParent $TemplateTaskId
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    Copy-Item -Path (Join-Path $TemplateRunDir '*') -Destination $runDir -Recurse -Force

    $agentsDir = Join-Path $repoRoot 'agents'
    New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
    Copy-Item -LiteralPath $TemplateRoleMapPath -Destination (Join-Path $agentsDir 'codex-role-map.json') -Force
    Copy-Item -LiteralPath $TemplateManifestPath -Destination (Join-Path $agentsDir 'manifest.json') -Force

    return [PSCustomObject]@{
        RepoRoot = $repoRoot
        TaskId = $TemplateTaskId
        RunDir = $runDir
    }
}

function Get-WorkOrderPath {
    param([object]$Scenario, [string]$WorkOrderId)
    return (Join-Path $Scenario.RunDir ("work_orders/{0}.json" -f $WorkOrderId))
}

function Get-ReturnPacketPath {
    param([object]$Scenario, [string]$WorkOrderId)
    $workOrder = Read-Json -PathValue (Get-WorkOrderPath -Scenario $Scenario -WorkOrderId $WorkOrderId)
    return (Join-Path $Scenario.RepoRoot ([string]$workOrder.return_packet_path))
}

function Get-RoleMapPath {
    param([object]$Scenario)
    return (Join-Path $Scenario.RepoRoot 'agents/codex-role-map.json')
}

function Get-ManifestPath {
    param([object]$Scenario)
    return (Join-Path $Scenario.RepoRoot 'agents/manifest.json')
}

function New-FrozenSourcePlanPair {
    param(
        [string]$RepoRoot,
        [string]$TaskId,
        [string]$PlanId,
        [string]$DocRelative,
        [string]$JsonRelative,
        [string]$Goal
    )

    $docPath = Join-Path $RepoRoot $DocRelative
    $jsonPath = Join-Path $RepoRoot $JsonRelative

    @(
        '# Frozen Plan',
        '',
        ('- task_id: {0}' -f $TaskId),
        ('- plan_id: {0}' -f $PlanId),
        '- status: frozen',
        '',
        '## Goal',
        ('- {0}' -f $Goal),
        '',
        '## Scope',
        ('- scope_in: {0}' -f $DocRelative),
        '- scope_out: none',
        '',
        '## Acceptance',
        '- source plan pair is frozen and bindable',
        '',
        '## Stop Conditions',
        '- none'
    ) | Set-Content -LiteralPath $docPath -Encoding UTF8

    $templatePlan = Read-Json -PathValue (Join-Path $TemplateRunDir 'plan.json')
    $templatePlan.plan_id = $PlanId
    $templatePlan.task_id = $TaskId
    $templatePlan.status = 'frozen'
    $templatePlan.source_plan_doc = $DocRelative.Replace('\', '/')
    $templatePlan.goal = $Goal
    $templatePlan.scope_in = @($DocRelative.Replace('\', '/'))
    $templatePlan.scope_out = @('none')
    $templatePlan.acceptance = @('source plan pair is frozen and bindable')
    $templatePlan.stop_conditions = @('none')
    Write-Json -PathValue $jsonPath -Data $templatePlan

    return [PSCustomObject]@{
        DocRelative = $DocRelative
        JsonRelative = $JsonRelative
        DocPath = $docPath
        JsonPath = $jsonPath
    }
}

function Invoke-Validate {
    param([object]$Scenario)

    $orchestrator = Join-Path $Scenario.RepoRoot 'skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1'
    $result = Invoke-PowerShellFile -FilePath $orchestrator -Arguments @('-Action', 'validate', '-RepoRoot', $Scenario.RepoRoot, '-TaskId', $Scenario.TaskId, '-Json')
    $json = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($result.Text)) {
            $json = ($result.Text | ConvertFrom-Json)
        }
    } catch {
        $json = $null
    }

    return [PSCustomObject]@{
        ExitCode = $result.ExitCode
        Text = $result.Text
        Json = $json
    }
}

function Invoke-ValidateWithoutTaskId {
    param([object]$Scenario)

    $orchestrator = Join-Path $Scenario.RepoRoot 'skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1'
    $result = Invoke-PowerShellFile -FilePath $orchestrator -Arguments @('-Action', 'validate', '-RepoRoot', $Scenario.RepoRoot, '-Json')
    $json = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($result.Text)) {
            $json = ($result.Text | ConvertFrom-Json)
        }
    } catch {
        $json = $null
    }

    return [PSCustomObject]@{
        ExitCode = $result.ExitCode
        Text = $result.Text
        Json = $json
    }
}

function Invoke-Hydrate {
    param(
        [object]$Scenario,
        [string]$TargetPath
    )

    $orchestrator = Join-Path $Scenario.RepoRoot 'skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1'
    $result = Invoke-PowerShellFile -FilePath $orchestrator -Arguments @('-Action', 'hydrate', '-RepoRoot', $Scenario.RepoRoot, '-Path', $TargetPath, '-Json')
    $json = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($result.Text)) {
            $json = ($result.Text | ConvertFrom-Json)
        }
    } catch {
        $json = $null
    }

    return [PSCustomObject]@{
        ExitCode = $result.ExitCode
        Text = $result.Text
        Json = $json
    }
}

function Invoke-CompileDispatchMessage {
    param(
        [object]$Scenario,
        [string]$TargetPath
    )

    $compiler = Join-Path $Scenario.RepoRoot 'skills/global-task-orchestrator/scripts/compile-dispatch-message.ps1'
    $result = Invoke-PowerShellFile -FilePath $compiler -Arguments @('-RepoRoot', $Scenario.RepoRoot, '-Path', $TargetPath, '-Json')
    $json = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($result.Text)) {
            $json = ($result.Text | ConvertFrom-Json)
        }
    } catch {
        $json = $null
    }

    return [PSCustomObject]@{
        ExitCode = $result.ExitCode
        Text = $result.Text
        Json = $json
    }
}

function Invoke-HydrateByTaskId {
    param(
        [object]$Scenario,
        [string]$TargetTaskId
    )

    $orchestrator = Join-Path $Scenario.RepoRoot 'skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1'
    $result = Invoke-PowerShellFile -FilePath $orchestrator -Arguments @('-Action', 'hydrate', '-RepoRoot', $Scenario.RepoRoot, '-TaskId', $TargetTaskId, '-Json')
    $json = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($result.Text)) {
            $json = ($result.Text | ConvertFrom-Json)
        }
    } catch {
        $json = $null
    }

    return [PSCustomObject]@{
        ExitCode = $result.ExitCode
        Text = $result.Text
        Json = $json
    }
}

function Invoke-Bootstrap {
    param(
        [string]$RepoRoot,
        [string]$TaskId,
        [string]$PlanId,
        [string]$SourcePlanDoc,
        [string]$SourcePlanJson
    )

    $orchestrator = Join-Path $RepoRoot 'skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1'
    $arguments = @('-Action', 'bootstrap', '-RepoRoot', $RepoRoot, '-TaskId', $TaskId, '-PlanId', $PlanId, '-SourcePlanDoc', $SourcePlanDoc, '-SourcePlanJson', $SourcePlanJson, '-Json')
    return (Invoke-PowerShellFile -FilePath $orchestrator -Arguments $arguments)
}

function Test-HappyPath {
    $scenario = New-Scenario -Name 'happy-path'
    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($result.ExitCode -eq 0) 'happy path should return exit code 0'
    Assert-True ($null -ne $result.Json) 'happy path should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'happy path should return ok=true'
    Assert-True ([int]$result.Json.errors.Count -eq 0) 'happy path should not have validation errors'
    Assert-True ([int]$result.Json.work_orders_checked -gt 0) 'happy path should validate at least one work_order'
}

function Test-MissingTaskIdFails {
    $scenario = New-Scenario -Name 'missing-taskid'
    $result = Invoke-ValidateWithoutTaskId -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing TaskId should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing TaskId should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '必须提供 -TaskId' -Message 'validate should hard-fail when TaskId is omitted'
}

function Test-RoleMapInvalidAgentType {
    $scenario = New-Scenario -Name 'role-map-invalid-agent-type'
    $roleMapPath = Get-RoleMapPath -Scenario $scenario
    $roleMap = Read-Json -PathValue $roleMapPath
    $roleMap.roles.reader.agent_type = 'invalid-agent-type'
    Write-Json -PathValue $roleMapPath -Data $roleMap

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'invalid role-map agent_type should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'invalid role-map agent_type should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'agent_type 非法' -Message 'validate output should mention invalid role-map agent_type'
}

function Test-RoleMapMissingRequiredRole {
    $scenario = New-Scenario -Name 'role-map-missing-required-role'
    $roleMapPath = Get-RoleMapPath -Scenario $scenario
    $roleMap = Read-Json -PathValue $roleMapPath
    $roleMap.roles.PSObject.Properties.Remove('test-verifier')
    Write-Json -PathValue $roleMapPath -Data $roleMap

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing required role should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing required role should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '缺少必需角色' -Message 'validate output should mention required role coverage'
}

function Test-RoleMapManifestConsistencyHappyPath {
    $scenario = New-Scenario -Name 'role-map-manifest-consistency-happy-path'
    $manifestPath = Get-ManifestPath -Scenario $scenario
    Assert-True (Test-Path -LiteralPath $manifestPath) 'manifest fixture should exist in scenario'

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($result.ExitCode -eq 0) 'consistent role-map and manifest should pass validate'
    Assert-True ($null -ne $result.Json) 'consistency happy path should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'consistent role-map and manifest should return ok=true'
}

function Test-DraftPlanValidate {
    $scenario = New-Scenario -Name 'draft-plan-validate'
    $planPath = Join-Path $scenario.RunDir 'plan.json'
    $plan = Read-Json -PathValue $planPath
    $plan.status = 'draft'
    Write-Json -PathValue $planPath -Data $plan

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'draft plan should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'draft plan should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'plan.json.status 必须为 frozen' -Message 'validate output should include the frozen gate'
}

function Test-FrozenRunPlanContentDriftFailsValidate {
    $scenario = New-Scenario -Name 'frozen-run-plan-content-drift-validate'
    $planPath = Join-Path $scenario.RunDir 'plan.json'
    $plan = Read-Json -PathValue $planPath
    $plan.status = 'frozen'
    $plan.goal = 'run plan goal drifted from source frozen plan'
    Write-Json -PathValue $planPath -Data $plan

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'frozen run plan drift should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'frozen run plan drift should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'run plan 与 source frozen plan 字段不一致' -Message 'validate should fail when run plan drifts from source frozen plan'
}

function Test-FrozenRunPlanSourcePlanJsonBypassFailsValidate {
    $scenario = New-Scenario -Name 'frozen-run-plan-source-plan-json-bypass-validate'
    $planPath = Join-Path $scenario.RunDir 'plan.json'
    $plan = Read-Json -PathValue $planPath
    $plan.status = 'frozen'
    $plan.goal = 'run plan drift plus source_plan_json bypass attempt'
    $plan | Add-Member -Force -NotePropertyName 'source_plan_json' -NotePropertyValue ("docs/ai/runs/{0}/plan.json" -f $scenario.TaskId)
    Write-Json -PathValue $planPath -Data $plan

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'source_plan_json bypass attempt should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'source_plan_json bypass attempt should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'source_plan_json 必须绑定到 source_plan_doc 对应的 frozen plan.json' -Message 'validate should reject run-declared source_plan_json bypasses'
}

function Test-DraftPlanBootstrap {
    $scenario = New-Scenario -Name 'draft-plan-bootstrap'
    $taskId = 'bootstrap-draft-plan-001'
    $planId = 'PLAN-BOOTSTRAP-DRAFT-001'
    $sourcePlanDocRelative = 'docs/plans/bootstrap-draft-source.md'
    $sourcePlanJsonRelative = 'docs/plans/bootstrap-draft-source.json'
    $sourcePlanDocPath = Join-Path $scenario.RepoRoot $sourcePlanDocRelative
    $sourcePlanJsonPath = Join-Path $scenario.RepoRoot $sourcePlanJsonRelative

    @(
        '# Frozen Plan',
        '',
        ('- task_id: {0}' -f $taskId),
        ('- plan_id: {0}' -f $planId),
        '- status: draft',
        '',
        '## Goal',
        '- Bootstrap draft gate test',
        '',
        '## Scope',
        '- scope_in: docs/plans/bootstrap-draft-source.md',
        '- scope_out: none',
        '',
        '## Acceptance',
        '- bootstrap must reject draft source plans',
        '',
        '## Stop Conditions',
        '- none'
    ) | Set-Content -LiteralPath $sourcePlanDocPath -Encoding UTF8

    $templatePlan = Read-Json -PathValue (Join-Path $scenario.RunDir 'plan.json')
    $templatePlan.plan_id = $planId
    $templatePlan.task_id = $taskId
    $templatePlan.status = 'draft'
    $templatePlan.source_plan_doc = $sourcePlanDocRelative.Replace('\', '/')
    $templatePlan.goal = 'Bootstrap draft gate test'
    $templatePlan.scope_in = @('docs/plans/bootstrap-draft-source.md')
    $templatePlan.scope_out = @('none')
    $templatePlan.acceptance = @('bootstrap must reject draft source plans')
    $templatePlan.stop_conditions = @('none')
    Write-Json -PathValue $sourcePlanJsonPath -Data $templatePlan

    $result = Invoke-Bootstrap -RepoRoot $scenario.RepoRoot -TaskId $taskId -PlanId $planId -SourcePlanDoc $sourcePlanDocRelative -SourcePlanJson $sourcePlanJsonRelative
    Assert-True ($result.ExitCode -ne 0) 'bootstrap should reject draft source plans'
    Assert-ContainsText -Text $result.Text -Expected 'status must be frozen' -Message 'bootstrap output should include the frozen gate'
}

function Test-ExistingRunDraftBootstrap {
    $scenario = New-Scenario -Name 'existing-run-draft-bootstrap'
    $taskId = 'bootstrap-existing-run-draft-001'
    $planId = 'PLAN-BOOTSTRAP-EXISTING-RUN-DRAFT-001'
    $sourcePlanDocRelative = 'docs/plans/bootstrap-existing-run-frozen-source.md'
    $sourcePlanJsonRelative = 'docs/plans/bootstrap-existing-run-frozen-source.json'
    $sourcePair = New-FrozenSourcePlanPair -RepoRoot $scenario.RepoRoot -TaskId $taskId -PlanId $planId -DocRelative $sourcePlanDocRelative -JsonRelative $sourcePlanJsonRelative -Goal 'Bootstrap existing run plan should also require frozen'

    $runDir = Join-Path $scenario.RepoRoot ("docs/ai/runs/{0}" -f $taskId)
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    $existingRunPlanPath = Join-Path $runDir 'plan.json'
    $existingRunPlan = Read-Json -PathValue $sourcePair.JsonPath
    $existingRunPlan.status = 'draft'
    Write-Json -PathValue $existingRunPlanPath -Data $existingRunPlan

    $result = Invoke-Bootstrap -RepoRoot $scenario.RepoRoot -TaskId $taskId -PlanId $planId -SourcePlanDoc $sourcePlanDocRelative -SourcePlanJson $sourcePlanJsonRelative
    Assert-True ($result.ExitCode -ne 0) 'bootstrap should reject existing run plans that are still draft'
    Assert-ContainsText -Text $result.Text -Expected 'existing run plan.json.status must be frozen' -Message 'bootstrap output should mention the existing run frozen gate'
}

function Test-ExistingRunFrozenContentDriftBootstrap {
    $scenario = New-Scenario -Name 'existing-run-frozen-content-drift-bootstrap'
    $taskId = 'bootstrap-existing-run-frozen-content-drift-001'
    $planId = 'PLAN-BOOTSTRAP-EXISTING-RUN-FROZEN-CONTENT-DRIFT-001'
    $sourcePlanDocRelative = 'docs/plans/bootstrap-existing-run-frozen-content-source.md'
    $sourcePlanJsonRelative = 'docs/plans/bootstrap-existing-run-frozen-content-source.json'
    $sourcePair = New-FrozenSourcePlanPair -RepoRoot $scenario.RepoRoot -TaskId $taskId -PlanId $planId -DocRelative $sourcePlanDocRelative -JsonRelative $sourcePlanJsonRelative -Goal 'Bootstrap existing run plan should match source frozen content'

    $runDir = Join-Path $scenario.RepoRoot ("docs/ai/runs/{0}" -f $taskId)
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    $existingRunPlanPath = Join-Path $runDir 'plan.json'
    $existingRunPlan = Read-Json -PathValue $sourcePair.JsonPath
    $existingRunPlan.status = 'frozen'
    $existingRunPlan.goal = 'drifted run goal'
    Write-Json -PathValue $existingRunPlanPath -Data $existingRunPlan

    $result = Invoke-Bootstrap -RepoRoot $scenario.RepoRoot -TaskId $taskId -PlanId $planId -SourcePlanDoc $sourcePlanDocRelative -SourcePlanJson $sourcePlanJsonRelative
    Assert-True ($result.ExitCode -ne 0) 'bootstrap should reject existing frozen run plans that drift from source frozen content'
    Assert-ContainsText -Text $result.Text -Expected 'does not match source frozen plan' -Message 'bootstrap output should mention source frozen content mismatch'
}

function Test-ExistingRunSourcePlanJsonBypassBootstrap {
    $scenario = New-Scenario -Name 'existing-run-source-plan-json-bypass-bootstrap'
    $taskId = 'bootstrap-existing-run-source-plan-json-bypass-001'
    $planId = 'PLAN-BOOTSTRAP-EXISTING-RUN-SOURCE-PLAN-JSON-BYPASS-001'
    $sourcePlanDocRelative = 'docs/plans/bootstrap-existing-run-source-plan-json-bypass-source.md'
    $sourcePlanJsonRelative = 'docs/plans/bootstrap-existing-run-source-plan-json-bypass-source.json'
    $sourcePair = New-FrozenSourcePlanPair -RepoRoot $scenario.RepoRoot -TaskId $taskId -PlanId $planId -DocRelative $sourcePlanDocRelative -JsonRelative $sourcePlanJsonRelative -Goal 'Bootstrap existing run plan should reject source_plan_json bypass'

    $runDir = Join-Path $scenario.RepoRoot ("docs/ai/runs/{0}" -f $taskId)
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    $existingRunPlanPath = Join-Path $runDir 'plan.json'
    $existingRunPlan = Read-Json -PathValue $sourcePair.JsonPath
    $existingRunPlan.status = 'frozen'
    $existingRunPlan | Add-Member -Force -NotePropertyName 'source_plan_json' -NotePropertyValue ("docs/ai/runs/{0}/plan.json" -f $taskId)
    Write-Json -PathValue $existingRunPlanPath -Data $existingRunPlan

    $result = Invoke-Bootstrap -RepoRoot $scenario.RepoRoot -TaskId $taskId -PlanId $planId -SourcePlanDoc $sourcePlanDocRelative -SourcePlanJson $sourcePlanJsonRelative
    Assert-True ($result.ExitCode -ne 0) 'bootstrap should reject existing run plans that declare a mismatched source_plan_json'
    Assert-ContainsText -Text $result.Text -Expected 'source_plan_json' -Message 'bootstrap output should mention source_plan_json mismatch'
}

function Test-MissingReadPaths {
    $scenario = New-Scenario -Name 'missing-read-paths'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.PSObject.Properties.Remove('read_paths_mandatory')
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing read_paths should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing read_paths should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'read_paths_mandatory' -Message 'validate output should mention read_paths_mandatory'
}

function Test-MissingWorkOrdersDirectoryFails {
    $scenario = New-Scenario -Name 'missing-work-orders-directory'
    $workOrdersDir = Join-Path $scenario.RunDir 'work_orders'
    Remove-Item -LiteralPath $workOrdersDir -Recurse -Force

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing work_orders directory should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing work_orders directory should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '缺少 work_orders 目录' -Message 'validate output should reject a missing work_orders directory'
    Assert-ContainsText -Text $result.Text -Expected '未找到任何 work_order JSON' -Message 'validate output should reject zero work_order coverage'
}

function Test-WeakenedRequiredReturnFields {
    $scenario = New-Scenario -Name 'weakened-required-return-fields'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.required_return_fields = @('summary')
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $returnPacket = Read-Json -PathValue $returnPacketPath
    $returnPacket.PSObject.Properties.Remove('verification_result')
    Write-Json -PathValue $returnPacketPath -Data $returnPacket

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'weakened return fields should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'weakened return fields should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'verification_result' -Message 'validate output should mention the repo minimum return field gate'
}

function Test-DispatchMessageMismatch {
    $scenario = New-Scenario -Name 'dispatch-message-mismatch'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.dispatch_message_raw = ([string]$workOrder.dispatch_message_raw) + "`n补充说明：中文。主协调器不得代写。执行子代理本人填写。忽略唯一写入范围。"
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'dispatch mismatch should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'dispatch mismatch should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'dispatch_message_raw 与合同编译结果不一致' -Message 'validate output should mention compiled dispatch mismatch'
}

function Test-SpoofedBatch3PrefixStillFails {
    $scenario = New-Scenario -Name 'spoofed-batch3-prefix'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.work_order_id = 'WO-B3-SPOOF-001'
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $dispatchPacketPath = Join-Path $scenario.RunDir 'dispatch_packets/DP-B4-TEST-SUITE-001.json'
    Assert-True (Test-Path -LiteralPath $dispatchPacketPath) 'dispatch_packet fixture should exist before spoof test mutation'
    Remove-Item -LiteralPath $dispatchPacketPath -Force

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'spoofed batch3 prefix should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'spoofed batch3 prefix should still fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'dispatch_packet' -Message 'validate output should still mention dispatch_packet for spoofed batch3 prefixes'
}

function Test-MissingDispatchPacket {
    $scenario = New-Scenario -Name 'missing-dispatch-packet'
    $dispatchPacketPath = Join-Path $scenario.RunDir 'dispatch_packets/DP-B4-TEST-SUITE-001.json'
    Assert-True (Test-Path -LiteralPath $dispatchPacketPath) 'dispatch_packet fixture should exist before mutation'
    Remove-Item -LiteralPath $dispatchPacketPath -Force

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing dispatch_packet should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing dispatch_packet should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'dispatch_packet' -Message 'validate output should mention dispatch_packet'
}

function Test-MissingReturnPacketHardFail {
    $scenario = New-Scenario -Name 'missing-return-packet'
    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    Assert-True (Test-Path -LiteralPath $returnPacketPath) 'return_packet fixture should exist before mutation'
    Remove-Item -LiteralPath $returnPacketPath -Force

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing return_packet should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing return_packet should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '缺少必需 return_packet' -Message 'validate output should treat missing return_packet as error'
}

function Test-ReturnPacketPayloadIdentityMismatchFails {
    $scenario = New-Scenario -Name 'return-packet-payload-identity-mismatch'
    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $otherReturnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-REVIEW-ACCEPT-001'
    Assert-True (Test-Path -LiteralPath $returnPacketPath) 'target return_packet fixture should exist before mutation'
    Assert-True (Test-Path -LiteralPath $otherReturnPacketPath) 'other return_packet fixture should exist before mutation'

    $otherReturnPacket = Read-Json -PathValue $otherReturnPacketPath
    Write-Json -PathValue $returnPacketPath -Data $otherReturnPacket

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'copied return_packet payload should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'copied return_packet payload should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'return_packet.work_order_id 与 work_order 不一致' -Message 'validate output should reject a copied return_packet payload with the wrong work_order binding'
    Assert-ContainsText -Text $result.Text -Expected 'return_packet.return_packet_id 与 work_order 不一致' -Message 'validate output should reject a copied return_packet payload with the wrong return_packet_id'
}

function Test-HydrateRewritesStaleDispatchMessage {
    $scenario = New-Scenario -Name 'hydrate-rewrites-stale-dispatch-message'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.dispatch_message_raw = '过期 dispatch message'
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $workOrderPath
    Assert-True ($hydrate.ExitCode -eq 0) 'hydrate should self-heal stale dispatch_message_raw'
    Assert-True ($null -ne $hydrate.Json) 'hydrate rewrite should emit parseable JSON'

    $updatedWorkOrder = Read-Json -PathValue $workOrderPath
    Assert-True ($updatedWorkOrder.dispatch_message_raw -ne '过期 dispatch message') 'hydrate should rewrite stale dispatch_message_raw'
    Assert-True ([string]$updatedWorkOrder.expected_written_role -eq 'control-plane-test-author') 'hydrate should backfill expected_written_role from the work_order contract'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$updatedWorkOrder.expected_written_by)) 'hydrate should not infer expected_written_by from return_packet content'
    Assert-True ([int]@($updatedWorkOrder.expected_written_by_patterns).Count -gt 0) 'hydrate should backfill machine-checkable expected_written_by_patterns when exact writer is unknown'
    Assert-True ([bool]$updatedWorkOrder.dispatch_packet_required) 'hydrate should persist explicit dispatch_packet_required for heuristically complex tasks'
    Assert-ContainsText -Text ([string]$updatedWorkOrder.dispatch_message_raw) -Expected '`written_role` 必须为 `control-plane-test-author`。' -Message 'hydrated dispatch_message_raw should include the exact written_role contract'
    Assert-ContainsText -Text ([string]$updatedWorkOrder.dispatch_message_raw) -Expected 'expected_written_by_patterns' -Message 'hydrated dispatch_message_raw should surface the machine-checkable written_by pattern contract'
}

function Test-HydrateCompileFailureNonZero {
    $scenario = New-Scenario -Name 'hydrate-compile-failure-nonzero'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.PSObject.Properties.Remove('read_paths_mandatory')
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $workOrderPath
    Assert-True ($hydrate.ExitCode -ne 0) 'hydrate compile failure should exit non-zero'
    Assert-True ($null -ne $hydrate.Json) 'hydrate compile failure should emit parseable JSON'
    Assert-True ([int]$hydrate.Json.compile_failures.Count -gt 0) 'hydrate compile failure payload should include compile_failures'
    Assert-ContainsText -Text $hydrate.Text -Expected 'read_paths_mandatory' -Message 'hydrate compile failure should mention the missing compile prerequisite'
}

function Test-HydrateInvalidJsonNonZero {
    $scenario = New-Scenario -Name 'hydrate-invalid-json-nonzero'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    Set-Content -LiteralPath $workOrderPath -Value '{ invalid-json' -Encoding UTF8

    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $workOrderPath
    Assert-True ($hydrate.ExitCode -ne 0) 'hydrate should exit non-zero for unparsable work_order JSON'
    Assert-True ($null -ne $hydrate.Json) 'hydrate invalid JSON should still emit parseable JSON payload'
    Assert-ContainsText -Text $hydrate.Text -Expected '无法解析 work_order' -Message 'hydrate invalid JSON should report the parse failure'
}

function Test-HydrateMissingPathNonZero {
    $scenario = New-Scenario -Name 'hydrate-missing-path-nonzero'
    $missingPath = Join-Path $scenario.RunDir 'work_orders/does-not-exist.json'

    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $missingPath
    Assert-True ($hydrate.ExitCode -ne 0) 'hydrate should exit non-zero when the target path does not exist'
    Assert-True ($null -ne $hydrate.Json) 'hydrate missing path should emit parseable JSON payload'
    Assert-ContainsText -Text $hydrate.Text -Expected 'hydrate 目标路径不存在' -Message 'hydrate missing path should report target resolution failure'
}

function Test-HydrateMissingTaskWorkOrdersNonZero {
    $scenario = New-Scenario -Name 'hydrate-missing-task-workorders'
    $missingTaskId = 'hydrate-missing-task-workorders-001'
    $runDir = Join-Path $scenario.RepoRoot ("docs/ai/runs/{0}" -f $missingTaskId)
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null

    $hydrate = Invoke-HydrateByTaskId -Scenario $scenario -TargetTaskId $missingTaskId
    Assert-True ($hydrate.ExitCode -ne 0) 'hydrate should exit non-zero when the target task run has no work_orders directory'
    Assert-True ($null -ne $hydrate.Json) 'hydrate missing task work_orders should emit parseable JSON payload'
    Assert-ContainsText -Text $hydrate.Text -Expected '缺少 work_orders 目录' -Message 'hydrate missing task work_orders should report the missing directory'
}

function Test-CompileDispatchMessageEmptyDirectoryNonZero {
    $scenario = New-Scenario -Name 'compile-dispatch-empty-directory'
    $emptyDir = Join-Path $scenario.RepoRoot 'empty-work-orders'
    New-Item -ItemType Directory -Path $emptyDir -Force | Out-Null

    $result = Invoke-CompileDispatchMessage -Scenario $scenario -TargetPath $emptyDir
    Assert-True ($result.ExitCode -ne 0) 'compile-dispatch-message should exit non-zero for an empty target directory'
    Assert-True ($null -ne $result.Json) 'compile-dispatch-message empty directory should emit parseable JSON payload'
    Assert-ContainsText -Text $result.Text -Expected '未找到任何 work_order JSON' -Message 'compile-dispatch-message should reject empty target collections'
}

function Test-HydrateDispatchPacketPathOutsideRunNonZero {
    $scenario = New-Scenario -Name 'hydrate-dispatch-packet-path-outside-run'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.dispatch_packet_path = 'docs/ai/runs/other-task/dispatch_packets/DP-B4-TEST-SUITE-001.json'
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $workOrderPath
    Assert-True ($hydrate.ExitCode -ne 0) 'hydrate should exit non-zero for dispatch_packet_path outside the current run'
    Assert-True ($null -ne $hydrate.Json) 'hydrate boundary failure should emit parseable JSON payload'
    Assert-ContainsText -Text $hydrate.Text -Expected '不在当前 task run 下' -Message 'hydrate boundary failure should mention the task-run violation'
}

function Test-HydrateMissingDispatchPacketFieldNonZero {
    $scenario = New-Scenario -Name 'hydrate-missing-dispatch-packet-field'
    $dispatchPacketPath = Join-Path $scenario.RunDir 'dispatch_packets/DP-B4-TEST-SUITE-001.json'
    $dispatchPacket = Read-Json -PathValue $dispatchPacketPath
    $dispatchPacket.PSObject.Properties.Remove('read_before_write')
    Write-Json -PathValue $dispatchPacketPath -Data $dispatchPacket

    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $workOrderPath
    Assert-True ($hydrate.ExitCode -ne 0) 'hydrate should exit non-zero when required dispatch_packet fields are missing'
    Assert-True ($null -ne $hydrate.Json) 'hydrate missing dispatch_packet field should emit parseable JSON payload'
    Assert-ContainsText -Text $hydrate.Text -Expected 'dispatch_packet.read_before_write' -Message 'hydrate should mention the missing dispatch_packet contract field'
}

function Test-ReturnPacketAuthorshipMismatch {
    $scenario = New-Scenario -Name 'return-packet-authorship-mismatch'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    Set-ObjectProperty -Object $workOrder -Name 'expected_written_role' -Value 'control-plane-test-author'
    Set-ObjectProperty -Object $workOrder -Name 'expected_written_by' -Value 'batch4-control-plane-test-subagent'
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $workOrderPath
    Assert-True ($hydrate.ExitCode -eq 0) 'hydrate should succeed before authorship mismatch validation'

    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $returnPacket = Read-Json -PathValue $returnPacketPath
    $returnPacket.written_role = 'control-plane-test-author'
    $returnPacket.written_by = 'different-subagent'
    Write-Json -PathValue $returnPacketPath -Data $returnPacket

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'authorship mismatch should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'authorship mismatch should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '期望作者身份不一致' -Message 'validate output should mention the explicit expected_written_by mismatch'
}

function Test-ReturnPacketPatternContractMismatch {
    $scenario = New-Scenario -Name 'return-packet-pattern-contract-mismatch'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $hydrate = Invoke-Hydrate -Scenario $scenario -TargetPath $workOrderPath
    Assert-True ($hydrate.ExitCode -eq 0) 'hydrate should succeed before pattern-contract validation'

    $hydratedWorkOrder = Read-Json -PathValue $workOrderPath
    Assert-True ([int]@($hydratedWorkOrder.expected_written_by_patterns).Count -gt 0) 'hydrate should backfill expected_written_by_patterns before validation'

    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $returnPacket = Read-Json -PathValue $returnPacketPath
    $returnPacket.written_role = 'control-plane-test-author'
    $returnPacket.written_by = 'random-worker'
    Write-Json -PathValue $returnPacketPath -Data $returnPacket

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'pattern contract mismatch should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'pattern contract mismatch should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'expected_written_by_patterns 作者身份模式合同' -Message 'validate should reject written_by values that do not match the explicit written_by pattern contract'
}

function Test-ReturnPacketPatternContractSpoofedAliasFails {
    $scenario = New-Scenario -Name 'return-packet-pattern-contract-spoofed-alias'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    Assert-True ([string]::IsNullOrWhiteSpace([string]$workOrder.expected_written_by)) 'spoofed alias test requires missing expected_written_by'
    if ([int]@($workOrder.expected_written_by_patterns).Count -eq 0) {
        Set-ObjectProperty -Object $workOrder -Name 'expected_written_by_patterns' -Value @('^batch4-control-plane-test-subagent$')
        Write-Json -PathValue $workOrderPath -Data $workOrder
    }

    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $returnPacket = Read-Json -PathValue $returnPacketPath
    $returnPacket.written_role = 'control-plane-test-author'
    $returnPacket.written_by = 'batch4-test-suite-subagent'
    Write-Json -PathValue $returnPacketPath -Data $returnPacket

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'spoofed alias pattern mismatch should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'spoofed alias pattern mismatch should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'expected_written_by_patterns 作者身份模式合同' -Message 'validate should reject near-spoof written_by aliases when expected_written_by is missing'
}

function Test-InvalidWrittenByPatternFails {
    $scenario = New-Scenario -Name 'invalid-written-by-pattern'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    Set-ObjectProperty -Object $workOrder -Name 'expected_written_by_patterns' -Value @('(')
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'invalid expected_written_by_patterns should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'invalid expected_written_by_patterns should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '不是合法正则' -Message 'validate should reject malformed written_by pattern contracts'
}

function Test-WeakWrittenByPatternFails {
    $scenario = New-Scenario -Name 'weak-written-by-pattern'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    Set-ObjectProperty -Object $workOrder -Name 'expected_written_by_patterns' -Value @('^.*$')
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'weak expected_written_by_patterns should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'weak expected_written_by_patterns should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '不能包含通配、分组或量词' -Message 'validate should reject wildcard written_by pattern contracts that weaken authorship binding'
}

function Test-EscapedRegexWrittenByPatternFails {
    $scenario = New-Scenario -Name 'escaped-regex-written-by-pattern'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    Set-ObjectProperty -Object $workOrder -Name 'expected_written_by_patterns' -Value @('^\d$')
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'escaped regex expected_written_by_patterns should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'escaped regex expected_written_by_patterns should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '不能包含通配、分组或量词' -Message 'validate should reject regex escape semantics inside expected_written_by_patterns'
}

function Test-ReturnPacketCoordinatorIdentityRejected {
    $scenario = New-Scenario -Name 'return-packet-coordinator-identity'
    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $returnPacket = Read-Json -PathValue $returnPacketPath
    $returnPacket.written_role = 'control-plane-test-author'
    $returnPacket.written_by = 'main-coordinator'
    Write-Json -PathValue $returnPacketPath -Data $returnPacket

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'coordinator identity should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'coordinator identity should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '协调器身份' -Message 'validate output should reject coordinator authorship'
}

function Test-ReturnPacketPathHijackFails {
    $scenario = New-Scenario -Name 'return-packet-path-hijack'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.return_packet_path = 'docs/ai/runs/contract-first-dispatch-batch3-4-20260403-153206-gtm2/return_packets/RP-B4-REVIEW-ACCEPT-001.json'
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'return_packet path hijack should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'return_packet path hijack should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'return_packet_path 文件名与 work_order 不一致' -Message 'validate output should reject return_packet_path hijacking'
}

function Test-DispatchPacketPathOutsideRunFails {
    $scenario = New-Scenario -Name 'dispatch-packet-path-outside-run'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.dispatch_packet_path = 'docs/ai/runs/other-task/dispatch_packets/DP-B4-TEST-SUITE-001.json'
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'dispatch_packet_path outside run should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'dispatch_packet_path outside run should fail validate'
    Assert-ContainsText -Text $result.Text -Expected '不在当前 task run 下' -Message 'validate output should mention the task-run boundary violation'
}

function Test-DispatchPacketPathReparsePointFails {
    $scenario = New-Scenario -Name 'dispatch-packet-path-reparse-point'
    $outsideDispatchRoot = Join-Path $scenario.RepoRoot 'outside-dispatch-packets'
    New-Item -ItemType Directory -Path $outsideDispatchRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $scenario.RunDir 'dispatch_packets/DP-B4-TEST-SUITE-001.json') -Destination (Join-Path $outsideDispatchRoot 'DP-B4-TEST-SUITE-001.json') -Force

    $junctionPath = Join-Path $scenario.RunDir 'dispatch_packets/junction'
    New-Item -ItemType Junction -Path $junctionPath -Target $outsideDispatchRoot | Out-Null

    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.dispatch_packet_path = ("docs/ai/runs/{0}/dispatch_packets/junction/DP-B4-TEST-SUITE-001.json" -f $scenario.TaskId)
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'dispatch_packet_path via reparse point should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'dispatch_packet_path via reparse point should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'reparse point' -Message 'validate should reject artifact paths that traverse a reparse point'
}

function Test-DispatchPacketTaskIdSpoofStillFails {
    $scenario = New-Scenario -Name 'dispatch-packet-taskid-spoof'
    $spoofTaskId = 'spoofed-task-id'
    $spoofDispatchDir = Join-Path $scenario.RepoRoot ("docs/ai/runs/{0}/dispatch_packets" -f $spoofTaskId)
    New-Item -ItemType Directory -Path $spoofDispatchDir -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $scenario.RunDir 'dispatch_packets/DP-B4-TEST-SUITE-001.json') -Destination (Join-Path $spoofDispatchDir 'DP-B4-TEST-SUITE-001.json') -Force

    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.task_id = $spoofTaskId
    $workOrder.dispatch_packet_path = ("docs/ai/runs/{0}/dispatch_packets/DP-B4-TEST-SUITE-001.json" -f $spoofTaskId)
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'spoofed task_id should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'spoofed task_id should not bypass dispatch_packet_path run boundary'
    Assert-ContainsText -Text $result.Text -Expected '不在当前 task run 下' -Message 'validate output should reject task_id + path spoofing'
}

function Test-ExplicitDispatchPacketRequiredOverridesHeuristic {
    $scenario = New-Scenario -Name 'explicit-dispatch-packet-required'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-REVIEW-ACCEPT-001'
    $workOrder = Read-Json -PathValue $workOrderPath
    Set-ObjectProperty -Object $workOrder -Name 'dispatch_packet_required' -Value $true
    Write-Json -PathValue $workOrderPath -Data $workOrder

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'explicit dispatch_packet_required should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'explicit dispatch_packet_required should force validate failure when packet is missing'
    Assert-ContainsText -Text $result.Text -Expected '复杂任务缺少 dispatch_packet_path' -Message 'validate output should honor the explicit dispatch_packet_required gate'
}

function Test-ReturnPacketRequiredFalseStillFails {
    $scenario = New-Scenario -Name 'return-packet-required-false'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'

    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.return_packet_required = $false
    Write-Json -PathValue $workOrderPath -Data $workOrder
    Remove-Item -LiteralPath $returnPacketPath -Force

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'return_packet_required=false bypass attempt should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'return_packet_required=false should not bypass validate'
    Assert-ContainsText -Text $result.Text -Expected 'return_packet_required 必须为 true' -Message 'validate should reject return_packet_required=false'
    Assert-ContainsText -Text $result.Text -Expected '缺少必需 return_packet' -Message 'validate should still hard-fail missing return_packet'
}

function Test-MissingReturnPacketStillFailsWithoutWorkOrderId {
    $scenario = New-Scenario -Name 'missing-return-packet-without-workorder-id'
    $workOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $returnPacketPath = Get-ReturnPacketPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'

    $workOrder = Read-Json -PathValue $workOrderPath
    $workOrder.PSObject.Properties.Remove('work_order_id')
    Write-Json -PathValue $workOrderPath -Data $workOrder
    Remove-Item -LiteralPath $returnPacketPath -Force

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'missing work_order_id plus missing return_packet should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'missing work_order_id plus missing return_packet should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'work_order 缺少字段 work_order_id' -Message 'validate output should mention missing work_order_id'
    Assert-ContainsText -Text $result.Text -Expected '缺少必需 return_packet' -Message 'validate should still hard-fail missing return_packet without relying on work_order_id'
}

function Test-DuplicateWorkOrderIdFails {
    $scenario = New-Scenario -Name 'duplicate-work-order-id'
    $sourceWorkOrderPath = Get-WorkOrderPath -Scenario $scenario -WorkOrderId 'WO-B4-TEST-SUITE-001'
    $duplicateWorkOrderPath = Join-Path $scenario.RunDir 'work_orders/WO-B4-TEST-SUITE-001-DUPLICATE.json'
    Copy-Item -LiteralPath $sourceWorkOrderPath -Destination $duplicateWorkOrderPath -Force

    $result = Invoke-Validate -Scenario $scenario
    Assert-True ($null -ne $result.Json) 'duplicate work_order_id should emit parseable JSON'
    Assert-True (-not [bool]$result.Json.ok) 'duplicate work_order_id should fail validate'
    Assert-ContainsText -Text $result.Text -Expected 'work_order_id 重复' -Message 'validate output should mention duplicate work_order_id'
}

Run-TestCase -Name 'Happy path: current run passes validate gate' -Body { Test-HappyPath }
Run-TestCase -Name 'Bad path: missing TaskId should fail validate' -Body { Test-MissingTaskIdFails }
Run-TestCase -Name 'Happy path: role-map and manifest consistency should pass validate' -Body { Test-RoleMapManifestConsistencyHappyPath }
Run-TestCase -Name 'Bad path: draft plan should fail validate' -Body { Test-DraftPlanValidate }
Run-TestCase -Name 'Bad path: frozen run plan content drift from source frozen plan should fail validate' -Body { Test-FrozenRunPlanContentDriftFailsValidate }
Run-TestCase -Name 'Bad path: run-declared source_plan_json should not bypass frozen plan drift validate' -Body { Test-FrozenRunPlanSourcePlanJsonBypassFailsValidate }
Run-TestCase -Name 'Bad path: bootstrap should reject draft source plan' -Body { Test-DraftPlanBootstrap }
Run-TestCase -Name 'Bad path: bootstrap should reject existing run draft plan' -Body { Test-ExistingRunDraftBootstrap }
Run-TestCase -Name 'Bad path: bootstrap should reject existing run frozen content drift' -Body { Test-ExistingRunFrozenContentDriftBootstrap }
Run-TestCase -Name 'Bad path: bootstrap should reject existing run source_plan_json bypass' -Body { Test-ExistingRunSourcePlanJsonBypassBootstrap }
Run-TestCase -Name 'Bad path: role-map invalid agent_type should fail validate' -Body { Test-RoleMapInvalidAgentType }
Run-TestCase -Name 'Bad path: role-map missing required role should fail validate' -Body { Test-RoleMapMissingRequiredRole }
Run-TestCase -Name 'Bad path: missing read_paths_mandatory should fail validate' -Body { Test-MissingReadPaths }
Run-TestCase -Name 'Bad path: missing work_orders directory should fail validate' -Body { Test-MissingWorkOrdersDirectoryFails }
Run-TestCase -Name 'Bad path: weakened required_return_fields should not bypass minimum return fields' -Body { Test-WeakenedRequiredReturnFields }
Run-TestCase -Name 'Bad path: dispatch_message_raw inconsistent with contract should fail validate' -Body { Test-DispatchMessageMismatch }
Run-TestCase -Name 'Bad path: spoofed WO-B3 prefix should still fail dispatch gates' -Body { Test-SpoofedBatch3PrefixStillFails }
Run-TestCase -Name 'Bad path: complex task missing dispatch_packet should fail validate' -Body { Test-MissingDispatchPacket }
Run-TestCase -Name 'Bad path: missing return_packet should fail validate' -Body { Test-MissingReturnPacketHardFail }
Run-TestCase -Name 'Bad path: copied return_packet payload should fail identity binding checks' -Body { Test-ReturnPacketPayloadIdentityMismatchFails }
Run-TestCase -Name 'Happy path: hydrate should rewrite stale dispatch_message_raw and backfill authorship fields' -Body { Test-HydrateRewritesStaleDispatchMessage }
Run-TestCase -Name 'Bad path: hydrate compile failure should exit non-zero' -Body { Test-HydrateCompileFailureNonZero }
Run-TestCase -Name 'Bad path: hydrate invalid JSON should exit non-zero' -Body { Test-HydrateInvalidJsonNonZero }
Run-TestCase -Name 'Bad path: hydrate missing path should exit non-zero' -Body { Test-HydrateMissingPathNonZero }
Run-TestCase -Name 'Bad path: hydrate missing task work_orders should exit non-zero' -Body { Test-HydrateMissingTaskWorkOrdersNonZero }
Run-TestCase -Name 'Bad path: compile-dispatch-message empty target directory should exit non-zero' -Body { Test-CompileDispatchMessageEmptyDirectoryNonZero }
Run-TestCase -Name 'Bad path: hydrate dispatch_packet_path outside current run should exit non-zero' -Body { Test-HydrateDispatchPacketPathOutsideRunNonZero }
Run-TestCase -Name 'Bad path: hydrate missing dispatch_packet contract field should exit non-zero' -Body { Test-HydrateMissingDispatchPacketFieldNonZero }
Run-TestCase -Name 'Bad path: return_packet authorship mismatch should fail validate' -Body { Test-ReturnPacketAuthorshipMismatch }
Run-TestCase -Name 'Bad path: return_packet written_by must match expected_written_by_patterns contract' -Body { Test-ReturnPacketPatternContractMismatch }
Run-TestCase -Name 'Bad path: return_packet spoofed alias should fail expected_written_by_patterns contract' -Body { Test-ReturnPacketPatternContractSpoofedAliasFails }
Run-TestCase -Name 'Bad path: malformed expected_written_by_patterns should fail validate' -Body { Test-InvalidWrittenByPatternFails }
Run-TestCase -Name 'Bad path: wildcard expected_written_by_patterns should fail validate' -Body { Test-WeakWrittenByPatternFails }
Run-TestCase -Name 'Bad path: regex escape expected_written_by_patterns should fail validate' -Body { Test-EscapedRegexWrittenByPatternFails }
Run-TestCase -Name 'Bad path: return_packet coordinator identity should be rejected' -Body { Test-ReturnPacketCoordinatorIdentityRejected }
Run-TestCase -Name 'Bad path: return_packet_path hijack should fail validate' -Body { Test-ReturnPacketPathHijackFails }
Run-TestCase -Name 'Bad path: dispatch_packet_path outside current run should fail validate' -Body { Test-DispatchPacketPathOutsideRunFails }
Run-TestCase -Name 'Bad path: dispatch_packet_path through reparse point should fail validate' -Body { Test-DispatchPacketPathReparsePointFails }
Run-TestCase -Name 'Bad path: spoofed task_id should not bypass dispatch_packet_path run boundary' -Body { Test-DispatchPacketTaskIdSpoofStillFails }
Run-TestCase -Name 'Bad path: explicit dispatch_packet_required should force dispatch_packet gate' -Body { Test-ExplicitDispatchPacketRequiredOverridesHeuristic }
Run-TestCase -Name 'Bad path: return_packet_required=false should not bypass missing return_packet hard fail' -Body { Test-ReturnPacketRequiredFalseStillFails }
Run-TestCase -Name 'Bad path: missing work_order_id should not bypass missing return_packet hard fail' -Body { Test-MissingReturnPacketStillFailsWithoutWorkOrderId }
Run-TestCase -Name 'Bad path: duplicate work_order_id should fail validate' -Body { Test-DuplicateWorkOrderIdFails }

Write-Host ("TOTAL PASS {0}" -f $script:PassCount)
if ($script:Failures.Count -gt 0) {
    Write-Host ("TOTAL FAIL {0}" -f $script:Failures.Count)
    foreach ($failure in $script:Failures) {
        Write-Host ("  {0}" -f $failure)
    }
    exit 1
}

Write-Host 'ALL TESTS PASSED'
exit 0
