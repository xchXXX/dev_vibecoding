param(
  [Parameter(Mandatory = $true)]
  [string]$Action,
  [string]$RepoRoot = (Get-Location).Path,
  [string]$TaskId = '',
  [string]$Topic = '',
  [string]$Title = '',
  [string]$Owner = 'main-coordinator',
  [string]$Objective = '',
  [string]$SubtaskId = '',
  [string]$Actor = 'main-coordinator',
  [string]$Type = '',
  [string]$Summary = '',
  [string]$EventJson = '',
  [switch]$Json
)

$ErrorActionPreference = 'Stop'

function Get-RepoPath {
  param([string]$Root)
  return [System.IO.Path]::GetFullPath($Root)
}

function Get-TasksRoot {
  param([string]$Root)
  return (Join-Path (Get-RepoPath -Root $Root) 'docs/ai/tasks')
}

function Get-TaskDir {
  param([string]$Root, [string]$Id)
  return (Join-Path (Get-TasksRoot -Root $Root) $Id)
}

function Get-StatePath {
  param([string]$Root, [string]$Id)
  return (Join-Path (Get-TaskDir -Root $Root -Id $Id) 'state.json')
}

function Get-TaskDocPath {
  param([string]$Root, [string]$Id)
  return (Join-Path (Get-TaskDir -Root $Root -Id $Id) 'task.md')
}

function Get-EventsPath {
  param([string]$Root, [string]$Id)
  return (Join-Path (Get-TaskDir -Root $Root -Id $Id) 'events.jsonl')
}

function Write-Payload {
  param($Payload)
  if ($Json) {
    $Payload | ConvertTo-Json -Depth 100
  } else {
    $Payload
  }
}

function Test-NonEmptyString {
  param($Value)
  return ($Value -is [string]) -and (-not [string]::IsNullOrWhiteSpace($Value))
}

function Test-NonEmptyArray {
  param($Value)
  if ($null -eq $Value) {
    return $false
  }

  $items = @($Value)
  if ($items.Count -eq 0) {
    return $false
  }

  foreach ($item in $items) {
    if ($item -is [string]) {
      if (-not [string]::IsNullOrWhiteSpace($item)) {
        return $true
      }
      continue
    }

    if ($null -ne $item) {
      return $true
    }
  }

  return $false
}

function Test-IsArrayValue {
  param($Value)

  if ($null -eq $Value) {
    return $false
  }

  return ($Value -is [System.Collections.IEnumerable]) -and -not ($Value -is [string])
}

function Test-StringArrayValue {
  param(
    $Value,
    [bool]$AllowEmpty = $true
  )

  if (-not (Test-IsArrayValue -Value $Value)) {
    return $false
  }

  $items = @($Value)
  if (-not $AllowEmpty -and $items.Count -eq 0) {
    return $false
  }

  foreach ($item in $items) {
    if (-not ($item -is [string])) {
      return $false
    }
  }

  return $true
}

