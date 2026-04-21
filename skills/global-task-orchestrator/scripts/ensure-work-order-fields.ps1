param(
  [string]$RepoRoot = (Get-Location).Path,
  [string]$Path = '',
  [string]$TaskId = '',
  [switch]$Json
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot 'control-plane-common.ps1')

$targets = New-Object System.Collections.Generic.List[string]
$resolutionErrors = New-Object System.Collections.Generic.List[string]
if ($Path) {
  if (Test-Path -LiteralPath $Path) {
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
      Get-ChildItem -Path $item.FullName -Filter *.json -File | ForEach-Object { $targets.Add($_.FullName) | Out-Null }
    } else {
      $targets.Add($item.FullName) | Out-Null
    }
  } else {
    $resolutionErrors.Add(("hydrate 目标路径不存在: {0}" -f $Path)) | Out-Null
  }
} elseif ($TaskId) {
  $woDir = Join-Path $RepoRoot ("docs/ai/runs/{0}/work_orders" -f $TaskId)
  if (Test-Path -LiteralPath $woDir) {
    Get-ChildItem -Path $woDir -Filter *.json -File | ForEach-Object { $targets.Add($_.FullName) | Out-Null }
  } else {
    $resolutionErrors.Add(("hydrate 目标 task run 缺少 work_orders 目录: {0}" -f $woDir)) | Out-Null
  }
} else {
  $resolutionErrors.Add('hydrate 必须提供 -Path 或 -TaskId。') | Out-Null
}

if (($targets.Count -eq 0) -and ($resolutionErrors.Count -eq 0)) {
  if ($Path) {
    $resolutionErrors.Add(("hydrate 未找到任何 work_order JSON: {0}" -f $Path)) | Out-Null
  } elseif ($TaskId) {
    $resolutionErrors.Add(("hydrate 目标 task run 下未找到任何 work_order JSON: docs/ai/runs/{0}/work_orders" -f $TaskId)) | Out-Null
  }
}

$defaultReturnFields = Get-MinimumRequiredReturnFields
$updated = New-Object System.Collections.Generic.List[string]
$compileFailures = New-Object System.Collections.Generic.List[object]

