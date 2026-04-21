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

function Has-Property {
  param($Object, [string]$Name)

  return $null -ne $Object.PSObject.Properties[$Name]
}

function Has-UsableValue {
  param($Object, [string]$Name)

  if (-not (Has-Property -Object $Object -Name $Name)) {
    return $false
  }

  return Test-UsableValue -Value $Object.$Name
}

function Has-Value {
  param($Object, [string]$Name)

  return Has-UsableValue -Object $Object -Name $Name
}

function Has-NonEmptyCollection {
  param($Value)

  if ($null -eq $Value) {
    return $false
  }

  if ($Value -is [string]) {
    return -not [string]::IsNullOrWhiteSpace($Value)
  }

  if ($Value -is [System.Collections.IEnumerable]) {
    foreach ($item in $Value) {
      if (Test-UsableValue -Value $item) {
        return $true
      }
    }
    return $false
  }

  return $true
}

function Get-StringArray {
  param($Value)

  $items = New-Object System.Collections.Generic.List[string]
  if ($null -eq $Value) {
    return $items.ToArray()
  }

  if ($Value -is [string]) {
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
      $items.Add($Value.Trim()) | Out-Null
    }
    return $items.ToArray()
  }

  foreach ($item in $Value) {
    if ($null -eq $item) {
      continue
    }

    $text = [string]$item
    if (-not [string]::IsNullOrWhiteSpace($text)) {
      $items.Add($text.Trim()) | Out-Null
    }
  }

  return $items.ToArray()
}

function Get-NonEmptyItemCount {
  param($Value)

  return (Get-StringArray -Value $Value).Count
}

function Get-NormalizedRelativePath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return ''
  }

  return (($Path.Trim()) -replace '[\\/]+', '/')
}

function Get-TaskIdFromRunPath {
  param([string]$TargetPath)

  if ([string]::IsNullOrWhiteSpace($TargetPath)) {
    return ''
  }

  if ($TargetPath -match 'docs[\\/]ai[\\/]runs[\\/]([^\\/]+)[\\/]') {
    return $Matches[1]
  }

  return ''
}

function Get-WorkOrderTaskId {
  param(
    $WorkOrder,
    [string]$FallbackTaskId = '',
    [string]$SourcePath = ''
  )

  if (-not [string]::IsNullOrWhiteSpace($FallbackTaskId)) {
    return $FallbackTaskId
  }

  $sourceTaskId = Get-TaskIdFromRunPath -TargetPath $SourcePath
  if (-not [string]::IsNullOrWhiteSpace($sourceTaskId)) {
    return $sourceTaskId
  }

  if (Has-UsableValue -Object $WorkOrder -Name 'task_id') {
    return [string]$WorkOrder.task_id
  }

  return ''
}

function Get-ReturnPacketId {
  param([string]$WorkOrderId)

  if ([string]::IsNullOrWhiteSpace($WorkOrderId)) {
    return ''
  }

  if ($WorkOrderId -match '^WO-') {
    return ($WorkOrderId -replace '^WO-', 'RP-')
  }

  return ('RP-' + $WorkOrderId)
}

function Test-DispatchPacketRequired {
  param($WorkOrder)

  return (Has-Property -Object $WorkOrder -Name 'dispatch_packet_required') -and ($WorkOrder.dispatch_packet_required -eq $true)
}

function Test-ImplicitlyComplexWorkOrder {
  param($WorkOrder)

  $writeCount = if (Has-Property -Object $WorkOrder -Name 'write_paths') {
    Get-NonEmptyItemCount -Value $WorkOrder.write_paths
  } else {
    0
  }

  $changeCount = if (Has-Property -Object $WorkOrder -Name 'change_spec') {
    if ($null -eq $WorkOrder.change_spec) {
      0
    } else {
      @($WorkOrder.change_spec).Count
    }
  } else {
    0
  }

  return (Has-UsableValue -Object $WorkOrder -Name 'dispatch_packet_path') -or ($writeCount -gt 3) -or ($changeCount -gt 1)
}

function Is-ComplexWorkOrder {
  param($WorkOrder)

  return (Test-DispatchPacketRequired -WorkOrder $WorkOrder) -or (Test-ImplicitlyComplexWorkOrder -WorkOrder $WorkOrder)
}

function Read-JsonFile {
  param([string]$TargetPath)

  try {
    return (Get-Content -LiteralPath $TargetPath -Raw -Encoding UTF8 | ConvertFrom-Json)
  } catch {
    return $null
  }
}

function Get-MinimumRequiredReturnFields {
  return @(
    'work_order_id',
    'status',
    'summary',
    'changed_files',
    'planned_files_not_changed',
    'verification_commands',
    'verification_result',
    'deviations_from_dispatch',
    'blocked_by',
    'risks',
    'follow_up_needed',
    'written_by',
    'written_role'
  )
}

function Normalize-DispatchMessage {
  param([string]$Text)

  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }

  return ($Text -replace "`r`n", "`n").Trim()
}

function Get-FrozenPlanRequiredFields {
  return @(
    'plan_id',
    'task_id',
    'status',
    'source_plan_doc',
    'goal',
    'scope_in',
    'scope_out',
    'acceptance',
    'stop_conditions'
  )
}

function Convert-PlanFieldToComparableText {
  param(
    $PlanObject,
    [string]$FieldName
  )

  if (-not (Has-Property -Object $PlanObject -Name $FieldName)) {
    return ''
  }

  $value = $PlanObject.$FieldName
  if ($null -eq $value) {
    return ''
  }

  if ($FieldName -eq 'source_plan_doc') {
    return Get-NormalizedRelativePath -Path ([string]$value)
  }

  if ($value -is [string]) {
    return ([string]$value).Trim()
  }

  return ($value | ConvertTo-Json -Depth 50 -Compress)
}

