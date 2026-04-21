param(
  [string]$RepoRoot = (Get-Location).Path,
  [Parameter(Mandatory = $true)]
  [string]$TaskId,
  [string]$PlanId = '',
  [string]$SourcePlanDoc = '',
  [string]$SourcePlanJson = '',
  [switch]$Json
)

function Resolve-RepoRelativePath {
  param(
    [string]$RepoRootPath,
    [string]$CandidatePath
  )

  if ([string]::IsNullOrWhiteSpace($CandidatePath)) {
    return $null
  }

  $repoFullPath = [System.IO.Path]::GetFullPath($RepoRootPath)
  $candidateFullPath = if ([System.IO.Path]::IsPathRooted($CandidatePath)) {
    [System.IO.Path]::GetFullPath($CandidatePath)
  } else {
    [System.IO.Path]::GetFullPath((Join-Path $RepoRootPath $CandidatePath))
  }

  $repoRootWithSeparator = if ($repoFullPath.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
    $repoFullPath
  } else {
    $repoFullPath + [System.IO.Path]::DirectorySeparatorChar
  }

  if (($candidateFullPath -ne $repoFullPath) -and (-not $candidateFullPath.StartsWith($repoRootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase))) {
    throw ("Path escapes repo root and cannot be bound: {0}" -f $CandidatePath)
  }

  $repoUri = New-Object System.Uri((($repoFullPath.TrimEnd('\')) + '\'))
  $candidateUri = New-Object System.Uri($candidateFullPath)
  $relativePath = [System.Uri]::UnescapeDataString($repoUri.MakeRelativeUri($candidateUri).ToString()).Replace('\', '/')

  return [ordered]@{
    FullPath = $candidateFullPath
    RelativePath = $relativePath
  }
}

function Test-UsableValue {
  param($Value)

  if ($null -eq $Value) {
    return $false
  }

  if ($Value -is [string]) {
    return -not [string]::IsNullOrWhiteSpace($Value)
  }

  return $true
}

function Assert-PlanField {
  param(
    $PlanObject,
    [string]$FieldName,
    [string]$PlanLabel = 'source plan.json'
  )

  $property = $PlanObject.PSObject.Properties[$FieldName]
  if (($null -eq $property) -or (-not (Test-UsableValue -Value $property.Value))) {
    throw ("Binding failed: {0} is missing field {1}" -f $PlanLabel, $FieldName)
  }
}

function Convert-PlanFieldToComparableText {
  param(
    $PlanObject,
    [string]$FieldName
  )

  $value = $PlanObject.$FieldName
  if ($null -eq $value) {
    return ''
  }

  if ($FieldName -eq 'source_plan_doc') {
    return ([string]$value).Trim().Replace('\', '/')
  }

  if ($value -is [string]) {
    return ([string]$value).Trim()
  }

  return ($value | ConvertTo-Json -Depth 50 -Compress)
}

function Assert-RunPlanMatchesSourceFrozenPlan {
  param(
    $RunPlanObject,
    $SourcePlanObject,
    [string]$RunPlanPath,
    [string]$SourcePlanPath
  )

  foreach ($field in @('plan_id','task_id','status','source_plan_doc','goal','scope_in','scope_out','acceptance','stop_conditions')) {
    Assert-PlanField -PlanObject $RunPlanObject -FieldName $field -PlanLabel 'existing run plan.json'
    Assert-PlanField -PlanObject $SourcePlanObject -FieldName $field -PlanLabel 'source plan.json'

    $runValue = Convert-PlanFieldToComparableText -PlanObject $RunPlanObject -FieldName $field
    $sourceValue = Convert-PlanFieldToComparableText -PlanObject $SourcePlanObject -FieldName $field
    if ($runValue -ne $sourceValue) {
      throw ("Binding failed: existing run plan.json field `{0}` does not match source frozen plan `{1}` (run: {2})." -f $field, $SourcePlanPath, $RunPlanPath)
    }
  }
}

$runDir = Join-Path $RepoRoot ("docs/ai/runs/{0}" -f $TaskId)
$sessionDir = Join-Path $RepoRoot (".ai/session/{0}" -f $TaskId)
$plansDir = Join-Path $RepoRoot 'docs/plans'
$created = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

foreach ($dir in @($runDir, (Join-Path $runDir 'work_orders'), (Join-Path $runDir 'dispatch_packets'), (Join-Path $runDir 'return_packets'), $sessionDir, $plansDir)) {
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $created.Add($dir) | Out-Null
  }
}

if (-not $PlanId) {
  $PlanId = 'PLAN-' + ($TaskId.ToUpper() -replace '[^A-Z0-9]+', '-')
}

$planPath = Join-Path $runDir 'plan.json'
$bindingMode = (-not [string]::IsNullOrWhiteSpace($SourcePlanDoc)) -or (-not [string]::IsNullOrWhiteSpace($SourcePlanJson))
$sourcePlanDocRelative = ''
$sourcePlanDocPath = ''
$sourcePlanJsonRelative = ''
$sourcePlanJsonPath = ''
$boundPlanObject = $null

if ($bindingMode) {
  if ([string]::IsNullOrWhiteSpace($SourcePlanDoc) -or [string]::IsNullOrWhiteSpace($SourcePlanJson)) {
    throw 'Binding an existing frozen plan requires both -SourcePlanDoc and -SourcePlanJson.'
  }

  $sourcePlanDocInfo = Resolve-RepoRelativePath -RepoRootPath $RepoRoot -CandidatePath $SourcePlanDoc
  $sourcePlanJsonInfo = Resolve-RepoRelativePath -RepoRootPath $RepoRoot -CandidatePath $SourcePlanJson
  $sourcePlanDocRelative = $sourcePlanDocInfo.RelativePath
  $sourcePlanDocPath = $sourcePlanDocInfo.FullPath
  $sourcePlanJsonRelative = $sourcePlanJsonInfo.RelativePath
  $sourcePlanJsonPath = $sourcePlanJsonInfo.FullPath

  if (-not (Test-Path -LiteralPath $sourcePlanDocPath)) {
    throw ("Binding failed: source plan.md does not exist: {0}" -f $sourcePlanDocRelative)
  }

  if (-not (Test-Path -LiteralPath $sourcePlanJsonPath)) {
    throw ("Binding failed: source plan.json does not exist: {0}" -f $sourcePlanJsonRelative)
  }

  try {
    $boundPlanObject = Get-Content -LiteralPath $sourcePlanJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    throw ("Binding failed: source plan.json cannot be parsed: {0}" -f $sourcePlanJsonRelative)
  }

  foreach ($field in @('plan_id','task_id','status','source_plan_doc','goal','scope_in','scope_out','acceptance','stop_conditions')) {
    Assert-PlanField -PlanObject $boundPlanObject -FieldName $field
  }

  if ($boundPlanObject.status -ne 'frozen') {
    throw ("Binding failed: source plan.json.status must be frozen: {0}" -f $boundPlanObject.status)
  }

  if ($boundPlanObject.task_id -ne $TaskId) {
    throw ("Binding failed: source plan.json.task_id={0} does not match TaskId={1}." -f $boundPlanObject.task_id, $TaskId)
  }

  if ($boundPlanObject.source_plan_doc.Replace('\', '/') -ne $sourcePlanDocRelative) {
    throw ("Binding failed: source plan.json.source_plan_doc={0} does not match -SourcePlanDoc={1}." -f $boundPlanObject.source_plan_doc, $sourcePlanDocRelative)
  }

  if ([string]::IsNullOrWhiteSpace($PlanId)) {
    $PlanId = $boundPlanObject.plan_id
  } elseif ($boundPlanObject.plan_id -ne $PlanId) {
    throw ("Binding failed: source plan.json.plan_id={0} does not match -PlanId={1}." -f $boundPlanObject.plan_id, $PlanId)
  }
} else {
  $sourcePlanDocRelative = ("docs/plans/{0}.md" -f $TaskId)
  $sourcePlanDocPath = Join-Path $RepoRoot $sourcePlanDocRelative
  if (-not (Test-Path -LiteralPath $sourcePlanDocPath)) {
    @(
      "# Frozen Plan",
      "",
      ("- task_id: {0}" -f $TaskId),
      ("- plan_id: {0}" -f $PlanId),
      "- status: draft",
      "",
      "## Goal",
      "- To be filled by the main coordinator",
      "",
      "## Scope",
      "- scope_in:",
      "- scope_out:",
      "",
      "## Acceptance",
      "- To be filled by the main coordinator",
      "",
      "## Stop Conditions",
      "- To be filled by the main coordinator"
    ) | Set-Content -LiteralPath $sourcePlanDocPath -Encoding UTF8
    $created.Add($sourcePlanDocPath) | Out-Null
  }
}

if (-not (Test-Path -LiteralPath $planPath)) {
  if ($bindingMode) {
    $boundPlanObject | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $planPath -Encoding UTF8
  } else {
    $plan = [ordered]@{
      plan_id = $PlanId
      task_id = $TaskId
      version = 3
      mode = 'proposal-confirm-then-execute'
      status = 'draft'
      plan_owner = 'main_window'
      source_plan_doc = $sourcePlanDocRelative.Replace('\', '/')
      plan_md_is_semantic_source = $true
      plan_json_is_structured_projection = $true
      goal = 'To be filled by the main coordinator'
      why = 'To be filled by the main coordinator'
      scope_in = @()
      scope_out = @()
      acceptance = @()
      stop_conditions = @()
      risks = @()
      phase_overview = @()
    }
    $plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $planPath -Encoding UTF8
  }
  $created.Add($planPath) | Out-Null
} elseif ($bindingMode) {
  try {
    $existingPlanObject = Get-Content -LiteralPath $planPath -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    throw ("Binding failed: existing run plan.json cannot be parsed: {0}" -f $planPath)
  }

  foreach ($field in @('plan_id','task_id','status','source_plan_doc')) {
    Assert-PlanField -PlanObject $existingPlanObject -FieldName $field -PlanLabel 'existing run plan.json'
  }

  if (($existingPlanObject.task_id -ne $TaskId) -or ($existingPlanObject.plan_id -ne $PlanId) -or ($existingPlanObject.source_plan_doc.Replace('\', '/') -ne $sourcePlanDocRelative)) {
    throw ("Binding failed: existing run plan.json does not match the requested frozen plan pair: {0}" -f $planPath)
  }

  if ($existingPlanObject.status -ne 'frozen') {
    throw ("Binding failed: existing run plan.json.status must be frozen: {0}" -f $existingPlanObject.status)
  }

  if ((-not [string]::IsNullOrWhiteSpace((Convert-PlanFieldToComparableText -PlanObject $existingPlanObject -FieldName 'source_plan_json'))) -and ((Convert-PlanFieldToComparableText -PlanObject $existingPlanObject -FieldName 'source_plan_json') -ne $sourcePlanJsonRelative.Replace('\', '/'))) {
    throw ("Binding failed: existing run plan.json field `source_plan_json` does not match source frozen plan `{0}` (run: {1})." -f $sourcePlanJsonRelative, $planPath)
  }

  Assert-RunPlanMatchesSourceFrozenPlan -RunPlanObject $existingPlanObject -SourcePlanObject $boundPlanObject -RunPlanPath $planPath -SourcePlanPath $sourcePlanJsonRelative
}

$startSession = Join-Path $RepoRoot 'scripts\start_session.ps1'
if (Test-Path $startSession) {
  powershell -ExecutionPolicy Bypass -File $startSession -TaskId $TaskId -RepoRoot $RepoRoot | Out-Null
} else {
  $warnings.Add('Missing scripts/start_session.ps1; session templates were not initialized.') | Out-Null
}

$payload = [ordered]@{
  task_id = $TaskId
  plan_id = $PlanId
  run_dir = $runDir
  session_dir = $sessionDir
  binding_mode = $bindingMode
  source_plan_doc = $sourcePlanDocRelative
  source_plan_json = $sourcePlanJsonRelative
  created = $created.ToArray()
  warnings = $warnings.ToArray()
}
if ($Json) { $payload | ConvertTo-Json -Depth 6 } else { $payload }