foreach ($target in $targets) {
  try {
    $obj = Get-Content -LiteralPath $target -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    $compileFailures.Add([ordered]@{ path = $target; errors = @('无法解析 work_order。') }) | Out-Null
    continue
  }

  $changed = $false
  $resolvedTaskId = Get-WorkOrderTaskId -WorkOrder $obj -FallbackTaskId $TaskId -SourcePath $target

  if ($resolvedTaskId -and -not (Has-Property -Object $obj -Name 'task_id')) {
    $obj | Add-Member -NotePropertyName 'task_id' -NotePropertyValue $resolvedTaskId
    $changed = $true
  }

  if ((-not (Has-Property -Object $obj -Name 'return_packet_required')) -or ($obj.return_packet_required -ne $true)) {
    if (Has-Property -Object $obj -Name 'return_packet_required') {
      $obj.return_packet_required = $true
    } else {
      $obj | Add-Member -NotePropertyName 'return_packet_required' -NotePropertyValue $true
    }
    $changed = $true
  }

  if (-not (Has-Value -Object $obj -Name 'completion_gate')) {
    if (Has-Property -Object $obj -Name 'completion_gate') {
      $obj.completion_gate = 'return_packet_written_and_accepted'
    } else {
      $obj | Add-Member -NotePropertyName 'completion_gate' -NotePropertyValue 'return_packet_written_and_accepted'
    }
    $changed = $true
  }

  if (-not (Has-Value -Object $obj -Name 'state_owner')) {
    if (Has-Property -Object $obj -Name 'state_owner') {
      $obj.state_owner = 'main-coordinator'
    } else {
      $obj | Add-Member -NotePropertyName 'state_owner' -NotePropertyValue 'main-coordinator'
    }
    $changed = $true
  }

  if (-not (Has-Property -Object $obj -Name 'required_return_fields')) {
    $obj | Add-Member -NotePropertyName 'required_return_fields' -NotePropertyValue $defaultReturnFields
    $changed = $true
  } else {
    $currentFields = Get-StringArray -Value $obj.required_return_fields
    if (-not (Test-ContainsAllFields -Actual $currentFields -Expected $defaultReturnFields)) {
      $mergedFields = New-Object System.Collections.Generic.List[string]
      foreach ($field in $currentFields + $defaultReturnFields) {
        if (-not [string]::IsNullOrWhiteSpace($field) -and -not $mergedFields.Contains($field)) {
          $mergedFields.Add($field) | Out-Null
        }
      }
      $obj.required_return_fields = $mergedFields.ToArray()
      $changed = $true
    }
  }

  if ((Test-ImplicitlyComplexWorkOrder -WorkOrder $obj) -or (Test-DispatchPacketRequired -WorkOrder $obj)) {
    if ((-not (Has-Property -Object $obj -Name 'dispatch_packet_required')) -or ($obj.dispatch_packet_required -ne $true)) {
      if (Has-Property -Object $obj -Name 'dispatch_packet_required') {
        $obj.dispatch_packet_required = $true
      } else {
        $obj | Add-Member -NotePropertyName 'dispatch_packet_required' -NotePropertyValue $true
      }
      $changed = $true
    }
  }

  if (-not (Has-Value -Object $obj -Name 'return_packet_path') -and $resolvedTaskId -and (Has-UsableValue -Object $obj -Name 'work_order_id')) {
    $returnPacketId = Get-ReturnPacketId -WorkOrderId $obj.work_order_id
    $returnPacketPath = "docs/ai/runs/{0}/return_packets/{1}.json" -f $resolvedTaskId, $returnPacketId
    if (Has-Property -Object $obj -Name 'return_packet_path') {
      $obj.return_packet_path = $returnPacketPath
    } else {
      $obj | Add-Member -NotePropertyName 'return_packet_path' -NotePropertyValue $returnPacketPath
    }
    $changed = $true
  }

  $expectedWrittenRole = Get-DefaultExpectedWrittenRole -WorkOrder $obj
  if ((-not (Has-UsableValue -Object $obj -Name 'expected_written_role')) -and (-not [string]::IsNullOrWhiteSpace($expectedWrittenRole))) {
    if (Has-Property -Object $obj -Name 'expected_written_role') {
      $obj.expected_written_role = $expectedWrittenRole
    } else {
      $obj | Add-Member -NotePropertyName 'expected_written_role' -NotePropertyValue $expectedWrittenRole
    }
    $changed = $true
  }

  if ((-not (Has-UsableValue -Object $obj -Name 'expected_written_by')) -and ((Get-ExplicitExpectedWrittenByPatterns -WorkOrder $obj).Count -eq 0)) {
    $derivedWrittenByPatterns = Get-DerivedExpectedWrittenByPatterns -WorkOrder $obj
    if ($derivedWrittenByPatterns.Count -gt 0) {
      if (Has-Property -Object $obj -Name 'expected_written_by_patterns') {
        $obj.expected_written_by_patterns = $derivedWrittenByPatterns
      } else {
        $obj | Add-Member -NotePropertyName 'expected_written_by_patterns' -NotePropertyValue $derivedWrittenByPatterns
      }
      $changed = $true
    }
  }

  $dispatchPacketResult = Get-DispatchPacketLoadResult -RepoRoot $RepoRoot -WorkOrder $obj -TaskId $resolvedTaskId -SourcePath $target
  $compilationErrors = New-Object System.Collections.Generic.List[string]
  foreach ($dispatchPacketError in @($dispatchPacketResult.errors)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$dispatchPacketError)) {
      $compilationErrors.Add([string]$dispatchPacketError) | Out-Null
    }
  }

  if ($compilationErrors.Count -eq 0) {
    $compilation = Get-DispatchMessageCompilation -WorkOrder $obj -DispatchPacket $dispatchPacketResult.packet -IncludeRoleContext:(Should-IncludeRoleContext -WorkOrder $obj)
    if ($compilation.ok) {
      $currentDispatchMessage = if (Has-UsableValue -Object $obj -Name 'dispatch_message_raw') { [string]$obj.dispatch_message_raw } else { '' }
      if ((-not (Has-Property -Object $obj -Name 'dispatch_message_raw')) -or ((Normalize-DispatchMessage -Text $currentDispatchMessage) -ne (Normalize-DispatchMessage -Text $compilation.text))) {
        if (Has-Property -Object $obj -Name 'dispatch_message_raw') {
          $obj.dispatch_message_raw = $compilation.text
        } else {
          $obj | Add-Member -NotePropertyName 'dispatch_message_raw' -NotePropertyValue $compilation.text
        }
        $changed = $true
      }
    } else {
      $compileFailures.Add([ordered]@{ path = $target; errors = $compilation.errors }) | Out-Null
    }
  } else {
    $compileFailures.Add([ordered]@{ path = $target; errors = $compilationErrors.ToArray() }) | Out-Null
  }

  if ($changed) {
    $obj | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $target -Encoding UTF8
    $updated.Add($target) | Out-Null
  }
}

$payload = [ordered]@{
  ok = (($compileFailures.Count -eq 0) -and ($resolutionErrors.Count -eq 0))
  target_count = $targets.Count
  updated = $updated.ToArray()
  count = $updated.Count
  errors = $resolutionErrors.ToArray()
  compile_failures = $compileFailures.ToArray()
}
if ($Json) { $payload | ConvertTo-Json -Depth 8 } else { $payload }
if (($compileFailures.Count -gt 0) -or ($resolutionErrors.Count -gt 0)) { $host.SetShouldExit(1) }