function Get-FrozenPlanConsistencyErrors {
  param(
    $RunPlan,
    $SourcePlan,
    [string]$RunPlanLabel = 'run plan.json',
    [string]$SourcePlanLabel = 'source frozen plan.json'
  )

  $errors = New-Object System.Collections.Generic.List[string]
  foreach ($field in (Get-FrozenPlanRequiredFields)) {
    if (-not (Has-UsableValue -Object $RunPlan -Name $field)) {
      $errors.Add(("run plan 缺少字段 {0}: {1}" -f $field, $RunPlanLabel)) | Out-Null
      continue
    }

    if (-not (Has-UsableValue -Object $SourcePlan -Name $field)) {
      $errors.Add(("source frozen plan 缺少字段 {0}: {1}" -f $field, $SourcePlanLabel)) | Out-Null
      continue
    }

    $runValue = Convert-PlanFieldToComparableText -PlanObject $RunPlan -FieldName $field
    $sourceValue = Convert-PlanFieldToComparableText -PlanObject $SourcePlan -FieldName $field
    if ($runValue -ne $sourceValue) {
      $errors.Add(("run plan 与 source frozen plan 字段不一致: {0}（run={1}, source={2}）" -f $field, $RunPlanLabel, $SourcePlanLabel)) | Out-Null
    }
  }

  return $errors.ToArray()
}

function Get-AllowedSourceFrozenPlanJsonCandidates {
  param(
    [string]$TaskId,
    $RunPlan
  )

  $candidates = New-Object System.Collections.Generic.List[string]
  $candidateSet = @{}

  function Add-AllowedSourcePlanCandidate {
    param([string]$CandidatePath)

    $normalizedCandidate = Get-NormalizedRelativePath -Path $CandidatePath
    if ([string]::IsNullOrWhiteSpace($normalizedCandidate)) {
      return
    }

    $key = $normalizedCandidate.ToLowerInvariant()
    if (-not $candidateSet.ContainsKey($key)) {
      $candidateSet[$key] = $true
      $candidates.Add($normalizedCandidate) | Out-Null
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($TaskId)) {
    Add-AllowedSourcePlanCandidate -CandidatePath ("docs/plans/{0}.plan.json" -f $TaskId)
  }

  if (Has-UsableValue -Object $RunPlan -Name 'source_plan_doc') {
    $sourcePlanDoc = Get-NormalizedRelativePath -Path ([string]$RunPlan.source_plan_doc)
    if (-not [string]::IsNullOrWhiteSpace($sourcePlanDoc)) {
      if ($sourcePlanDoc -match '\.md$') {
        Add-AllowedSourcePlanCandidate -CandidatePath ($sourcePlanDoc -replace '\.md$', '.plan.json')
        Add-AllowedSourcePlanCandidate -CandidatePath ($sourcePlanDoc -replace '\.md$', '.json')
      }
      Add-AllowedSourcePlanCandidate -CandidatePath ($sourcePlanDoc + '.plan.json')
    }
  }

  return $candidates.ToArray()
}

function Resolve-SourceFrozenPlanJsonPath {
  param(
    [string]$RepoRoot,
    [string]$TaskId,
    $RunPlan
  )

  $candidates = @(Get-AllowedSourceFrozenPlanJsonCandidates -TaskId $TaskId -RunPlan $RunPlan)
  $declaredSourcePlanJson = if (Has-UsableValue -Object $RunPlan -Name 'source_plan_json') {
    Get-NormalizedRelativePath -Path ([string]$RunPlan.source_plan_json)
  } else {
    ''
  }
  $declaredSourcePlanJsonAllowed = $true
  if (-not [string]::IsNullOrWhiteSpace($declaredSourcePlanJson)) {
    $declaredSourcePlanJsonAllowed = $false
    foreach ($candidate in $candidates) {
      if ($candidate -eq $declaredSourcePlanJson) {
        $declaredSourcePlanJsonAllowed = $true
        break
      }
    }
  }

  foreach ($candidate in @($candidates)) {
    $absolutePath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $candidate))
    if (Test-Path -LiteralPath $absolutePath) {
      return [ordered]@{
        found = $true
        relative_path = $candidate
        absolute_path = $absolutePath
        candidates = @($candidates)
        declared_source_plan_json = $declaredSourcePlanJson
        declared_source_plan_json_allowed = $declaredSourcePlanJsonAllowed
      }
    }
  }

  return [ordered]@{
    found = $false
    relative_path = ''
    absolute_path = ''
    candidates = @($candidates)
    declared_source_plan_json = $declaredSourcePlanJson
    declared_source_plan_json_allowed = $declaredSourcePlanJsonAllowed
  }
}

function Should-IncludeRoleContext {
  param($WorkOrder)

  return (Has-UsableValue -Object $WorkOrder -Name 'role_source_path') -or (Has-UsableValue -Object $WorkOrder -Name 'role_map_path')
}

