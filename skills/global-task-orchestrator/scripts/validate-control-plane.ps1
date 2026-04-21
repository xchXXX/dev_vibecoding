param(
  [string]$RepoRoot = (Get-Location).Path,
  [string]$TaskId = '',
  [switch]$Json
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot 'control-plane-common.ps1')

function Add-Message {
  param(
    [System.Collections.Generic.List[string]]$Bucket,
    [string]$Message
  )
  $Bucket.Add($Message) | Out-Null
}

$errors = New-Object 'System.Collections.Generic.List[string]'
$warnings = New-Object 'System.Collections.Generic.List[string]'
$plansChecked = 0
$workOrdersChecked = 0
$returnPacketsChecked = 0
$minimumReturnFields = Get-MinimumRequiredReturnFields
$allowedAgentTypes = @('default', 'explorer', 'worker')
$requiredCodexRoles = @(
  'planner',
  'reader',
  'reviewer',
  'backend-implementer',
  'frontend-implementer',
  'test-verifier',
  'doc-curator',
  'ops-runbook'
)

if ([string]::IsNullOrWhiteSpace($TaskId)) {
  Add-Message -Bucket $errors -Message 'validate-control-plane.ps1 必须提供 -TaskId。'
}

if ($TaskId) {
  $runDir = Join-Path $RepoRoot ("docs/ai/runs/{0}" -f $TaskId)
  $planPath = Join-Path $runDir 'plan.json'
  $workOrderDir = Join-Path $runDir 'work_orders'
  $returnPacketDir = Join-Path $runDir 'return_packets'
  $roleMapPath = Join-Path $RepoRoot 'agents/codex-role-map.json'
  $manifestPath = Join-Path $RepoRoot 'agents/manifest.json'
  $workOrderIndex = @{}
  $workOrderPathIndex = @{}

  $roleMapRoleIndex = @{}
  $manifestRoleIndex = @{}
  if (-not (Test-Path -LiteralPath $roleMapPath)) {
    Add-Message -Bucket $errors -Message ("缺少 codex-role-map: {0}" -f $roleMapPath)
  } else {
    $roleMap = Read-JsonFile -TargetPath $roleMapPath
    if ($null -eq $roleMap) {
      Add-Message -Bucket $errors -Message ("无法解析 codex-role-map: {0}" -f $roleMapPath)
    } elseif (-not (Has-Property -Object $roleMap -Name 'roles')) {
      Add-Message -Bucket $errors -Message ("codex-role-map 缺少 roles 字段: {0}" -f $roleMapPath)
    } else {
      $roleEntries = @($roleMap.roles.PSObject.Properties)
      if ($roleEntries.Count -eq 0) {
        Add-Message -Bucket $errors -Message ("codex-role-map.roles 不能为空: {0}" -f $roleMapPath)
      }

      foreach ($roleEntry in $roleEntries) {
        $roleName = [string]$roleEntry.Name
        $roleMapRoleIndex[$roleName] = $roleEntry.Value
        if (-not (Has-UsableValue -Object $roleEntry.Value -Name 'agent_type')) {
          Add-Message -Bucket $errors -Message ("codex-role-map 角色缺少 agent_type: {0} ({1})" -f $roleName, $roleMapPath)
          continue
        }

        $agentType = [string]$roleEntry.Value.agent_type
        if ($allowedAgentTypes -notcontains $agentType) {
          Add-Message -Bucket $errors -Message ("codex-role-map 角色 agent_type 非法: {0} -> {1}（允许值: {2}）" -f $roleName, $agentType, ($allowedAgentTypes -join '/'))
        }
      }
    }
  }

  foreach ($requiredRole in $requiredCodexRoles) {
    if (-not $roleMapRoleIndex.ContainsKey($requiredRole)) {
      Add-Message -Bucket $errors -Message ("codex-role-map 缺少必需角色: {0}" -f $requiredRole)
    }
  }

  if (-not (Test-Path -LiteralPath $manifestPath)) {
    Add-Message -Bucket $errors -Message ("缺少 agents/manifest.json: {0}" -f $manifestPath)
  } else {
    $manifest = Read-JsonFile -TargetPath $manifestPath
    if ($null -eq $manifest) {
      Add-Message -Bucket $errors -Message ("无法解析 agents/manifest.json: {0}" -f $manifestPath)
    } elseif (-not (Has-NonEmptyCollection -Value $manifest.items)) {
      Add-Message -Bucket $errors -Message ("agents/manifest.json.items 缺失或为空: {0}" -f $manifestPath)
    } else {
      foreach ($manifestItem in @($manifest.items)) {
        if (-not (Has-UsableValue -Object $manifestItem -Name 'id')) {
          Add-Message -Bucket $errors -Message ("agents/manifest.json 存在缺少 id 的条目: {0}" -f $manifestPath)
          continue
        }

        $manifestRoleId = [string]$manifestItem.id
        $manifestRoleIndex[$manifestRoleId] = $manifestItem

        if (-not $roleMapRoleIndex.ContainsKey($manifestRoleId)) {
          Add-Message -Bucket $errors -Message ("manifest 角色未在 codex-role-map 中定义: {0}" -f $manifestRoleId)
          continue
        }

        $roleMapRole = $roleMapRoleIndex[$manifestRoleId]
        $toolSet = @{}
        foreach ($tool in (Get-StringArray -Value $manifestItem.tools)) {
          $toolSet[$tool.ToLowerInvariant()] = $true
        }

        if (Has-UsableValue -Object $roleMapRole -Name 'allow_write') {
          $allowWrite = [bool]$roleMapRole.allow_write
          $hasWriteTool = $toolSet.ContainsKey('write')
          if ($allowWrite -ne $hasWriteTool) {
            Add-Message -Bucket $errors -Message ("role-map 与 manifest 写权限不一致: {0} (allow_write={1}, manifest.tools 包含 Write={2})" -f $manifestRoleId, $allowWrite, $hasWriteTool)
          }
        }

        if (Has-UsableValue -Object $roleMapRole -Name 'allow_shell') {
          $allowShell = [bool]$roleMapRole.allow_shell
          $hasBashTool = $toolSet.ContainsKey('bash')
          if ($allowShell -ne $hasBashTool) {
            Add-Message -Bucket $errors -Message ("role-map 与 manifest shell 权限不一致: {0} (allow_shell={1}, manifest.tools 包含 Bash={2})" -f $manifestRoleId, $allowShell, $hasBashTool)
          }
        }
      }
    }
  }

  foreach ($roleMapRoleId in $roleMapRoleIndex.Keys) {
    if (-not $manifestRoleIndex.ContainsKey($roleMapRoleId)) {
      Add-Message -Bucket $errors -Message ("codex-role-map 角色未在 manifest 中定义: {0}" -f $roleMapRoleId)
    }
  }

  if (-not (Test-Path $planPath)) {
    Add-Message -Bucket $errors -Message ("缺少 plan.json: {0}" -f $planPath)
  } else {
    $plansChecked += 1
    $plan = Read-JsonFile -TargetPath $planPath
    if ($null -eq $plan) {
      Add-Message -Bucket $errors -Message ("无法解析 plan.json: {0}" -f $planPath)
    } else {
      foreach ($field in @('plan_id','task_id','status','source_plan_doc','goal','scope_in','scope_out','acceptance','stop_conditions')) {
        if (-not (Has-UsableValue -Object $plan -Name $field)) {
          Add-Message -Bucket $errors -Message ("plan.json 缺少字段 {0}: {1}" -f $field, $planPath)
        }
      }

      if ((Has-UsableValue -Object $plan -Name 'task_id') -and ($plan.task_id -ne $TaskId)) {
        Add-Message -Bucket $errors -Message ("plan.json.task_id 与目录 task_id 不一致: {0}" -f $planPath)
      }

      if ((Has-UsableValue -Object $plan -Name 'status') -and ($plan.status -ne 'frozen')) {
        Add-Message -Bucket $errors -Message ("plan.json.status 必须为 frozen: {0}" -f $planPath)
      }

      if (Has-UsableValue -Object $plan -Name 'source_plan_doc') {
        $sourcePlanDocPath = Join-Path $RepoRoot $plan.source_plan_doc
        if (-not (Test-Path $sourcePlanDocPath)) {
          Add-Message -Bucket $errors -Message ("source_plan_doc 指向的方案文档不存在: {0}" -f $sourcePlanDocPath)
        }
      }

      $sourceFrozenPlanResolution = Resolve-SourceFrozenPlanJsonPath -RepoRoot $RepoRoot -TaskId $TaskId -RunPlan $plan
      if ((-not [string]::IsNullOrWhiteSpace([string]$sourceFrozenPlanResolution.declared_source_plan_json)) -and (-not [bool]$sourceFrozenPlanResolution.declared_source_plan_json_allowed)) {
        $candidateText = if (@($sourceFrozenPlanResolution.candidates).Count -gt 0) {
          (@($sourceFrozenPlanResolution.candidates) -join ', ')
        } else {
          '<none>'
        }
        Add-Message -Bucket $errors -Message ("plan.json.source_plan_json 必须绑定到 source_plan_doc 对应的 frozen plan.json（声明 `{0}`，候选: {1}）: {2}" -f [string]$sourceFrozenPlanResolution.declared_source_plan_json, $candidateText, $planPath)
      }

      if (-not $sourceFrozenPlanResolution.found) {
        $candidateText = if (@($sourceFrozenPlanResolution.candidates).Count -gt 0) {
          (@($sourceFrozenPlanResolution.candidates) -join ', ')
        } else {
          '<none>'
        }
        Add-Message -Bucket $errors -Message ("无法定位 source frozen plan.json（候选: {0}）: {1}" -f $candidateText, $planPath)
      } else {
        $sourceFrozenPlan = Read-JsonFile -TargetPath $sourceFrozenPlanResolution.absolute_path
        if ($null -eq $sourceFrozenPlan) {
          Add-Message -Bucket $errors -Message ("无法解析 source frozen plan.json: {0}" -f $sourceFrozenPlanResolution.absolute_path)
        } else {
          foreach ($field in (Get-FrozenPlanRequiredFields)) {
            if (-not (Has-UsableValue -Object $sourceFrozenPlan -Name $field)) {
              Add-Message -Bucket $errors -Message ("source frozen plan.json 缺少字段 {0}: {1}" -f $field, $sourceFrozenPlanResolution.absolute_path)
            }
          }

          if ((Has-UsableValue -Object $sourceFrozenPlan -Name 'status') -and ($sourceFrozenPlan.status -ne 'frozen')) {
            Add-Message -Bucket $errors -Message ("source frozen plan.json.status 必须为 frozen: {0}" -f $sourceFrozenPlanResolution.absolute_path)
          }

          foreach ($planConsistencyError in (Get-FrozenPlanConsistencyErrors -RunPlan $plan -SourcePlan $sourceFrozenPlan -RunPlanLabel $planPath -SourcePlanLabel $sourceFrozenPlanResolution.absolute_path)) {
            Add-Message -Bucket $errors -Message ([string]$planConsistencyError)
          }
        }
      }
    }
  }

  if (Test-Path -LiteralPath $workOrderDir) {
    Get-ChildItem -Path $workOrderDir -Filter *.json -File | ForEach-Object {
      $workOrdersChecked += 1
      $obj = Read-JsonFile -TargetPath $_.FullName
      if ($null -eq $obj) {
        Add-Message -Bucket $errors -Message ("无法解析 work_order: {0}" -f $_.FullName)
        return
      }

      foreach ($field in @('work_order_id','dispatch_message_raw','return_packet_path','return_packet_required','required_return_fields','completion_gate','state_owner')) {
        if (-not (Has-UsableValue -Object $obj -Name $field)) {
          Add-Message -Bucket $errors -Message ("work_order 缺少字段 {0}: {1}" -f $field, $_.FullName)
        }
      }

      foreach ($patternValidationError in (Get-ExpectedWrittenByPatternValidationErrors -WorkOrder $obj)) {
        Add-Message -Bucket $errors -Message ("work_order.expected_written_by_patterns 非法（{0}）: {1}" -f [string]$patternValidationError, $_.FullName)
      }

      if ((Has-UsableValue -Object $obj -Name 'task_id') -and ($obj.task_id -ne $TaskId)) {
        Add-Message -Bucket $errors -Message ("work_order.task_id 与目录 task_id 不一致: {0}" -f $_.FullName)
      }

      if (-not (Has-NonEmptyCollection -Value $obj.read_paths_mandatory)) {
        Add-Message -Bucket $errors -Message ("work_order.read_paths_mandatory 缺失或为空: {0}" -f $_.FullName)
      }

      if (-not (Has-NonEmptyCollection -Value $obj.evidence_summary)) {
        Add-Message -Bucket $errors -Message ("work_order.evidence_summary 缺失或为空: {0}" -f $_.FullName)
      }

      $requiredReturnFields = if (Has-Property -Object $obj -Name 'required_return_fields') { Get-StringArray -Value $obj.required_return_fields } else { @() }
      if (-not (Test-ContainsAllFields -Actual $requiredReturnFields -Expected $minimumReturnFields)) {
        Add-Message -Bucket $errors -Message ("work_order.required_return_fields 缺少仓库最低字段集合: {0}" -f $_.FullName)
      }
      $dispatchPacketResult = Get-DispatchPacketLoadResult -RepoRoot $RepoRoot -WorkOrder $obj -TaskId $TaskId -SourcePath $_.FullName
      $dispatchPacket = $dispatchPacketResult.packet
      $dispatchPacketAbsolutePath = [string]$dispatchPacketResult.absolute_path
      foreach ($dispatchPacketError in @($dispatchPacketResult.errors)) {
        Add-Message -Bucket $errors -Message ([string]$dispatchPacketError)
      }

      if (Has-UsableValue -Object $obj -Name 'dispatch_message_raw') {
        $raw = [string]$obj.dispatch_message_raw
        if (-not $raw.Contains('中文')) {
          Add-Message -Bucket $errors -Message ("dispatch_message_raw 缺少必需约束 '中文': {0}" -f $_.FullName)
        }

        $hasOwnerGuard = $raw.Contains('主协调器不得代写') -or $raw.Contains('主协调器及其他角色不得替代撰写') -or $raw.Contains('不要代写执行子代理正文')
        if (-not $hasOwnerGuard) {
          Add-Message -Bucket $errors -Message ("dispatch_message_raw 缺少必需约束 '主协调器不得代写': {0}" -f $_.FullName)
        }

        $hasAuthorOwnership = $raw.Contains('执行子代理本人') -or $raw.Contains('执行子代理正文') -or $raw.Contains('执行子代理')
        if (-not $hasAuthorOwnership) {
          Add-Message -Bucket $errors -Message ("dispatch_message_raw 缺少必需约束 '执行子代理本人': {0}" -f $_.FullName)
        }

        $compilation = if (@($dispatchPacketResult.errors).Count -gt 0) {
          [ordered]@{
            ok = $false
            errors = @($dispatchPacketResult.errors)
            text = ''
          }
        } else {
          Get-DispatchMessageCompilation -WorkOrder $obj -DispatchPacket $dispatchPacket -IncludeRoleContext:(Should-IncludeRoleContext -WorkOrder $obj)
        }
        if (-not $compilation.ok) {
          Add-Message -Bucket $errors -Message ("dispatch_message_raw 无法从合同稳定编译: {0}" -f $_.FullName)
          if (@($dispatchPacketResult.errors).Count -eq 0) {
            foreach ($compileError in $compilation.errors) {
              Add-Message -Bucket $errors -Message ("  - {0}" -f $compileError)
            }
          }
        } elseif ((Normalize-DispatchMessage -Text $raw) -ne (Normalize-DispatchMessage -Text $compilation.text)) {
          Add-Message -Bucket $errors -Message ("dispatch_message_raw 与合同编译结果不一致: {0}" -f $_.FullName)
        }
      }

      if ((Has-UsableValue -Object $obj -Name 'completion_gate') -and ($obj.completion_gate -ne 'return_packet_written_and_accepted')) {
        Add-Message -Bucket $errors -Message ("completion_gate 必须为 return_packet_written_and_accepted: {0}" -f $_.FullName)
      }

      if ((Has-UsableValue -Object $obj -Name 'state_owner') -and ($obj.state_owner -ne 'main-coordinator')) {
        Add-Message -Bucket $errors -Message ("state_owner 必须为 main-coordinator: {0}" -f $_.FullName)
      }

      if ((Has-UsableValue -Object $obj -Name 'return_packet_required') -and ($obj.return_packet_required -ne $true)) {
        Add-Message -Bucket $errors -Message ("return_packet_required 必须为 true: {0}" -f $_.FullName)
      }

      if ((-not (Has-UsableValue -Object $obj -Name 'expected_written_by')) -and ((Get-ExpectedWrittenByPatterns -WorkOrder $obj).Count -eq 0)) {
        Add-Message -Bucket $errors -Message ("work_order 缺少可校验的作者身份合同（expected_written_by / expected_written_by_patterns）: {0}" -f $_.FullName)
      }

      $returnPacketResult = Get-ReturnPacketLoadResult -RepoRoot $RepoRoot -WorkOrder $obj -TaskId $TaskId -SourcePath $_.FullName
      foreach ($returnPacketError in @($returnPacketResult.errors)) {
        Add-Message -Bucket $errors -Message ([string]$returnPacketError)
      }

      if (Has-UsableValue -Object $obj -Name 'return_packet_path') {
        if ($null -eq $returnPacketResult.packet) {
          $returnPacketAbsolutePath = if (-not [string]::IsNullOrWhiteSpace([string]$returnPacketResult.absolute_path)) {
            [string]$returnPacketResult.absolute_path
          } else {
            Join-Path $RepoRoot $obj.return_packet_path
          }
          Add-Message -Bucket $errors -Message ("缺少必需 return_packet: {0}" -f $returnPacketAbsolutePath)
        }
      }

      if (Has-UsableValue -Object $obj -Name 'work_order_id') {
        $workOrderIdValue = [string]$obj.work_order_id
        if ($workOrderIndex.ContainsKey($workOrderIdValue)) {
          $firstPath = if ($workOrderPathIndex.ContainsKey($workOrderIdValue)) { [string]$workOrderPathIndex[$workOrderIdValue] } else { '<unknown>' }
          Add-Message -Bucket $errors -Message ("work_order_id 重复: {0}（首次: {1}，重复: {2}）" -f $workOrderIdValue, $firstPath, $_.FullName)
        } else {
          $workOrderIndex[$workOrderIdValue] = $obj
          $workOrderPathIndex[$workOrderIdValue] = $_.FullName
        }
      }

      $workOrderId = if (Has-UsableValue -Object $obj -Name 'work_order_id') { [string]$obj.work_order_id } else { '' }
      $isComplexWorkOrder = Is-ComplexWorkOrder -WorkOrder $obj
      if ($isComplexWorkOrder) {
        if (-not (Has-UsableValue -Object $obj -Name 'dispatch_packet_path')) {
          Add-Message -Bucket $errors -Message ("复杂任务缺少 dispatch_packet_path: {0}" -f $_.FullName)
        } elseif (@($dispatchPacketResult.errors).Count -eq 0 -and $null -eq $dispatchPacket) {
          Add-Message -Bucket $errors -Message ("无法解析 dispatch_packet: {0}" -f $dispatchPacketAbsolutePath)
        } elseif (@($dispatchPacketResult.errors).Count -eq 0) {
          foreach ($dispatchField in @('read_before_write','execution_order','change_spec')) {
            if (-not (Has-NonEmptyCollection -Value $dispatchPacket.$dispatchField)) {
              Add-Message -Bucket $errors -Message ("dispatch_packet.{0} 缺失或为空: {1}" -f $dispatchField, $dispatchPacketAbsolutePath)
            }
          }

          $hasVerificationFocus = Has-NonEmptyCollection -Value $dispatchPacket.verification_focus
          $hasHandoffNotes = Has-NonEmptyCollection -Value $dispatchPacket.handoff_notes
          if (-not $hasVerificationFocus -and -not $hasHandoffNotes) {
            Add-Message -Bucket $errors -Message ("dispatch_packet 缺少 verification_focus/handoff_notes: {0}" -f $dispatchPacketAbsolutePath)
          }

          if ((Has-UsableValue -Object $dispatchPacket -Name 'task_id') -and ($dispatchPacket.task_id -ne $TaskId)) {
            Add-Message -Bucket $errors -Message ("dispatch_packet.task_id 与目录 task_id 不一致: {0}" -f $dispatchPacketAbsolutePath)
          }

          if ((Has-UsableValue -Object $dispatchPacket -Name 'work_order_id') -and -not [string]::IsNullOrWhiteSpace($workOrderId) -and ($dispatchPacket.work_order_id -ne $workOrderId)) {
            Add-Message -Bucket $errors -Message ("dispatch_packet.work_order_id 与 work_order 不一致: {0}" -f $dispatchPacketAbsolutePath)
          }
        }
      }
    }
  } else {
    Add-Message -Bucket $errors -Message ("缺少 work_orders 目录: {0}" -f $workOrderDir)
  }

  if ($workOrdersChecked -eq 0) {
    Add-Message -Bucket $errors -Message ("当前 task run 未找到任何 work_order JSON: {0}" -f $workOrderDir)
  }

  if (Test-Path -LiteralPath $returnPacketDir) {
    Get-ChildItem -Path $returnPacketDir -Filter *.json -File | ForEach-Object {
      $returnPacketsChecked += 1
      $obj = Read-JsonFile -TargetPath $_.FullName
      if ($null -eq $obj) {
        Add-Message -Bucket $errors -Message ("无法解析 return_packet: {0}" -f $_.FullName)
        return
      }

      foreach ($field in @('return_packet_id','task_id','work_order_id','status','summary','written_by','written_role')) {
        if (-not (Has-UsableValue -Object $obj -Name $field)) {
          Add-Message -Bucket $errors -Message ("return_packet 缺少字段 {0}: {1}" -f $field, $_.FullName)
        }
      }

      if ((Has-UsableValue -Object $obj -Name 'task_id') -and ($obj.task_id -ne $TaskId)) {
        Add-Message -Bucket $errors -Message ("return_packet.task_id 与目录 task_id 不一致: {0}" -f $_.FullName)
      }

      if ((Has-UsableValue -Object $obj -Name 'work_order_id') -and $workOrderIndex.ContainsKey($obj.work_order_id)) {
        $workOrder = $workOrderIndex[$obj.work_order_id]
        $requiredFields = New-Object System.Collections.Generic.List[string]
        foreach ($field in (Get-StringArray -Value $workOrder.required_return_fields) + $minimumReturnFields) {
          if (-not [string]::IsNullOrWhiteSpace($field) -and -not $requiredFields.Contains($field)) {
            $requiredFields.Add($field) | Out-Null
          }
        }

        foreach ($field in $requiredFields) {
          if (-not (Has-UsableValue -Object $obj -Name $field)) {
            Add-Message -Bucket $errors -Message ("return_packet 未满足 required_return_fields.{0}: {1}" -f $field, $_.FullName)
          }
        }

        $expectedAuthorship = Get-ExpectedReturnPacketAuthorship -WorkOrder $workOrder
        if ([string]::IsNullOrWhiteSpace($expectedAuthorship.written_role)) {
          Add-Message -Bucket $errors -Message ("work_order 缺少 expected_written_role/role，无法校验 return_packet 作者角色: {0}" -f $_.FullName)
        } elseif ((Has-UsableValue -Object $obj -Name 'written_role') -and ($obj.written_role -ne $expectedAuthorship.written_role)) {
          Add-Message -Bucket $errors -Message ("return_packet.written_role 与 work_order 期望作者角色不一致（期望 `{0}`，实际 `{1}`）: {2}" -f $expectedAuthorship.written_role, [string]$obj.written_role, $_.FullName)
        }

        if ((-not [string]::IsNullOrWhiteSpace($expectedAuthorship.written_by)) -and (Has-UsableValue -Object $obj -Name 'written_by') -and ($obj.written_by -ne $expectedAuthorship.written_by)) {
          Add-Message -Bucket $errors -Message ("return_packet.written_by 与 work_order 期望作者身份不一致（期望 `{0}`，实际 `{1}`）: {2}" -f $expectedAuthorship.written_by, [string]$obj.written_by, $_.FullName)
        } elseif ((Has-UsableValue -Object $obj -Name 'written_by') -and (-not (Test-WrittenByMatchesExpectedIdentity -WorkOrder $workOrder -WrittenBy ([string]$obj.written_by)))) {
          $contractLabel = switch ([string]$expectedAuthorship.written_by_contract_source) {
            'expected_written_by_patterns' { 'expected_written_by_patterns 作者身份模式合同' }
            'derived' { 'expected_written_by_patterns 作者身份模式合同（派生）' }
            default { '作者身份合同' }
          }
          Add-Message -Bucket $errors -Message ("return_packet.written_by 未匹配当前工单的{0}: {1}" -f $contractLabel, $_.FullName)
        }

        if ((Has-UsableValue -Object $obj -Name 'written_by') -and (Test-CoordinatorLikeAuthorshipValue -Value ([string]$obj.written_by))) {
          Add-Message -Bucket $errors -Message ("return_packet.written_by 不得使用协调器身份: {0}" -f $_.FullName)
        }

        if ((Has-UsableValue -Object $obj -Name 'written_role') -and (Test-CoordinatorLikeAuthorshipValue -Value ([string]$obj.written_role))) {
          Add-Message -Bucket $errors -Message ("return_packet.written_role 不得使用协调器身份: {0}" -f $_.FullName)
        }
      } else {
        Add-Message -Bucket $warnings -Message ("找不到对应 work_order 的 return_packet: {0}" -f $_.FullName)
      }
    }
  }
}