function Read-JsonFile {
  param([string]$PathValue)
  return (Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-JsonFile {
  param([string]$PathValue, $Data)
  Set-Content -LiteralPath $PathValue -Value ($Data | ConvertTo-Json -Depth 100) -Encoding UTF8
}

function New-TaskSlug {
  param([string]$Value)
  $text = if ([string]::IsNullOrWhiteSpace($Value)) { 'task' } else { $Value.ToLowerInvariant() }
  $text = [regex]::Replace($text, '[^a-z0-9]+', '-')
  $text = $text.Trim('-')
  if ([string]::IsNullOrWhiteSpace($text)) {
    $text = 'task'
  }
  if ($text.Length -gt 48) {
    $text = $text.Substring(0, 48).Trim('-')
  }
  return $text
}

function New-TaskIdValue {
  param([string]$Value)
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $slug = New-TaskSlug -Value $Value
  $suffix = ([guid]::NewGuid().ToString('N')).Substring(0, 6)
  return ('{0}-{1}-{2}' -f $stamp, $slug, $suffix)
}

function Normalize-RepoRelativePath {
  param([string]$Value)

  if (-not (Test-NonEmptyString -Value $Value)) {
    return ''
  }

  $normalized = $Value.Trim().Replace('\', '/')
  while ($normalized.StartsWith('./')) {
    $normalized = $normalized.Substring(2)
  }

  $normalized = $normalized.TrimStart('/')
  return $normalized
}

function Test-PathMatchesScope {
  param(
    [string]$PathValue,
    [object[]]$Scopes
  )

  $normalizedPath = Normalize-RepoRelativePath -Value $PathValue
  if (-not (Test-NonEmptyString -Value $normalizedPath)) {
    return $false
  }

  foreach ($scope in @($Scopes)) {
    $normalizedScope = Normalize-RepoRelativePath -Value ([string]$scope)
    if (-not (Test-NonEmptyString -Value $normalizedScope)) {
      continue
    }

    if ($normalizedScope.EndsWith('/')) {
      $prefix = $normalizedScope.TrimEnd('/')
      if (($normalizedPath -eq $prefix) -or $normalizedPath.StartsWith($prefix + '/')) {
        return $true
      }
      continue
    }

    $pattern = New-Object System.Management.Automation.WildcardPattern($normalizedScope, [System.Management.Automation.WildcardOptions]::IgnoreCase)
    if ($pattern.IsMatch($normalizedPath)) {
      return $true
    }
  }

  return $false
}

function Render-TaskMarkdown {
  param($State)

  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add('# 任务摘要') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('## 基本信息') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add(('- `task_id`: `{0}`' -f [string]$State.task_id)) | Out-Null
  $lines.Add(('- `title`: {0}' -f [string]$State.title)) | Out-Null
  $lines.Add(('- `status`: `{0}`' -f [string]$State.status)) | Out-Null
  $lines.Add(('- `owner`: `{0}`' -f [string]$State.owner)) | Out-Null
  $lines.Add('') | Out-Null

  $lines.Add('## 目标') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add(('- {0}' -f [string]$State.objective)) | Out-Null
  $lines.Add('') | Out-Null

  $lines.Add('## 范围') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('### Scope In') | Out-Null
  $lines.Add('') | Out-Null
  foreach ($item in @($State.scope_in)) {
    $lines.Add(('- {0}' -f [string]$item)) | Out-Null
  }
  $lines.Add('') | Out-Null
  $lines.Add('### Scope Out') | Out-Null
  $lines.Add('') | Out-Null
  foreach ($item in @($State.scope_out)) {
    $lines.Add(('- {0}' -f [string]$item)) | Out-Null
  }
  $lines.Add('') | Out-Null

  $lines.Add('## 验收标准') | Out-Null
  $lines.Add('') | Out-Null
  foreach ($item in @($State.acceptance)) {
    $lines.Add(('- {0}' -f [string]$item)) | Out-Null
  }
  $lines.Add('') | Out-Null

  $lines.Add('## 停止条件') | Out-Null
  $lines.Add('') | Out-Null
  foreach ($item in @($State.stop_conditions)) {
    $lines.Add(('- {0}' -f [string]$item)) | Out-Null
  }
  $lines.Add('') | Out-Null

  $lines.Add('## 关键决定') | Out-Null
  $lines.Add('') | Out-Null
  foreach ($item in @($State.decisions)) {
    $lines.Add(('- {0}' -f [string]$item)) | Out-Null
  }
  $lines.Add('') | Out-Null

  $lines.Add('## 当前阶段') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add(('- `current_phase`: `{0}`' -f [string]$State.current_phase)) | Out-Null
  $lines.Add('') | Out-Null

  $lines.Add('## 子任务') | Out-Null
  $lines.Add('') | Out-Null
  if (@($State.subtasks).Count -eq 0) {
    $lines.Add('- 当前没有子任务。') | Out-Null
    $lines.Add('') | Out-Null
  } else {
    foreach ($subtask in @($State.subtasks)) {
      $lines.Add(('### {0}' -f [string]$subtask.subtask_id)) | Out-Null
      $lines.Add('') | Out-Null
      $lines.Add(('- `title`: {0}' -f [string]$subtask.title)) | Out-Null
      $lines.Add(('- `role`: `{0}`' -f [string]$subtask.role)) | Out-Null
      $lines.Add(('- `status`: `{0}`' -f [string]$subtask.status)) | Out-Null
      if ($null -ne $subtask.assignment) {
        $lines.Add(('- `goal`: {0}' -f [string]$subtask.assignment.goal)) | Out-Null
      }
      if (Test-NonEmptyArray -Value $subtask.dependencies) {
        $lines.Add(('- `dependencies`: `{0}`' -f ((@($subtask.dependencies) -join '`, `')))) | Out-Null
      }
      $lines.Add('') | Out-Null
    }
  }

  $lines.Add('## 更新时间') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add(('- `{0}`' -f [string]$State.updated_at)) | Out-Null

  return (($lines.ToArray() -join "`r`n").Trim() + "`r`n")
}

function Set-StateTimestamp {
  param($State)
  $State.updated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
}

function New-InitialState {
  param(
    [string]$Id,
    [string]$ResolvedTitle,
    [string]$ResolvedOwner,
    [string]$ResolvedObjective
  )

  $timestamp = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
  return [ordered]@{
    task_id = $Id
    title = $ResolvedTitle
    status = 'draft'
    owner = $ResolvedOwner
    objective = $ResolvedObjective
    scope_in = @('To be filled')
    scope_out = @('To be filled')
    acceptance = @('To be filled')
    stop_conditions = @('To be filled')
    decisions = @()
    current_phase = 'planning'
    subtasks = @()
    updated_at = $timestamp
    version = 1
  }
}

function Get-AllowedPhases {
  return @('planning','doc_sync','test_sync','code_impl','review','blocked')
}

function Get-VerificationContractRequiredFields {
  return @('minimal_repro','hit_proof','diagnostic_checks','acceptance_checks','non_goals','review_evidence')
}

function Test-ReviewEvidenceObject {
  param(
    $Value,
    [bool]$AllowEmpty = $true
  )

  if ($null -eq $Value) {
    return $false
  }

  if ($Value -is [string]) {
    return $false
  }

  if (Test-IsArrayValue -Value $Value) {
    return $false
  }

  $properties = @()
  if ($Value -is [System.Collections.IDictionary]) {
    foreach ($key in $Value.Keys) {
      $properties += [pscustomobject]@{
        Name = [string]$key
        Value = $Value[$key]
      }
    }
  } elseif ($null -ne $Value.PSObject) {
    foreach ($property in $Value.PSObject.Properties) {
      $properties += [pscustomobject]@{
        Name = [string]$property.Name
        Value = $property.Value
      }
    }
  } else {
    return $false
  }

  if (-not $AllowEmpty -and $properties.Count -eq 0) {
    return $false
  }

  foreach ($property in $properties) {
    if (-not (Test-NonEmptyString -Value $property.Name)) {
      return $false
    }

    if (-not (Test-NonEmptyString -Value ([string]$property.Value))) {
      return $false
    }
  }

  return $true
}

function Test-IsEvidenceProducerRole {
  param([string]$Role)

  if (-not (Test-NonEmptyString -Value $Role)) {
    return $false
  }

  return $Role.EndsWith('implementer') -or ($Role -in @('test-verifier','ops-runbook'))
}

function Get-RepoRelativeTaskPaths {
  param([string]$Id)

  return [ordered]@{
    state_json = ('docs/ai/tasks/{0}/state.json' -f $Id)
    task_md = ('docs/ai/tasks/{0}/task.md' -f $Id)
    events_jsonl = ('docs/ai/tasks/{0}/events.jsonl' -f $Id)
  }
}

function Add-ValidationError {
  param(
    [System.Collections.Generic.List[string]]$Errors,
    [string]$Message
  )
  $Errors.Add($Message) | Out-Null
}

function Add-ValidationWarning {
  param(
    [System.Collections.Generic.List[string]]$Warnings,
    [string]$Message
  )
  $Warnings.Add($Message) | Out-Null
}

function Validate-RoleMapAndManifest {
  param(
    [string]$Root,
    [System.Collections.Generic.List[string]]$Errors
  )

  $roleMapPath = Join-Path (Get-RepoPath -Root $Root) 'agents/codex-role-map.json'
  $manifestPath = Join-Path (Get-RepoPath -Root $Root) 'agents/manifest.json'
  $requiredRoles = @('planner','reader','reviewer','backend-implementer','frontend-implementer','test-verifier','doc-curator','ops-runbook')
  $allowedAgentTypes = @('default','explorer','worker')

  if (-not (Test-Path -LiteralPath $roleMapPath)) {
    Add-ValidationError -Errors $Errors -Message ("Missing codex role map: {0}" -f $roleMapPath)
    return
  }

  if (-not (Test-Path -LiteralPath $manifestPath)) {
    Add-ValidationError -Errors $Errors -Message ("Missing agents manifest: {0}" -f $manifestPath)
    return
  }

  try {
    $roleMap = Read-JsonFile -PathValue $roleMapPath
  } catch {
    Add-ValidationError -Errors $Errors -Message ("Cannot parse codex role map: {0}" -f $roleMapPath)
    return
  }

  try {
    $manifest = Read-JsonFile -PathValue $manifestPath
  } catch {
    Add-ValidationError -Errors $Errors -Message ("Cannot parse agents manifest: {0}" -f $manifestPath)
    return
  }

  if ($null -eq $roleMap.PSObject.Properties['roles']) {
    Add-ValidationError -Errors $Errors -Message ("codex role map is missing roles: {0}" -f $roleMapPath)
    return
  }

  if ($null -eq $manifest.PSObject.Properties['items']) {
    Add-ValidationError -Errors $Errors -Message ("agents manifest is missing items: {0}" -f $manifestPath)
    return
  }

  $manifestById = @{}
  $manifestRoleIds = New-Object System.Collections.Generic.List[string]
  foreach ($item in @($manifest.items)) {
    if ($null -eq $item.PSObject.Properties['id']) {
      Add-ValidationError -Errors $Errors -Message ("agents manifest item is missing id: {0}" -f $manifestPath)
      continue
    }

    $roleId = [string]$item.id
    if ($manifestById.ContainsKey($roleId)) {
      Add-ValidationError -Errors $Errors -Message ("agents manifest contains duplicate role id: {0}" -f $roleId)
      continue
    }

    $manifestById[$roleId] = $item
    $manifestRoleIds.Add($roleId) | Out-Null
  }

  $roleMapRoleIds = New-Object System.Collections.Generic.List[string]
  foreach ($property in $roleMap.roles.PSObject.Properties) {
    $roleMapRoleIds.Add([string]$property.Name) | Out-Null
  }

  foreach ($roleName in $requiredRoles) {
    if ($roleMapRoleIds -notcontains $roleName) {
      Add-ValidationError -Errors $Errors -Message ("codex role map is missing required role: {0}" -f $roleName)
    }

    if ($manifestRoleIds -notcontains $roleName) {
      Add-ValidationError -Errors $Errors -Message ("agents manifest is missing required role: {0}" -f $roleName)
    }
  }

  foreach ($roleName in $roleMapRoleIds) {
    $rolePayload = $roleMap.roles.$roleName
    $agentType = if ($null -ne $rolePayload.PSObject.Properties['agent_type']) { [string]$rolePayload.agent_type } else { '' }
    if ($allowedAgentTypes -notcontains $agentType) {
      Add-ValidationError -Errors $Errors -Message ("codex role map has invalid agent_type for {0}: {1}" -f $roleName, $agentType)
    }

    if (-not $manifestById.ContainsKey($roleName)) {
      Add-ValidationError -Errors $Errors -Message ("role-map contains role not present in manifest: {0}" -f $roleName)
      continue
    }

    $manifestItem = $manifestById[$roleName]
    $tools = @($manifestItem.tools)
    $manifestAllowWrite = ($tools -contains 'Write')
    $manifestAllowShell = ($tools -contains 'Bash')
    $roleAllowWrite = ($null -ne $rolePayload.PSObject.Properties['allow_write']) -and ([bool]$rolePayload.allow_write)
    $roleAllowShell = ($null -ne $rolePayload.PSObject.Properties['allow_shell']) -and ([bool]$rolePayload.allow_shell)

    if ($roleAllowWrite -ne $manifestAllowWrite) {
      Add-ValidationError -Errors $Errors -Message ("allow_write mismatch between role-map and manifest for role: {0}" -f $roleName)
    }

    if ($roleAllowShell -ne $manifestAllowShell) {
      Add-ValidationError -Errors $Errors -Message ("allow_shell mismatch between role-map and manifest for role: {0}" -f $roleName)
    }
  }

  foreach ($roleName in $manifestRoleIds) {
    if ($roleMapRoleIds -notcontains $roleName) {
      Add-ValidationError -Errors $Errors -Message ("manifest contains role not present in role-map: {0}" -f $roleName)
    }
  }
}

function Validate-ResultPaths {
  param(
    [string]$SubtaskId,
    [string]$FieldName,
    [object[]]$Paths,
    [object[]]$WriteScopes,
    [System.Collections.Generic.List[string]]$Errors
  )

  foreach ($pathValue in @($Paths)) {
    $normalizedPath = Normalize-RepoRelativePath -Value ([string]$pathValue)
    if (-not (Test-NonEmptyString -Value $normalizedPath)) {
      Add-ValidationError -Errors $Errors -Message ("subtask.result.{0} contains an empty path: {1}" -f $FieldName, $SubtaskId)
      continue
    }

    if (-not (Test-PathMatchesScope -PathValue $normalizedPath -Scopes $WriteScopes)) {
      Add-ValidationError -Errors $Errors -Message ("subtask.result.{0} escapes subtask.write_paths: {1} -> {2}" -f $FieldName, $SubtaskId, $normalizedPath)
    }
  }
}

function Validate-SubtaskResult {
  param(
    $Subtask,
    [System.Collections.Generic.List[string]]$Errors
  )

  $subtaskId = [string]$Subtask.subtask_id
  $status = [string]$Subtask.status
  $role = [string]$Subtask.role
  $result = $Subtask.result

  foreach ($field in @('status','summary','changed_files','planned_files_not_changed','verification','deviations','blocked_by','risks','follow_up','written_by','written_role')) {
    if ($null -eq $result.PSObject.Properties[$field]) {
      Add-ValidationError -Errors $Errors -Message ("subtask.result.{0} is missing: {1}" -f $field, $subtaskId)
    }
  }

  if (-not (Test-NonEmptyString -Value ([string]$result.status))) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.status is missing or empty: {0}" -f $subtaskId)
  } elseif ([string]$result.status -ne $status) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.status must match subtask.status: {0}" -f $subtaskId)
  }

  foreach ($field in @('summary','written_by','written_role')) {
    if (-not (Test-NonEmptyString -Value ([string]$result.$field))) {
      Add-ValidationError -Errors $Errors -Message ("subtask.result.{0} is missing or empty: {1}" -f $field, $subtaskId)
    }
  }

  if ((Test-NonEmptyString -Value ([string]$result.written_role)) -and ([string]$result.written_role -ne $role)) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.written_role must match subtask.role: {0}" -f $subtaskId)
  }

  foreach ($field in @('changed_files','planned_files_not_changed','deviations','blocked_by','risks','follow_up')) {
    if ($null -eq $result.PSObject.Properties[$field]) {
      continue
    }

    if (-not (Test-StringArrayValue -Value $result.$field)) {
      Add-ValidationError -Errors $Errors -Message ("subtask.result.{0} must be an array of strings: {1}" -f $field, $subtaskId)
    }
  }

  if (Test-StringArrayValue -Value $result.changed_files) {
    Validate-ResultPaths -SubtaskId $subtaskId -FieldName 'changed_files' -Paths @($result.changed_files) -WriteScopes @($Subtask.write_paths) -Errors $Errors
  }

  if (Test-StringArrayValue -Value $result.planned_files_not_changed) {
    Validate-ResultPaths -SubtaskId $subtaskId -FieldName 'planned_files_not_changed' -Paths @($result.planned_files_not_changed) -WriteScopes @($Subtask.write_paths) -Errors $Errors
  }

  if (($role -in @('reader','reviewer')) -and (Test-NonEmptyArray -Value $result.changed_files)) {
    Add-ValidationError -Errors $Errors -Message ("read-only role cannot report changed_files: {0}" -f $subtaskId)
  }

  if ($status -eq 'blocked' -and -not (Test-NonEmptyArray -Value $result.blocked_by)) {
    Add-ValidationError -Errors $Errors -Message ("blocked subtask.result.blocked_by is missing or empty: {0}" -f $subtaskId)
  }

  if ($null -eq $result.verification) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.verification is missing: {0}" -f $subtaskId)
    return
  }

  if ($null -eq $result.verification.PSObject.Properties['commands']) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.verification.commands is missing: {0}" -f $subtaskId)
  } elseif (-not (Test-StringArrayValue -Value $result.verification.commands)) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.verification.commands must be an array of strings: {0}" -f $subtaskId)
  } elseif (($status -eq 'completed') -and -not (Test-NonEmptyArray -Value $result.verification.commands)) {
    Add-ValidationError -Errors $Errors -Message ("completed subtask.result.verification.commands is missing or empty: {0}" -f $subtaskId)
  }

  if ($null -eq $result.verification.PSObject.Properties['result']) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.verification.result is missing: {0}" -f $subtaskId)
  } elseif (-not (Test-NonEmptyString -Value ([string]$result.verification.result))) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.verification.result is missing or empty: {0}" -f $subtaskId)
  }

  if (($null -ne $result.PSObject.Properties['review_evidence']) -and -not (Test-ReviewEvidenceObject -Value $result.review_evidence -AllowEmpty $false)) {
    Add-ValidationError -Errors $Errors -Message ("subtask.result.review_evidence must be an object with non-empty string values: {0}" -f $subtaskId)
  }
}