function Get-TaskRunArtifactPathCheck {
  param(
    [string]$RepoRoot,
    [string]$TaskId,
    [string]$RelativePath,
    [string]$ArtifactDirectory
  )

  $normalizedRelativePath = Get-NormalizedRelativePath -Path $RelativePath
  $expectedRelativePrefix = if ([string]::IsNullOrWhiteSpace($TaskId)) {
    ''
  } else {
    ("docs/ai/runs/{0}/{1}/" -f $TaskId, $ArtifactDirectory)
  }

  $payload = [ordered]@{
    ok = $false
    task_id = $TaskId
    artifact_directory = $ArtifactDirectory
    relative_path = $RelativePath
    normalized_relative_path = $normalizedRelativePath
    expected_relative_prefix = $expectedRelativePrefix
    absolute_path = ''
    expected_absolute_prefix = ''
    error = ''
  }

  if ([string]::IsNullOrWhiteSpace($normalizedRelativePath)) {
    $payload.error = ("缺少 {0} 相对路径，无法校验 task run 边界。" -f $ArtifactDirectory)
    return $payload
  }

  if ([string]::IsNullOrWhiteSpace($TaskId)) {
    $payload.error = ("缺少 task_id，无法校验 {0} 是否位于当前 task run。" -f $normalizedRelativePath)
    return $payload
  }

  $absolutePath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $normalizedRelativePath))
  $expectedAbsoluteRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot ("docs/ai/runs/{0}/{1}" -f $TaskId, $ArtifactDirectory)))
  $expectedAbsolutePrefix = $expectedAbsoluteRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar

  $payload.absolute_path = $absolutePath
  $payload.expected_absolute_prefix = $expectedAbsolutePrefix

  if (-not $absolutePath.StartsWith($expectedAbsolutePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    $payload.error = ("{0} 不在当前 task run 下，期望前缀 `{1}`，实际为 `{2}`。" -f $ArtifactDirectory, $expectedRelativePrefix, $normalizedRelativePath)
    return $payload
  }

  $currentPath = $expectedAbsoluteRoot
  if (Test-Path -LiteralPath $currentPath) {
    $rootItem = Get-Item -LiteralPath $currentPath -Force
    if (($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      $payload.error = ("{0} 根目录包含 reparse point，禁止用于 control-plane 合同产物: `{1}`。" -f $ArtifactDirectory, $currentPath)
      return $payload
    }
  }

  $relativeRemainder = $absolutePath.Substring($expectedAbsoluteRoot.TrimEnd('\', '/').Length).TrimStart('\', '/')
  if (-not [string]::IsNullOrWhiteSpace($relativeRemainder)) {
    foreach ($segment in ($relativeRemainder -split '[\\/]')) {
      if ([string]::IsNullOrWhiteSpace($segment)) {
        continue
      }

      $currentPath = Join-Path $currentPath $segment
      if (-not (Test-Path -LiteralPath $currentPath)) {
        break
      }

      $pathItem = Get-Item -LiteralPath $currentPath -Force
      if (($pathItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        $payload.error = ("{0} 路径包含 reparse point，禁止越界跳转: `{1}`。" -f $ArtifactDirectory, $currentPath)
        return $payload
      }
    }
  }

  $payload.ok = $true
  return $payload
}

function Get-DefaultExpectedWrittenRole {
  param($WorkOrder)

  if (Has-UsableValue -Object $WorkOrder -Name 'expected_written_role') {
    return [string]$WorkOrder.expected_written_role
  }

  if (-not (Has-UsableValue -Object $WorkOrder -Name 'role')) {
    return ''
  }

  $role = [string]$WorkOrder.role
  if ($role -match '^batch\d+(?:\.\d+)?-(.+reviewer)$') {
    return $Matches[1]
  }

  return $role
}

function Get-ExpectedReturnPacketAuthorship {
  param($WorkOrder)

  $expectedWrittenBy = if (Has-UsableValue -Object $WorkOrder -Name 'expected_written_by') {
    [string]$WorkOrder.expected_written_by
  } else {
    ''
  }
  $explicitPatterns = Get-ExplicitExpectedWrittenByPatterns -WorkOrder $WorkOrder
  $derivedPatterns = Get-DerivedExpectedWrittenByPatterns -WorkOrder $WorkOrder
  $contractSource = if (-not [string]::IsNullOrWhiteSpace($expectedWrittenBy)) {
    'expected_written_by'
  } elseif ($explicitPatterns.Count -gt 0) {
    'expected_written_by_patterns'
  } else {
    'derived'
  }

  return [ordered]@{
    written_role = (Get-DefaultExpectedWrittenRole -WorkOrder $WorkOrder)
    written_by = $expectedWrittenBy
    written_by_patterns = if ($explicitPatterns.Count -gt 0) { $explicitPatterns } else { $derivedPatterns }
    written_by_contract_source = $contractSource
  }
}

function Normalize-AuthorshipIdentity {
  param([string]$Value)

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return ''
  }

  return (($Value.Trim().ToLowerInvariant()) -replace '[\s_]+', '-')
}

function Add-UniqueString {
  param(
    [System.Collections.Generic.List[string]]$Bucket,
    [string]$Value
  )

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return
  }

  if (-not $Bucket.Contains($Value)) {
    $Bucket.Add($Value) | Out-Null
  }
}

function Add-NormalizedUniqueString {
  param(
    [System.Collections.Generic.List[string]]$Bucket,
    [string]$Value
  )

  $normalizedValue = Normalize-AuthorshipIdentity -Value $Value
  if ([string]::IsNullOrWhiteSpace($normalizedValue)) {
    return
  }

  if (-not $Bucket.Contains($normalizedValue)) {
    $Bucket.Add($normalizedValue) | Out-Null
  }
}

function Get-WorkOrderBatchIdentityAliases {
  param($WorkOrder)

  $aliases = New-Object System.Collections.Generic.List[string]
  if (-not (Has-UsableValue -Object $WorkOrder -Name 'work_order_id')) {
    return $aliases.ToArray()
  }

  $workOrderId = [string]$WorkOrder.work_order_id
  if ($workOrderId -match '^WO-([A-Za-z0-9\.]+)-') {
    $batchToken = Normalize-AuthorshipIdentity -Value $Matches[1]
    Add-NormalizedUniqueString -Bucket $aliases -Value $batchToken

    if ($batchToken -match '^b(\d+)$') {
      $digits = [string]$Matches[1]
      Add-NormalizedUniqueString -Bucket $aliases -Value ('batch{0}' -f $digits)
      if ($digits.Length -gt 1) {
        Add-NormalizedUniqueString -Bucket $aliases -Value ('batch{0}.{1}' -f $digits.Substring(0, 1), $digits.Substring(1))
        Add-NormalizedUniqueString -Bucket $aliases -Value ('batch-{0}.{1}' -f $digits.Substring(0, 1), $digits.Substring(1))
      }
    }
  }

  return $aliases.ToArray()
}

function Get-WorkOrderIdentitySlugAliases {
  param($WorkOrder)

  $aliases = New-Object System.Collections.Generic.List[string]
  if (-not (Has-UsableValue -Object $WorkOrder -Name 'work_order_id')) {
    return $aliases.ToArray()
  }

  $workOrderId = [string]$WorkOrder.work_order_id
  if ($workOrderId -notmatch '^WO-[^-]+-(.+)-\d+$') {
    return $aliases.ToArray()
  }

  $slug = Normalize-AuthorshipIdentity -Value $Matches[1]
  Add-NormalizedUniqueString -Bucket $aliases -Value $slug

  if ($slug -match '^(.*)-harden$') {
    Add-NormalizedUniqueString -Bucket $aliases -Value ('{0}-hardener' -f [string]$Matches[1])
  }

  $roleSuffix = ''
  if (Has-UsableValue -Object $WorkOrder -Name 'role') {
    $normalizedRole = Normalize-AuthorshipIdentity -Value ([string]$WorkOrder.role)
    foreach ($suffix in @('compiler', 'reviewer', 'author', 'hardener')) {
      if ($normalizedRole -match ('-{0}$' -f [regex]::Escape($suffix))) {
        $roleSuffix = $suffix
        break
      }
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($roleSuffix)) {
    if (($slug -notmatch ('-{0}$' -f [regex]::Escape($roleSuffix)))) {
      Add-NormalizedUniqueString -Bucket $aliases -Value ('{0}-{1}' -f $slug, $roleSuffix)
    }

    if (($roleSuffix -eq 'hardener') -and ($slug -match '^(.*)-harden$')) {
      Add-NormalizedUniqueString -Bucket $aliases -Value ('{0}-hardener' -f [string]$Matches[1])
    }
  }

  return $aliases.ToArray()
}

function Get-WrittenByIdentityAliases {
  param($WorkOrder)

  $aliases = New-Object System.Collections.Generic.List[string]
  $roleCandidates = New-Object System.Collections.Generic.List[string]
  $expectedRole = Get-DefaultExpectedWrittenRole -WorkOrder $WorkOrder
  if (-not [string]::IsNullOrWhiteSpace($expectedRole)) {
    Add-UniqueString -Bucket $roleCandidates -Value ([string]$expectedRole)
  }

  if (Has-UsableValue -Object $WorkOrder -Name 'role') {
    Add-UniqueString -Bucket $roleCandidates -Value ([string]$WorkOrder.role)
  }

  foreach ($slugAlias in (Get-WorkOrderIdentitySlugAliases -WorkOrder $WorkOrder)) {
    Add-UniqueString -Bucket $roleCandidates -Value ([string]$slugAlias)
  }

  $batchAliases = Get-WorkOrderBatchIdentityAliases -WorkOrder $WorkOrder
  foreach ($candidate in $roleCandidates.ToArray()) {
    $normalizedCandidate = Normalize-AuthorshipIdentity -Value $candidate
    Add-NormalizedUniqueString -Bucket $aliases -Value $normalizedCandidate

    foreach ($batchAlias in $batchAliases) {
      if ($normalizedCandidate.StartsWith(($batchAlias + '-'), [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-NormalizedUniqueString -Bucket $aliases -Value ($normalizedCandidate.Substring($batchAlias.Length + 1))
      }
    }

    if ($normalizedCandidate -match '^contract-(.+)$') {
      Add-NormalizedUniqueString -Bucket $aliases -Value ([string]$Matches[1])
    }

    if ($normalizedCandidate -match '^(.*)-author$') {
      Add-NormalizedUniqueString -Bucket $aliases -Value ('{0}-subagent' -f [string]$Matches[1])
    }
  }

  return $aliases.ToArray()
}

function Get-MatchingIdentityTokens {
  param([string]$Value)

  $tokens = New-Object System.Collections.Generic.List[string]
  $normalizedValue = Normalize-AuthorshipIdentity -Value $Value
  if ([string]::IsNullOrWhiteSpace($normalizedValue)) {
    return $tokens.ToArray()
  }

  foreach ($token in ($normalizedValue -split '-')) {
    if ([string]::IsNullOrWhiteSpace($token)) {
      continue
    }

    if ($token -match '^\d+(\.\d+)?$') {
      continue
    }

    if ($token -match '^(batch\d+(\.\d+)?|b\d+(\.\d+)?)$') {
      continue
    }

    if (@('batch', 'llm', 'subagent', 'worker', 'executor', 'agent') -contains $token) {
      continue
    }

    if (-not $tokens.Contains($token)) {
      $tokens.Add($token) | Out-Null
    }
  }

  return $tokens.ToArray()
}

function Get-MinimumIdentityTokenOverlap {
  param([string[]]$RoleTokens)

  if (($null -eq $RoleTokens) -or ($RoleTokens.Count -eq 0)) {
    return 0
  }

  if ($RoleTokens.Count -le 2) {
    return $RoleTokens.Count
  }

  return ($RoleTokens.Count - 1)
}

function Test-IdentityAliasMatchesRoleHints {
  param(
    [string]$Alias,
    [string[]]$RoleHints
  )

  $aliasTokens = Get-MatchingIdentityTokens -Value $Alias
  if ($aliasTokens.Count -eq 0) {
    return $false
  }

  foreach ($roleHint in $RoleHints) {
    $roleTokens = Get-MatchingIdentityTokens -Value $roleHint
    if ($roleTokens.Count -eq 0) {
      continue
    }

    $matched = 0
    foreach ($token in $aliasTokens) {
      if ($roleTokens -contains $token) {
        $matched += 1
      }
    }

    if ($matched -ge (Get-MinimumIdentityTokenOverlap -RoleTokens $roleTokens)) {
      return $true
    }
  }

  return $false
}

function Get-ExplicitExpectedWrittenByPatterns {
  param($WorkOrder)

  $patterns = New-Object System.Collections.Generic.List[string]
  if (-not (Has-Property -Object $WorkOrder -Name 'expected_written_by_patterns')) {
    return $patterns.ToArray()
  }

  foreach ($pattern in (Get-StringArray -Value $WorkOrder.expected_written_by_patterns)) {
    if (-not [string]::IsNullOrWhiteSpace($pattern) -and -not $patterns.Contains($pattern)) {
      $patterns.Add([string]$pattern) | Out-Null
    }
  }

  return $patterns.ToArray()
}

function Get-DerivedExpectedWrittenByPatterns {
  param($WorkOrder)

  $patterns = New-Object System.Collections.Generic.List[string]
  $aliases = Get-WrittenByIdentityAliases -WorkOrder $WorkOrder
  $batchAliases = Get-WorkOrderBatchIdentityAliases -WorkOrder $WorkOrder
  $roleHints = New-Object System.Collections.Generic.List[string]
  $expectedRole = Get-DefaultExpectedWrittenRole -WorkOrder $WorkOrder
  if (-not [string]::IsNullOrWhiteSpace($expectedRole)) {
    Add-UniqueString -Bucket $roleHints -Value ([string]$expectedRole)
  }

  if (Has-UsableValue -Object $WorkOrder -Name 'role') {
    Add-UniqueString -Bucket $roleHints -Value ([string]$WorkOrder.role)
  }

  foreach ($alias in $aliases) {
    if (-not (Test-IdentityAliasMatchesRoleHints -Alias $alias -RoleHints $roleHints.ToArray())) {
      continue
    }

    $escapedAlias = [regex]::Escape($alias)
    foreach ($pattern in @(
      ('^{0}$' -f $escapedAlias),
      ('^llm-{0}$' -f $escapedAlias),
      ('^{0}-subagent$' -f $escapedAlias),
      ('^subagent-{0}$' -f $escapedAlias)
    )) {
      Add-UniqueString -Bucket $patterns -Value $pattern
    }

    foreach ($batchAlias in $batchAliases) {
      $escapedBatchAlias = [regex]::Escape($batchAlias)
      foreach ($pattern in @(
        ('^{0}-{1}$' -f $escapedBatchAlias, $escapedAlias),
        ('^{0}-{1}-subagent$' -f $escapedBatchAlias, $escapedAlias),
        ('^subagent-{0}-{1}$' -f $escapedBatchAlias, $escapedAlias)
      )) {
        Add-UniqueString -Bucket $patterns -Value $pattern
      }
    }
  }

  return $patterns.ToArray()
}

function Get-ExpectedWrittenByPatterns {
  param($WorkOrder)

  $explicitPatterns = Get-ExplicitExpectedWrittenByPatterns -WorkOrder $WorkOrder
  if ($explicitPatterns.Count -gt 0) {
    return $explicitPatterns
  }

  return (Get-DerivedExpectedWrittenByPatterns -WorkOrder $WorkOrder)
}

function Test-WrittenByMatchesExpectedIdentity {
  param(
    $WorkOrder,
    [string]$WrittenBy
  )

  $normalizedWrittenBy = Normalize-AuthorshipIdentity -Value $WrittenBy
  if ([string]::IsNullOrWhiteSpace($normalizedWrittenBy)) {
    return $false
  }

  if (Has-UsableValue -Object $WorkOrder -Name 'expected_written_by') {
    return $normalizedWrittenBy -eq (Normalize-AuthorshipIdentity -Value ([string]$WorkOrder.expected_written_by))
  }

  foreach ($pattern in (Get-ExpectedWrittenByPatterns -WorkOrder $WorkOrder)) {
    if ([string]::IsNullOrWhiteSpace($pattern)) {
      continue
    }

    try {
      if ($normalizedWrittenBy -match $pattern) {
        return $true
      }
    } catch {
      continue
    }
  }

  return $false
}

function Get-ComparableAnchoredPatternLiteral {
  param([string]$Pattern)

  if ([string]::IsNullOrWhiteSpace($Pattern)) {
    return ''
  }

  if ((-not $Pattern.StartsWith('^')) -or (-not $Pattern.EndsWith('$'))) {
    return ''
  }

  $body = $Pattern.Substring(1, $Pattern.Length - 2)
  if ([string]::IsNullOrWhiteSpace($body)) {
    return ''
  }

  if ($body -match '\\(?![.\-\\])') {
    return ''
  }

  if ($body -match '(?<!\\)[\.\*\+\?\|\[\]\(\)\{\}]') {
    return ''
  }

  return (($body -replace '\\\\', '\') -replace '\\([.-])', '$1')
}

function Get-ExpectedWrittenByPatternValidationErrors {
  param($WorkOrder)

  $validationErrors = New-Object System.Collections.Generic.List[string]
  $explicitPatterns = Get-ExplicitExpectedWrittenByPatterns -WorkOrder $WorkOrder
  if ($explicitPatterns.Count -eq 0) {
    return $validationErrors.ToArray()
  }

  $allowedPatternLookup = @{}
  foreach ($allowedPattern in (Get-DerivedExpectedWrittenByPatterns -WorkOrder $WorkOrder)) {
    $allowedLiteral = Get-ComparableAnchoredPatternLiteral -Pattern $allowedPattern
    if (-not [string]::IsNullOrWhiteSpace($allowedLiteral)) {
      $allowedPatternLookup[$allowedLiteral] = $true
    }
  }

  foreach ($pattern in $explicitPatterns) {
    try {
      [void][regex]::new($pattern)
    } catch {
      $validationErrors.Add(("模式 `{0}` 不是合法正则。" -f $pattern)) | Out-Null
      continue
    }

    if ((-not $pattern.StartsWith('^')) -or (-not $pattern.EndsWith('$'))) {
      $validationErrors.Add(("模式 `{0}` 必须锚定整串。" -f $pattern)) | Out-Null
      continue
    }

    $patternLiteral = Get-ComparableAnchoredPatternLiteral -Pattern $pattern
    if ([string]::IsNullOrWhiteSpace($patternLiteral)) {
      $validationErrors.Add(("模式 `{0}` 只能使用锚定的字面身份，不能包含通配、分组或量词。" -f $pattern)) | Out-Null
      continue
    }

    if (-not $allowedPatternLookup.ContainsKey($patternLiteral)) {
      $validationErrors.Add(("模式 `{0}` 不在允许的派生作者身份模式集合内。" -f $pattern)) | Out-Null
      continue
    }
  }

  return $validationErrors.ToArray()
}

function Get-ExpectedWrittenByContractDescription {
  param($WorkOrder)

  if (Has-UsableValue -Object $WorkOrder -Name 'expected_written_by') {
    return ('`written_by` 必须为 `{0}`。' -f [string]$WorkOrder.expected_written_by)
  }

  if ((Get-ExplicitExpectedWrittenByPatterns -WorkOrder $WorkOrder).Count -gt 0) {
    return '`written_by` 必须匹配 `expected_written_by_patterns` 中至少一个正则模式。'
  }

  return ''
}

function Get-ExpectedWrittenByContractExamples {
  param($WorkOrder)

  if ((Get-ExplicitExpectedWrittenByPatterns -WorkOrder $WorkOrder).Count -eq 0) {
    return @()
  }

  $examples = New-Object System.Collections.Generic.List[string]
  foreach ($pattern in (Get-ExpectedWrittenByPatterns -WorkOrder $WorkOrder)) {
    if ($pattern -match '^\^(.+)\$$') {
      $literal = [string]$Matches[1]
      if ($literal -notmatch '[\[\]\(\)\?\+\*\|]') {
        $literal = ($literal -replace '\\-', '-')
        if (-not $examples.Contains($literal)) {
          $examples.Add($literal) | Out-Null
        }
      }
    }

    if ($examples.Count -ge 4) {
      break
    }
  }

  return $examples.ToArray()
}

function Test-CoordinatorLikeAuthorshipValue {
  param([string]$Value)

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $false
  }

  $normalized = $Value.Trim().ToLowerInvariant()
  if ($normalized.Contains('主协调器')) {
    return $true
  }

  foreach ($pattern in @(
    '(^|[-_ ])main[-_ ]?coordinator($|[-_ ])',
    '(^|[-_ ])main[-_ ]?window($|[-_ ])',
    '(^|[-_ ])plan[-_ ]?window($|[-_ ])',
    '(^|[-_ ])execute[-_ ]?window($|[-_ ])',
    '(^|[-_ ])orchestrator($|[-_ ])'
  )) {
    if ($normalized -match $pattern) {
      return $true
    }
  }

  return $false
}

function Get-DispatchPacketLoadResult {
  param(
    [string]$RepoRoot,
    $WorkOrder,
    [string]$TaskId = '',
    [string]$SourcePath = ''
  )

  $errors = New-Object System.Collections.Generic.List[string]
  $resolvedTaskId = Get-WorkOrderTaskId -WorkOrder $WorkOrder -FallbackTaskId $TaskId -SourcePath $SourcePath
  $dispatchPacketPath = if (Has-UsableValue -Object $WorkOrder -Name 'dispatch_packet_path') {
    [string]$WorkOrder.dispatch_packet_path
  } else {
    ''
  }

  $absolutePath = ''
  $dispatchPacket = $null

  if (-not [string]::IsNullOrWhiteSpace($dispatchPacketPath)) {
    $pathCheck = Get-TaskRunArtifactPathCheck -RepoRoot $RepoRoot -TaskId $resolvedTaskId -RelativePath $dispatchPacketPath -ArtifactDirectory 'dispatch_packets'
    if (-not $pathCheck.ok) {
      $errors.Add($pathCheck.error) | Out-Null
    } else {
      $absolutePath = $pathCheck.absolute_path
      if (-not (Test-Path -LiteralPath $absolutePath)) {
        $errors.Add(("dispatch_packet 不存在: {0}" -f $absolutePath)) | Out-Null
      } else {
        $dispatchPacket = Read-JsonFile -TargetPath $absolutePath
        if ($null -eq $dispatchPacket) {
          $errors.Add(("无法解析 dispatch_packet: {0}" -f $absolutePath)) | Out-Null
        }
      }
    }
  }

  return [ordered]@{
    task_id = $resolvedTaskId
    relative_path = $dispatchPacketPath
    absolute_path = $absolutePath
    packet = $dispatchPacket
    errors = $errors.ToArray()
  }
}

function Get-ReturnPacketLoadResult {
  param(
    [string]$RepoRoot,
    $WorkOrder,
    [string]$TaskId = '',
    [string]$SourcePath = ''
  )

  $errors = New-Object System.Collections.Generic.List[string]
  $resolvedTaskId = Get-WorkOrderTaskId -WorkOrder $WorkOrder -FallbackTaskId $TaskId -SourcePath $SourcePath
  $returnPacketPath = if (Has-UsableValue -Object $WorkOrder -Name 'return_packet_path') {
    [string]$WorkOrder.return_packet_path
  } else {
    ''
  }
  $expectedWorkOrderId = if (Has-UsableValue -Object $WorkOrder -Name 'work_order_id') {
    [string]$WorkOrder.work_order_id
  } else {
    ''
  }
  $expectedReturnPacketId = Get-ReturnPacketId -WorkOrderId $expectedWorkOrderId

  $absolutePath = ''
  $returnPacket = $null

  if (-not [string]::IsNullOrWhiteSpace($returnPacketPath)) {
    $pathCheck = Get-TaskRunArtifactPathCheck -RepoRoot $RepoRoot -TaskId $resolvedTaskId -RelativePath $returnPacketPath -ArtifactDirectory 'return_packets'
    if (-not $pathCheck.ok) {
      $errors.Add($pathCheck.error) | Out-Null
    } else {
      $absolutePath = $pathCheck.absolute_path

      if (-not (Test-Path -LiteralPath $absolutePath)) {
        $errors.Add(("return_packet 不存在: {0}" -f $absolutePath)) | Out-Null
      } else {
        $returnPacket = Read-JsonFile -TargetPath $absolutePath
        if ($null -eq $returnPacket) {
          $errors.Add(("无法解析 return_packet: {0}" -f $absolutePath)) | Out-Null
        } else {
          if ((-not [string]::IsNullOrWhiteSpace($resolvedTaskId)) -and (Has-UsableValue -Object $returnPacket -Name 'task_id') -and ([string]$returnPacket.task_id -ne $resolvedTaskId)) {
            $errors.Add(("return_packet.task_id 与当前 task_id 不一致（期望 `{0}`，实际 `{1}`）: {2}" -f $resolvedTaskId, [string]$returnPacket.task_id, $absolutePath)) | Out-Null
          }

          if (-not [string]::IsNullOrWhiteSpace($expectedWorkOrderId)) {
            if ((-not (Has-UsableValue -Object $returnPacket -Name 'work_order_id')) -or ([string]$returnPacket.work_order_id -ne $expectedWorkOrderId)) {
              $actualWorkOrderId = if (Has-UsableValue -Object $returnPacket -Name 'work_order_id') { [string]$returnPacket.work_order_id } else { '' }
              $errors.Add(("return_packet.work_order_id 与 work_order 不一致（期望 `{0}`，实际 `{1}`）: {2}" -f $expectedWorkOrderId, $actualWorkOrderId, $absolutePath)) | Out-Null
            }
          }

          if (-not [string]::IsNullOrWhiteSpace($expectedReturnPacketId)) {
            $actualReturnPacketId = if (Has-UsableValue -Object $returnPacket -Name 'return_packet_id') { [string]$returnPacket.return_packet_id } else { '' }
            if ($actualReturnPacketId -ne $expectedReturnPacketId) {
              $errors.Add(("return_packet.return_packet_id 与 work_order 不一致（期望 `{0}`，实际 `{1}`）: {2}" -f $expectedReturnPacketId, $actualReturnPacketId, $absolutePath)) | Out-Null
            }

            $actualLeafName = [System.IO.Path]::GetFileName($absolutePath)
            $expectedLeafName = '{0}.json' -f $expectedReturnPacketId
            if ($actualLeafName -ne $expectedLeafName) {
              $errors.Add(("return_packet_path 文件名与 work_order 不一致（期望 `{0}`，实际 `{1}`）: {2}" -f $expectedLeafName, $actualLeafName, $absolutePath)) | Out-Null
            }
          }
        }
      }
    }
  }

  return [ordered]@{
    task_id = $resolvedTaskId
    relative_path = $returnPacketPath
    absolute_path = $absolutePath
    packet = $returnPacket
    expected_work_order_id = $expectedWorkOrderId
    expected_return_packet_id = $expectedReturnPacketId
    errors = $errors.ToArray()
  }
}

function Add-BulletedLines {
  param(
    [System.Collections.Generic.List[string]]$Lines,
    [string]$Header,
    $Items,
    [switch]$WrapInBackticks
  )

  $values = Get-StringArray -Value $Items
  if ($values.Count -eq 0) {
    return
  }

  $Lines.Add($Header) | Out-Null
  foreach ($value in $values) {
    $rendered = if ($WrapInBackticks) {
      ('- `{0}`' -f $value)
    } else {
      ("- {0}" -f $value)
    }
    $Lines.Add($rendered) | Out-Null
  }
  $Lines.Add('') | Out-Null
}

function Add-ChangeSpecLines {
  param(
    [System.Collections.Generic.List[string]]$Lines,
    $ChangeSpec
  )

  if ($null -eq $ChangeSpec) {
    return
  }

  $entries = @($ChangeSpec)
  if ($entries.Count -eq 0) {
    return
  }

  $Lines.Add('逐文件改法：') | Out-Null
  foreach ($entry in $entries) {
    $path = if (Has-UsableValue -Object $entry -Name 'path') { [string]$entry.path } else { '<unknown-path>' }
    $instructions = if (Has-Property -Object $entry -Name 'instructions') {
      (Get-StringArray -Value $entry.instructions) -join '；'
    } else {
      ''
    }

    if ([string]::IsNullOrWhiteSpace($instructions)) {
      $Lines.Add(('- `{0}`' -f $path)) | Out-Null
    } else {
      $Lines.Add(('- `{0}`: {1}' -f $path, $instructions)) | Out-Null
    }
  }
  $Lines.Add('') | Out-Null
}

function Add-DispatchPacketLines {
  param(
    [System.Collections.Generic.List[string]]$Lines,
    $DispatchPacket
  )

  if ($null -eq $DispatchPacket) {
    return
  }

  $Lines.Add('复杂任务施工图：') | Out-Null

  $mapping = @(
    @{ Header = '先读后写：'; Name = 'read_before_write'; Wrap = $true },
    @{ Header = '执行顺序：'; Name = 'execution_order'; Wrap = $false },
    @{ Header = '不变量：'; Name = 'invariants'; Wrap = $false },
    @{ Header = '禁改范围：'; Name = 'forbidden_changes'; Wrap = $false },
    @{ Header = '依赖说明：'; Name = 'dependency_notes'; Wrap = $false },
    @{ Header = '完成信号：'; Name = 'done_signals'; Wrap = $false },
    @{ Header = '校验关注点：'; Name = 'verification_focus'; Wrap = $false },
    @{ Header = '回退策略：'; Name = 'fallback_strategy'; Wrap = $false },
    @{ Header = '交接说明：'; Name = 'handoff_notes'; Wrap = $false }
  )

  foreach ($item in $mapping) {
    if (Has-Property -Object $DispatchPacket -Name $item.Name) {
      Add-BulletedLines -Lines $Lines -Header $item.Header -Items $DispatchPacket.$($item.Name) -WrapInBackticks:$item.Wrap
    }
  }
}


function Add-RoleContextLines {
  param(
    [System.Collections.Generic.List[string]]$Lines,
    $WorkOrder
  )

  $roleSourcePath = if (Has-UsableValue -Object $WorkOrder -Name 'role_source_path') {
    [string]$WorkOrder.role_source_path
  } else {
    ''
  }

  $roleMapPath = if (Has-UsableValue -Object $WorkOrder -Name 'role_map_path') {
    [string]$WorkOrder.role_map_path
  } else {
    ''
  }

  if ([string]::IsNullOrWhiteSpace($roleSourcePath) -and [string]::IsNullOrWhiteSpace($roleMapPath)) {
    return
  }

  $Lines.Add('角色上下文（可选启用）：') | Out-Null
  if (-not [string]::IsNullOrWhiteSpace($roleSourcePath)) {
    $Lines.Add(('- `role_source_path`: `{0}`' -f $roleSourcePath)) | Out-Null
  }
  if (-not [string]::IsNullOrWhiteSpace($roleMapPath)) {
    $Lines.Add(('- `role_map_path`: `{0}`' -f $roleMapPath)) | Out-Null
  }
  $Lines.Add('- 缺省上述字段时，沿用历史工单编译行为。') | Out-Null
  $Lines.Add('') | Out-Null
}

function Test-ContainsAllFields {
  param(
    [string[]]$Actual,
    [string[]]$Expected
  )

  $lookup = @{}
  foreach ($field in $Actual) {
    $lookup[$field] = $true
  }

  foreach ($field in $Expected) {
    if (-not $lookup.ContainsKey($field)) {
      return $false
    }
  }

  return $true
}

function Get-DispatchMessageCompilation {
  param(
    $WorkOrder,
    $DispatchPacket,
    [switch]$IncludeRoleContext
  )

  $errors = New-Object System.Collections.Generic.List[string]

  foreach ($field in @('task_goal', 'read_paths_mandatory', 'write_paths', 'scope_out', 'acceptance_criteria', 'stop_conditions', 'return_packet_path')) {
    if (-not (Has-UsableValue -Object $WorkOrder -Name $field)) {
      $errors.Add(("work_order 缺少 dispatch_message_raw 编译必需字段 {0}" -f $field)) | Out-Null
    }
  }

  if (-not (Has-NonEmptyCollection -Value $WorkOrder.read_paths_mandatory)) {
    $errors.Add('work_order.read_paths_mandatory 缺失或为空，无法编译 dispatch_message_raw。') | Out-Null
  }
  if (-not (Has-NonEmptyCollection -Value $WorkOrder.write_paths)) {
    $errors.Add('work_order.write_paths 缺失或为空，无法编译 dispatch_message_raw。') | Out-Null
  }
  if (-not (Has-NonEmptyCollection -Value $WorkOrder.scope_out)) {
    $errors.Add('work_order.scope_out 缺失或为空，无法编译 dispatch_message_raw。') | Out-Null
  }
  if (-not (Has-NonEmptyCollection -Value $WorkOrder.acceptance_criteria)) {
    $errors.Add('work_order.acceptance_criteria 缺失或为空，无法编译 dispatch_message_raw。') | Out-Null
  }
  if (-not (Has-NonEmptyCollection -Value $WorkOrder.stop_conditions)) {
    $errors.Add('work_order.stop_conditions 缺失或为空，无法编译 dispatch_message_raw。') | Out-Null
  }

  if (Is-ComplexWorkOrder -WorkOrder $WorkOrder) {
    if ($null -eq $DispatchPacket) {
      $errors.Add('复杂任务缺少 dispatch_packet，无法编译 dispatch_message_raw。') | Out-Null
    } else {
      foreach ($field in @('read_before_write', 'execution_order', 'change_spec')) {
        if (-not (Has-Property -Object $DispatchPacket -Name $field) -or -not (Has-NonEmptyCollection -Value $DispatchPacket.$field)) {
          $errors.Add(("dispatch_packet.{0} 缺失或为空，无法编译 dispatch_message_raw。" -f $field)) | Out-Null
        }
      }
    }
  }

  if ($errors.Count -gt 0) {
    return [ordered]@{
      ok = $false
      errors = $errors.ToArray()
      text = ''
    }
  }

  $lines = New-Object System.Collections.Generic.List[string]
  $role = if (Has-UsableValue -Object $WorkOrder -Name 'role') { [string]$WorkOrder.role } else { 'execution-worker' }

  $lines.Add(('你是 `{0}` 执行子代理。' -f $role)) | Out-Null
  $lines.Add('先完整阅读 `read_paths_mandatory`，`evidence_summary` 仅作导航，不能代替原文件阅读。') | Out-Null
  $lines.Add('说明性文本默认中文；字段名、路径、脚本参数、代码标识符保持原样。') | Out-Null
  $lines.Add('') | Out-Null

  if ($IncludeRoleContext) {
    Add-RoleContextLines -Lines $lines -WorkOrder $WorkOrder
  }

  Add-BulletedLines -Lines $lines -Header '任务目标：' -Items @([string]$WorkOrder.task_goal)
  Add-BulletedLines -Lines $lines -Header '必读上下文：' -Items $WorkOrder.read_paths_mandatory -WrapInBackticks
  Add-BulletedLines -Lines $lines -Header '导航摘要：' -Items $WorkOrder.evidence_summary
  Add-BulletedLines -Lines $lines -Header '唯一写入范围：' -Items $WorkOrder.write_paths -WrapInBackticks
  Add-BulletedLines -Lines $lines -Header '禁改范围：' -Items $WorkOrder.scope_out
  Add-BulletedLines -Lines $lines -Header '执行约束：' -Items $WorkOrder.constraints
  Add-ChangeSpecLines -Lines $lines -ChangeSpec $WorkOrder.change_spec

  if ($null -ne $DispatchPacket) {
    Add-DispatchPacketLines -Lines $lines -DispatchPacket $DispatchPacket
  }

  Add-BulletedLines -Lines $lines -Header '执行步骤：' -Items $WorkOrder.execution_steps
  Add-BulletedLines -Lines $lines -Header '验收标准：' -Items $WorkOrder.acceptance_criteria
  Add-BulletedLines -Lines $lines -Header '验证步骤：' -Items $WorkOrder.verification_steps
  Add-BulletedLines -Lines $lines -Header '停止条件：' -Items $WorkOrder.stop_conditions

  $completionGate = if (Has-UsableValue -Object $WorkOrder -Name 'completion_gate') {
    [string]$WorkOrder.completion_gate
  } else {
    'return_packet_written_and_accepted'
  }

  $lines.Add('回执要求：') | Out-Null
  $lines.Add('- `return_packet` 正文必须由执行子代理本人填写，主协调器不得代写。') | Out-Null
  $lines.Add(('- `return_packet_path`: `{0}`' -f [string]$WorkOrder.return_packet_path)) | Out-Null
  $lines.Add(('- `completion_gate`: `{0}`' -f $completionGate)) | Out-Null
  if (Has-UsableValue -Object $WorkOrder -Name 'expected_written_role') {
    $lines.Add(('- `written_role` 必须为 `{0}`。' -f [string]$WorkOrder.expected_written_role)) | Out-Null
  }
  $writtenByContractDescription = Get-ExpectedWrittenByContractDescription -WorkOrder $WorkOrder
  if (-not [string]::IsNullOrWhiteSpace($writtenByContractDescription)) {
    $lines.Add(('- {0}' -f $writtenByContractDescription)) | Out-Null
  }
  if (-not (Has-UsableValue -Object $WorkOrder -Name 'expected_written_by')) {
    $writtenByExamples = Get-ExpectedWrittenByContractExamples -WorkOrder $WorkOrder
    if ($writtenByExamples.Count -gt 0) {
      $lines.Add(('- `written_by` 示例可为：`{0}`。' -f ($writtenByExamples -join '` / `'))) | Out-Null
    }
  }
  $lines.Add('- 若信息不足以安全实施，返回 `blocked`，不要猜测。') | Out-Null
  $lines.Add('- 完成前先写 `return_packet`，再声明完成。') | Out-Null

  return [ordered]@{
    ok = $true
    errors = @()
    text = (($lines.ToArray() -join "`n").Trim())
  }
}