$repoDoctor = Join-Path $RepoRoot 'modules\ops_tooling\debug\scripts\repo_doctor.ps1'
$output = @()
$repoDoctorOk = $true
if (Test-Path $repoDoctor) {
  $output = powershell -ExecutionPolicy Bypass -File $repoDoctor -Strict 2>&1
  $repoDoctorOk = $LASTEXITCODE -eq 0
  if (-not $repoDoctorOk) {
    Add-Message -Bucket $errors -Message 'repo_doctor.ps1 -Strict 返回失败。'
  }
} else {
  Add-Message -Bucket $warnings -Message '未找到 repo_doctor.ps1，已跳过 repo_doctor 严格校验。'
}

$ok = ($errors.Count -eq 0) -and $repoDoctorOk
$payload = [ordered]@{
  task_id = $TaskId
  ok = $ok
  repo_root = $RepoRoot
  validator = 'validate-control-plane.ps1'
  plans_checked = $plansChecked
  work_orders_checked = $workOrdersChecked
  return_packets_checked = $returnPacketsChecked
  errors = $errors.ToArray()
  warnings = $warnings.ToArray()
  output = ($output -join "`n")
}
if ($Json) { $payload | ConvertTo-Json -Depth 6 } else { $payload }
if (-not $ok) { $host.SetShouldExit(1) }