function Validate-ReviewEvidenceCoverage {
  param(
    $State,
    [object[]]$RequiredSlots,
    [System.Collections.Generic.List[string]]$Errors
  )

  $coveredSlots = @{}
  foreach ($subtask in @($State.subtasks)) {
    if ([string]$subtask.status -ne 'completed') {
      continue
    }

    if (-not (Test-IsEvidenceProducerRole -Role ([string]$subtask.role))) {
      continue
    }

    if ($null -eq $subtask.PSObject.Properties['result']) {
      continue
    }

    $result = $subtask.result
    if ($null -eq $result.PSObject.Properties['review_evidence']) {
      continue
    }

    if (-not (Test-ReviewEvidenceObject -Value $result.review_evidence -AllowEmpty $false)) {
      continue
    }

    $entries = if ($result.review_evidence -is [System.Collections.IDictionary]) {
      foreach ($key in $result.review_evidence.Keys) {
        [pscustomobject]@{
          Name = [string]$key
          Value = $result.review_evidence[$key]
        }
      }
    } else {
      @($result.review_evidence.PSObject.Properties | ForEach-Object {
        [pscustomobject]@{
          Name = [string]$_.Name
          Value = $_.Value
        }
      })
    }

    foreach ($entry in $entries) {
      if (Test-NonEmptyString -Value $entry.Name) {
        $coveredSlots[$entry.Name] = [string]$subtask.subtask_id
      }
    }
  }

  foreach ($slot in @($RequiredSlots)) {
    $slotName = [string]$slot
    if (-not (Test-NonEmptyString -Value $slotName)) {
      continue
    }

    if (-not $coveredSlots.ContainsKey($slotName)) {
      Add-ValidationError -Errors $Errors -Message ("state.json.verification_contract.review_evidence slot is not covered by any completed execution/test subtask.result.review_evidence: {0}" -f $slotName)
    }
  }
}

