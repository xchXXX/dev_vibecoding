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

function Assert-Match {
  param(
    [string]$Value,
    [string]$Pattern,
    [string]$Message
  )
  if ($Value -notmatch $Pattern) {
    throw $Message
  }
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$skillRoot = Join-Path $repoRoot 'skills\global-task-orchestrator'
$skillPath = Join-Path $skillRoot 'SKILL.md'
$governancePath = Join-Path $skillRoot 'references\governance-essentials.md'
$stateSchemaPath = Join-Path $skillRoot 'references\state-schema.md'
$usageModesPath = Join-Path $skillRoot 'references\usage-modes.md'
$openAiYamlPath = Join-Path $skillRoot 'agents\openai.yaml'
$scriptPath = Join-Path $skillRoot 'scripts\orchestrator_ctl.ps1'

Assert-True (Test-Path -LiteralPath $skillPath) 'SKILL.md must exist for global-task-orchestrator'
Assert-True (Test-Path -LiteralPath $governancePath) 'governance-essentials.md must exist for global-task-orchestrator'
Assert-True (Test-Path -LiteralPath $stateSchemaPath) 'state-schema.md must exist for global-task-orchestrator'
Assert-True (Test-Path -LiteralPath $usageModesPath) 'usage-modes.md must exist for global-task-orchestrator'
Assert-True (Test-Path -LiteralPath $openAiYamlPath) 'agents/openai.yaml must exist for global-task-orchestrator'
Assert-True (Test-Path -LiteralPath $scriptPath) 'orchestrator_ctl.ps1 must exist for global-task-orchestrator'

$skillContent = Get-Content -LiteralPath $skillPath -Raw -Encoding UTF8
$governanceContent = Get-Content -LiteralPath $governancePath -Raw -Encoding UTF8
$stateSchemaContent = Get-Content -LiteralPath $stateSchemaPath -Raw -Encoding UTF8
$openAiYaml = Get-Content -LiteralPath $openAiYamlPath -Raw -Encoding UTF8
$scriptContent = Get-Content -LiteralPath $scriptPath -Raw -Encoding UTF8

Assert-Match -Value $skillContent -Pattern '一个正式长任务只对应一个 `task_id`' -Message 'SKILL.md must define one formal long task per task_id'
Assert-Match -Value $skillContent -Pattern 'Plan Window' -Message 'SKILL.md must document Plan Window responsibilities'
Assert-Match -Value $skillContent -Pattern 'Execute Window' -Message 'SKILL.md must document Execute Window responsibilities'
Assert-Match -Value $skillContent -Pattern 'current_phase' -Message 'SKILL.md must document current_phase'
Assert-Match -Value $skillContent -Pattern 'planning / doc_sync / test_sync / code_impl / review / blocked' -Message 'SKILL.md must document the recommended current_phase values'
Assert-Match -Value $skillContent -Pattern 'verification_contract' -Message 'SKILL.md must document verification_contract'
Assert-Match -Value $skillContent -Pattern 'review_evidence' -Message 'SKILL.md must document review_evidence'
Assert-Match -Value $skillContent -Pattern 'build-execute-handoff' -Message 'SKILL.md must document build-execute-handoff'
Assert-Match -Value $skillContent -Pattern '不要重新 `init-task`' -Message 'SKILL.md must document the re-init prohibition in handoff guidance'

Assert-Match -Value $governanceContent -Pattern 'current_phase' -Message 'governance essentials must mention current_phase'
Assert-Match -Value $governanceContent -Pattern 'planning / doc_sync / test_sync / code_impl / review / blocked' -Message 'governance essentials must document the recommended phase values'
Assert-Match -Value $governanceContent -Pattern 'verification_contract' -Message 'governance essentials must mention verification_contract gates'
Assert-Match -Value $governanceContent -Pattern 'review_evidence' -Message 'governance essentials must mention review_evidence coverage'

Assert-Match -Value $stateSchemaContent -Pattern 'verification_contract' -Message 'state-schema reference must mention verification_contract'
Assert-Match -Value $stateSchemaContent -Pattern 'result\.review_evidence' -Message 'state-schema reference must mention result.review_evidence'

Assert-Match -Value $openAiYaml -Pattern 'display_name:\s*"Global Task Orchestrator"' -Message 'openai.yaml must expose the expected display name'
Assert-Match -Value $openAiYaml -Pattern 'short_description:\s*"基于 state\.json 的轻量任务协调 skill"' -Message 'openai.yaml must expose the expected short description'
Assert-Match -Value $openAiYaml -Pattern 'default_prompt:\s*".*one formal long task per task_id.*Plan and Execute windows.*state\.json\.current_phase.*only delegate reader subtasks.*never re-run init-task.*core documentation sync and test work.*implementation/review to be delegated.*verification_contract.*review_evidence.*"' -Message 'openai.yaml default_prompt must cover task identity, phase handling, Plan/Execute routing, re-init prohibition, docs/tests ordering, verification_contract, and review_evidence'

Assert-Match -Value $scriptContent -Pattern 'function Get-AllowedPhases \{' -Message 'orchestrator_ctl.ps1 must define the allowed current_phase values helper'
Assert-Match -Value $scriptContent -Pattern "@\('planning','doc_sync','test_sync','code_impl','review','blocked'\)" -Message 'orchestrator_ctl.ps1 must keep the expected current_phase values'
Assert-Match -Value $scriptContent -Pattern 'Validate-VerificationContract' -Message 'orchestrator_ctl.ps1 must validate verification_contract'
Assert-Match -Value $scriptContent -Pattern 'Validate-ReviewEvidenceCoverage' -Message 'orchestrator_ctl.ps1 must validate review evidence coverage'

Write-Host 'PASS: global-task-orchestrator skill metadata and documentation contract'