function Validate-VerificationContract {
  param(
    $State,
    [System.Collections.Generic.List[string]]$Errors
  )

  $phase = [string]$State.current_phase
  $requiresContract = @('code_impl','review') -contains $phase
  $contractProperty = $State.PSObject.Properties['verification_contract']

  if ($null -eq $contractProperty) {
    if ($requiresContract) {
      Add-ValidationError -Errors $Errors -Message ("state.json.verification_contract is required before entering {0}" -f $phase)
    }
    return
  }

  $contract = $contractProperty.Value
  if ($null -eq $contract -or $contract -is [string] -or (Test-IsArrayValue -Value $contract)) {
    Add-ValidationError -Errors $Errors -Message 'state.json.verification_contract must be an object.'
    return
  }

  foreach ($field in (Get-VerificationContractRequiredFields)) {
    if ($null -eq $contract.PSObject.Properties[$field]) {
      Add-ValidationError -Errors $Errors -Message ("state.json.verification_contract.{0} is missing." -f $field)
    }
  }

  foreach ($field in @('minimal_repro','hit_proof')) {
    if (($null -ne $contract.PSObject.Properties[$field]) -and -not (Test-NonEmptyString -Value ([string]$contract.$field))) {
      Add-ValidationError -Errors $Errors -Message ("state.json.verification_contract.{0} is missing or empty." -f $field)
    }
  }

  foreach ($field in @('diagnostic_checks','acceptance_checks','non_goals','review_evidence')) {
    if (($null -ne $contract.PSObject.Properties[$field]) -and -not (Test-StringArrayValue -Value $contract.$field -AllowEmpty $false)) {
      Add-ValidationError -Errors $Errors -Message ("state.json.verification_contract.{0} must be a non-empty array of strings." -f $field)
    }
  }

  if (($phase -eq 'review') -and (Test-StringArrayValue -Value $contract.review_evidence -AllowEmpty $false)) {
    Validate-ReviewEvidenceCoverage -State $State -RequiredSlots @($contract.review_evidence) -Errors $Errors
  }
}

function Validate-CompletedTaskClosure {
  param(
    $State,
    [System.Collections.Generic.List[string]]$Errors
  )

  if ([string]$State.status -ne 'completed') {
    return
  }

  foreach ($subtask in @($State.subtasks)) {
    $subtaskId = [string]$subtask.subtask_id
    $subtaskStatus = [string]$subtask.status
    if (@('completed','cancelled') -contains $subtaskStatus) {
      continue
    }

    Add-ValidationError -Errors $Errors -Message ("state.json.status=completed requires every subtask to be completed or cancelled: {0} is {1}" -f $subtaskId, $subtaskStatus)
  }
}

function Validate-State {
  param(
    [string]$Root,
    [string]$Id
  )

  $errors = New-Object System.Collections.Generic.List[string]
  $warnings = New-Object System.Collections.Generic.List[string]
  $taskDir = Get-TaskDir -Root $Root -Id $Id
  $statePath = Get-StatePath -Root $Root -Id $Id
  $taskDocPath = Get-TaskDocPath -Root $Root -Id $Id
  $eventsPath = Get-EventsPath -Root $Root -Id $Id

  if (-not (Test-NonEmptyString -Value $Id)) {
    Add-ValidationError -Errors $errors -Message 'validate requires -TaskId.'
    return [ordered]@{ ok = $false; errors = $errors.ToArray(); warnings = @(); task_id = $Id }
  }

  if (-not (Test-Path -LiteralPath $taskDir)) {
    Add-ValidationError -Errors $errors -Message ("Missing task directory: {0}" -f $taskDir)
    return [ordered]@{ ok = $false; errors = $errors.ToArray(); warnings = @(); task_id = $Id }
  }

  if (-not (Test-Path -LiteralPath $statePath)) {
    Add-ValidationError -Errors $errors -Message ("Missing state.json: {0}" -f $statePath)
    return [ordered]@{ ok = $false; errors = $errors.ToArray(); warnings = @(); task_id = $Id }
  }

  $state = $null
  try {
    $state = Read-JsonFile -PathValue $statePath
  } catch {
    Add-ValidationError -Errors $errors -Message ("Cannot parse state.json: {0}" -f $statePath)
    return [ordered]@{ ok = $false; errors = $errors.ToArray(); warnings = @(); task_id = $Id }
  }

  foreach ($field in @('task_id','title','status','owner','objective','scope_in','scope_out','acceptance','stop_conditions','decisions','current_phase','subtasks','updated_at','version')) {
    if ($null -eq $state.PSObject.Properties[$field]) {
      Add-ValidationError -Errors $errors -Message ("state.json is missing field {0}: {1}" -f $field, $statePath)
    }
  }

  if ((Test-NonEmptyString -Value ([string]$state.task_id)) -and ([string]$state.task_id -ne $Id)) {
    Add-ValidationError -Errors $errors -Message ("state.json.task_id does not match directory task_id: {0}" -f $statePath)
  }

  if (@('draft','active','blocked','completed','archived') -notcontains [string]$state.status) {
    Add-ValidationError -Errors $errors -Message ("state.json.status is invalid: {0}" -f [string]$state.status)
  }

  foreach ($field in @('title','owner','objective','current_phase','updated_at')) {
    if (-not (Test-NonEmptyString -Value ([string]$state.$field))) {
      Add-ValidationError -Errors $errors -Message ("state.json.{0} is missing or empty: {1}" -f $field, $statePath)
    }
  }

  $allowedPhases = Get-AllowedPhases
  if ((Test-NonEmptyString -Value ([string]$state.current_phase)) -and ($allowedPhases -notcontains [string]$state.current_phase)) {
    Add-ValidationError -Errors $errors -Message ("state.json.current_phase is invalid; allowed values: {0}" -f ($allowedPhases -join ', '))
  }

  foreach ($field in @('scope_in','scope_out','acceptance','stop_conditions')) {
    if (-not (Test-StringArrayValue -Value $state.$field -AllowEmpty $false)) {
      Add-ValidationError -Errors $errors -Message ("state.json.{0} is missing or empty: {1}" -f $field, $statePath)
    }
  }

  if (-not (Test-StringArrayValue -Value $state.decisions)) {
    Add-ValidationError -Errors $errors -Message ("state.json.decisions must be an array of strings: {0}" -f $statePath)
  }

  if (-not (Test-IsArrayValue -Value $state.subtasks)) {
    Add-ValidationError -Errors $errors -Message ("state.json.subtasks must be an array: {0}" -f $statePath)
    $state.subtasks = @()
  }

  $subtaskIds = @{}
  foreach ($subtask in @($state.subtasks)) {
    foreach ($field in @('subtask_id','title','role','status','dependencies','read_paths','write_paths','assignment')) {
      if ($null -eq $subtask.PSObject.Properties[$field]) {
        Add-ValidationError -Errors $errors -Message ("subtask is missing field {0}: {1}" -f $field, $statePath)
      }
    }

    $subtaskId = [string]$subtask.subtask_id
    if (-not (Test-NonEmptyString -Value $subtaskId)) {
      Add-ValidationError -Errors $errors -Message ("subtask_id is missing or empty: {0}" -f $statePath)
    } elseif ($subtaskIds.ContainsKey($subtaskId)) {
      Add-ValidationError -Errors $errors -Message ("Duplicate subtask_id: {0}" -f $subtaskId)
    } else {
      $subtaskIds[$subtaskId] = $true
    }

    if (-not (Test-NonEmptyString -Value ([string]$subtask.title))) {
      Add-ValidationError -Errors $errors -Message ("subtask.title is missing or empty: {0}" -f $subtaskId)
    }

    if (-not (Test-NonEmptyString -Value ([string]$subtask.role))) {
      Add-ValidationError -Errors $errors -Message ("subtask.role is missing or empty: {0}" -f $subtaskId)
    }

    if (@('pending','ready','in_progress','blocked','completed','cancelled') -notcontains [string]$subtask.status) {
      Add-ValidationError -Errors $errors -Message ("subtask.status is invalid: {0}" -f [string]$subtask.status)
    }

    if ([string]$subtask.status -ne 'cancelled') {
      if (-not (Test-StringArrayValue -Value $subtask.read_paths -AllowEmpty $false)) {
        Add-ValidationError -Errors $errors -Message ("subtask.read_paths is missing or empty: {0}" -f $subtaskId)
      }

      $requiresWritePaths = (@('reader','reviewer') -notcontains [string]$subtask.role)
      if ($requiresWritePaths -and -not (Test-StringArrayValue -Value $subtask.write_paths -AllowEmpty $false)) {
        Add-ValidationError -Errors $errors -Message ("subtask.write_paths is missing or empty: {0}" -f $subtaskId)
      }

      if ((@('reader','reviewer') -contains [string]$subtask.role) -and -not (Test-StringArrayValue -Value $subtask.write_paths)) {
        Add-ValidationError -Errors $errors -Message ("read-only role write_paths must be an array: {0}" -f $subtaskId)
      }

      if ((@('reader','reviewer') -contains [string]$subtask.role) -and (Test-NonEmptyArray -Value $subtask.write_paths)) {
        Add-ValidationError -Errors $errors -Message ("read-only role should not declare write_paths: {0}" -f $subtaskId)
      }
    }

    if (-not (Test-StringArrayValue -Value $subtask.dependencies)) {
      Add-ValidationError -Errors $errors -Message ("subtask.dependencies must be an array of strings: {0}" -f $subtaskId)
    }

    $assignment = $subtask.assignment
    if ($null -eq $assignment) {
      Add-ValidationError -Errors $errors -Message ("subtask.assignment is missing: {0}" -f $subtaskId)
    } else {
      foreach ($field in @('goal','must_include','verification')) {
        if ($null -eq $assignment.PSObject.Properties[$field]) {
          Add-ValidationError -Errors $errors -Message ("subtask.assignment.{0} is missing: {1}" -f $field, $subtaskId)
        }
      }

      if (-not (Test-NonEmptyString -Value ([string]$assignment.goal))) {
        Add-ValidationError -Errors $errors -Message ("subtask.assignment.goal is missing or empty: {0}" -f $subtaskId)
      }

      foreach ($field in @('must_include','verification')) {
        if (-not (Test-StringArrayValue -Value $assignment.$field -AllowEmpty $false)) {
          Add-ValidationError -Errors $errors -Message ("subtask.assignment.{0} is missing or empty: {1}" -f $field, $subtaskId)
        }
      }
    }

    if (@('completed','blocked') -contains [string]$subtask.status) {
      if ($null -eq $subtask.PSObject.Properties['result']) {
        Add-ValidationError -Errors $errors -Message ("{0} subtask is missing result: {1}" -f [string]$subtask.status, $subtaskId)
      } else {
        Validate-SubtaskResult -Subtask $subtask -Errors $errors
      }
    }
  }

  Validate-VerificationContract -State $state -Errors $errors
  Validate-CompletedTaskClosure -State $state -Errors $errors

  if (-not (Test-Path -LiteralPath $taskDocPath)) {
    Add-ValidationError -Errors $errors -Message ("Missing task.md: {0}" -f $taskDocPath)
  }

  if (Test-Path -LiteralPath $eventsPath) {
    $lineNumber = 0
    foreach ($line in (Get-Content -LiteralPath $eventsPath -Encoding UTF8)) {
      $lineNumber += 1
      if ([string]::IsNullOrWhiteSpace($line)) {
        continue
      }

      $event = $null
      try {
        $event = $line | ConvertFrom-Json
      } catch {
        Add-ValidationError -Errors $errors -Message ("events.jsonl line {0} is not valid JSON: {1}" -f $lineNumber, $eventsPath)
        continue
      }

      foreach ($field in @('ts','actor','type','summary','refs')) {
        if ($null -eq $event.PSObject.Properties[$field]) {
          Add-ValidationError -Errors $errors -Message ("events.jsonl line {0} is missing field {1}: {2}" -f $lineNumber, $field, $eventsPath)
        }
      }

      if (($null -ne $event.PSObject.Properties['refs']) -and -not (Test-StringArrayValue -Value $event.refs)) {
        Add-ValidationError -Errors $errors -Message ("events.jsonl line {0} field refs must be an array of strings: {1}" -f $lineNumber, $eventsPath)
      }
    }
  } else {
    Add-ValidationWarning -Warnings $warnings -Message ("events.jsonl not found; continuing in minimal mode: {0}" -f $eventsPath)
  }

  Validate-RoleMapAndManifest -Root $Root -Errors $errors

  return [ordered]@{
    ok = ($errors.Count -eq 0)
    task_id = $Id
    task_dir = $taskDir
    errors = $errors.ToArray()
    warnings = $warnings.ToArray()
    subtask_count = @($state.subtasks).Count
  }
}

switch ($Action) {
  'new-task' {
    $taskIdValue = New-TaskIdValue -Value $Topic
    Write-Payload ([ordered]@{
      ok = $true
      task_id = $taskIdValue
      topic = $Topic
    })
    break
  }

  'init-task' {
    if (-not (Test-NonEmptyString -Value $TaskId)) {
      throw 'init-task requires -TaskId.'
    }

    $repo = Get-RepoPath -Root $RepoRoot
    $tasksRoot = Get-TasksRoot -Root $repo
    $taskDir = Get-TaskDir -Root $repo -Id $TaskId
    New-Item -ItemType Directory -Path $tasksRoot -Force | Out-Null
    if (Test-Path -LiteralPath $taskDir) {
      throw ("task already exists: {0}" -f $taskDir)
    }
    New-Item -ItemType Directory -Path $taskDir -Force | Out-Null

    $resolvedTitle = if (Test-NonEmptyString -Value $Title) { $Title } else { $TaskId }
    $resolvedOwner = if (Test-NonEmptyString -Value $Owner) { $Owner } else { 'main-coordinator' }
    $resolvedObjective = if (Test-NonEmptyString -Value $Objective) { $Objective } else { 'Fill the task objective before execution.' }
    $state = New-InitialState -Id $TaskId -ResolvedTitle $resolvedTitle -ResolvedOwner $resolvedOwner -ResolvedObjective $resolvedObjective
    $statePath = Get-StatePath -Root $repo -Id $TaskId
    $taskDocPath = Get-TaskDocPath -Root $repo -Id $TaskId
    $eventsPath = Get-EventsPath -Root $repo -Id $TaskId

    Write-JsonFile -PathValue $statePath -Data $state
    Set-Content -LiteralPath $taskDocPath -Value (Render-TaskMarkdown -State $state) -Encoding UTF8
    $initEvent = [ordered]@{
      ts = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
      actor = 'main-coordinator'
      type = 'task_initialized'
      summary = 'Initialized task control plane.'
      refs = @(
        ('docs/ai/tasks/{0}/state.json' -f $TaskId),
        ('docs/ai/tasks/{0}/task.md' -f $TaskId)
      )
    } | ConvertTo-Json -Depth 20 -Compress
    Set-Content -LiteralPath $eventsPath -Value ($initEvent + "`r`n") -Encoding UTF8

    Write-Payload ([ordered]@{
      ok = $true
      task_id = $TaskId
      task_dir = $taskDir
      created = @($statePath, $taskDocPath, $eventsPath)
    })
    break
  }

  'sync-task-md' {
    if (-not (Test-NonEmptyString -Value $TaskId)) {
      throw 'sync-task-md requires -TaskId.'
    }

    $state = Read-JsonFile -PathValue (Get-StatePath -Root $RepoRoot -Id $TaskId)
    Set-StateTimestamp -State $state
    Write-JsonFile -PathValue (Get-StatePath -Root $RepoRoot -Id $TaskId) -Data $state
    $content = Render-TaskMarkdown -State $state
    Set-Content -LiteralPath (Get-TaskDocPath -Root $RepoRoot -Id $TaskId) -Value $content -Encoding UTF8
    Write-Payload ([ordered]@{
      ok = $true
      task_id = $TaskId
      task_md_path = (Get-TaskDocPath -Root $RepoRoot -Id $TaskId)
    })
    break
  }

  'append-event' {
    if (-not (Test-NonEmptyString -Value $TaskId)) {
      throw 'append-event requires -TaskId.'
    }

    $event = $null
    if (Test-NonEmptyString -Value $EventJson) {
      $event = $EventJson | ConvertFrom-Json
    } else {
      if (-not (Test-NonEmptyString -Value $Type)) {
        throw 'append-event requires -Type when -EventJson is not provided.'
      }
      if (-not (Test-NonEmptyString -Value $Summary)) {
        throw 'append-event requires -Summary when -EventJson is not provided.'
      }
      $event = [ordered]@{
        ts = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
        actor = if (Test-NonEmptyString -Value $Actor) { $Actor } else { 'main-coordinator' }
        type = $Type
        summary = $Summary
        refs = @()
      }
    }

    Add-Content -LiteralPath (Get-EventsPath -Root $RepoRoot -Id $TaskId) -Value (($event | ConvertTo-Json -Depth 20 -Compress) + "`r`n") -Encoding UTF8
    Write-Payload ([ordered]@{
      ok = $true
      task_id = $TaskId
      events_path = (Get-EventsPath -Root $RepoRoot -Id $TaskId)
      type = [string]$event.type
    })
    break
  }

  'build-subtask-brief' {
    if (-not (Test-NonEmptyString -Value $TaskId)) {
      throw 'build-subtask-brief requires -TaskId.'
    }
    if (-not (Test-NonEmptyString -Value $SubtaskId)) {
      throw 'build-subtask-brief requires -SubtaskId.'
    }

    $state = Read-JsonFile -PathValue (Get-StatePath -Root $RepoRoot -Id $TaskId)
    $subtask = @($state.subtasks) | Where-Object { [string]$_.subtask_id -eq $SubtaskId } | Select-Object -First 1
    if ($null -eq $subtask) {
      throw ("subtask not found: {0}" -f $SubtaskId)
    }

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add(('You own subtask `{0}`.' -f [string]$subtask.subtask_id)) | Out-Null
    $lines.Add(('Role: `{0}`.' -f [string]$subtask.role)) | Out-Null
    $lines.Add(('Title: {0}' -f [string]$subtask.title)) | Out-Null
    $lines.Add(('Goal: {0}' -f [string]$subtask.assignment.goal)) | Out-Null
    $lines.Add('Read these paths first:') | Out-Null
    foreach ($pathValue in @($subtask.read_paths)) {
      $lines.Add(('- `{0}`' -f [string]$pathValue)) | Out-Null
    }
    $lines.Add('Only write to these paths:') | Out-Null
    foreach ($pathValue in @($subtask.write_paths)) {
      $lines.Add(('- `{0}`' -f [string]$pathValue)) | Out-Null
    }
    $lines.Add('Must include:') | Out-Null
    foreach ($item in @($subtask.assignment.must_include)) {
      $lines.Add(('- {0}' -f [string]$item)) | Out-Null
    }
    $lines.Add('Write results back to `state.json.subtasks[].result`, and append `events.jsonl` only when needed.') | Out-Null
    $text = ($lines.ToArray() -join "`n")

    Write-Payload ([ordered]@{
      ok = $true
      task_id = $TaskId
      subtask_id = $SubtaskId
      brief = $text
    })
    break
  }

  'build-execute-handoff' {
    if (-not (Test-NonEmptyString -Value $TaskId)) {
      throw 'build-execute-handoff requires -TaskId.'
    }

    $statePath = Get-StatePath -Root $RepoRoot -Id $TaskId
    if (-not (Test-Path -LiteralPath $statePath)) {
      throw ("Missing state.json: {0}" -f $statePath)
    }

    $state = Read-JsonFile -PathValue $statePath
    $paths = Get-RepoRelativeTaskPaths -Id $TaskId
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add(('继续已有长任务 `task_id={0}`。' -f $TaskId)) | Out-Null
    $lines.Add(('当前 `current_phase`：`{0}`。' -f [string]$state.current_phase)) | Out-Null
    $lines.Add(('任务目标：{0}' -f [string]$state.objective)) | Out-Null
    if (Test-NonEmptyArray -Value $state.scope_in) {
      $lines.Add('当前 scope_in：') | Out-Null
      foreach ($item in @($state.scope_in)) {
        $lines.Add(('- {0}' -f [string]$item)) | Out-Null
      }
    }
    if (Test-NonEmptyArray -Value $state.scope_out) {
      $lines.Add('当前 scope_out：') | Out-Null
      foreach ($item in @($state.scope_out)) {
        $lines.Add(('- {0}' -f [string]$item)) | Out-Null
      }
    }
    $lines.Add('先完整阅读以下文件：') | Out-Null
    $lines.Add(('- `{0}`' -f [string]$paths.state_json)) | Out-Null
    $lines.Add(('- `{0}`' -f [string]$paths.task_md)) | Out-Null
    $lines.Add('若已定稿方案文档与施工文档，也必须一并阅读。') | Out-Null
    $lines.Add('执行要求：先委派子代理，再推进当前批次；主协调器不得直接代做执行型或审查型工作。') | Out-Null
    $lines.Add('优先顺序：先组织核心文档同步，再组织测试补齐与测试执行，之后才进入代码或配置实现。') | Out-Null
    if ([string]$state.current_phase -eq 'planning') {
      $lines.Add('若 `current_phase` 仍为 `planning`，默认先从核心文档同步开始，再进入测试补齐与测试执行。') | Out-Null
    }
    if (Test-NonEmptyArray -Value $state.acceptance) {
      $lines.Add('当前已定稿验收：') | Out-Null
      foreach ($item in @($state.acceptance)) {
        $lines.Add(('- {0}' -f [string]$item)) | Out-Null
      }
    }
    if (Test-NonEmptyArray -Value $state.stop_conditions) {
      $lines.Add('当前停止条件：') | Out-Null
      foreach ($item in @($state.stop_conditions)) {
        $lines.Add(('- {0}' -f [string]$item)) | Out-Null
      }
    }
    if (Test-NonEmptyArray -Value $state.subtasks) {
      $lines.Add('首批建议子任务：') | Out-Null
      foreach ($subtask in @($state.subtasks)) {
        $goal = ''
        if ($null -ne $subtask.PSObject.Properties['assignment'] -and $null -ne $subtask.assignment.PSObject.Properties['goal']) {
          $goal = [string]$subtask.assignment.goal
        }
        $lines.Add(('- `{0}` / role=`{1}` / status=`{2}` / goal={3}' -f [string]$subtask.subtask_id, [string]$subtask.role, [string]$subtask.status, $goal)) | Out-Null
      }
    }
    $lines.Add('禁止事项：不要重新 `init-task`，不要把新开执行窗口误判成新任务，不要跳过子代理直接收口。') | Out-Null

    $text = ($lines.ToArray() -join "`n")
    Write-Payload ([ordered]@{
      ok = $true
      task_id = $TaskId
      current_phase = [string]$state.current_phase
      handoff = $text
    })
    break
  }

  'validate' {
    $result = Validate-State -Root $RepoRoot -Id $TaskId
    Write-Payload $result
    if (-not $result.ok) {
      exit 1
    }
    break
  }

  default {
    throw ("Unsupported action: {0}" -f $Action)
  }
}

