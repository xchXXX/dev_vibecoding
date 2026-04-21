param(
  [string]$Path = '',
  [string]$TaskId = '',
  [switch]$Json
)

function Get-TaskIdFromPath {
  param([string]$TargetPath)
  if ($TargetPath -match 'docs[\\/]ai[\\/]runs[\\/]([^\\/]+)[\\/]') {
    return $Matches[1]
  }
  return ''
}

function Get-ReturnPacketId {
  param([string]$WorkOrderId, [string]$FallbackFileName)
  if (-not [string]::IsNullOrWhiteSpace($WorkOrderId)) {
    if ($WorkOrderId -match '^WO-') {
      return ($WorkOrderId -replace '^WO-', 'RP-')
    }
    return ('RP-' + $WorkOrderId)
  }
  return [System.IO.Path]::GetFileNameWithoutExtension($FallbackFileName)
}

function Has-Property {
  param($Object, [string]$Name)
  return $null -ne $Object.PSObject.Properties[$Name]
}

$targets = New-Object System.Collections.Generic.List[string]
if ($Path) {
  if (Test-Path $Path) {
    $item = Get-Item $Path
    if ($item.PSIsContainer) {
      Get-ChildItem -Path $item.FullName -Filter *.json -File | ForEach-Object { $targets.Add($_.FullName) | Out-Null }
    } else {
      $targets.Add($item.FullName) | Out-Null
    }
  }
}

$updated = New-Object System.Collections.Generic.List[string]
foreach ($target in $targets) {
  try {
    $obj = Get-Content -LiteralPath $target -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    continue
  }

  $changed = $false
  $resolvedTaskId = if ($TaskId) {
    $TaskId
  } elseif ((Has-Property -Object $obj -Name 'task_id') -and $obj.task_id) {
    $obj.task_id
  } else {
    Get-TaskIdFromPath -TargetPath $target
  }

  if (-not (Has-Property -Object $obj -Name 'return_packet_id')) {
    $obj | Add-Member -NotePropertyName 'return_packet_id' -NotePropertyValue (Get-ReturnPacketId -WorkOrderId $obj.work_order_id -FallbackFileName $target)
    $changed = $true
  }

  if ($resolvedTaskId -and -not (Has-Property -Object $obj -Name 'task_id')) {
    $obj | Add-Member -NotePropertyName 'task_id' -NotePropertyValue $resolvedTaskId
    $changed = $true
  }

  foreach ($field in @('changed_files', 'verification', 'risks', 'next_actions')) {
    if (-not (Has-Property -Object $obj -Name $field)) {
      $obj | Add-Member -NotePropertyName $field -NotePropertyValue @()
      $changed = $true
    }
  }

  foreach ($field in @('planned_files_not_changed', 'verification_commands', 'deviations_from_dispatch', 'blocked_by', 'follow_up_needed')) {
    if (-not (Has-Property -Object $obj -Name $field)) {
      $obj | Add-Member -NotePropertyName $field -NotePropertyValue @()
      $changed = $true
    }
  }

  if (-not (Has-Property -Object $obj -Name 'verification_result')) {
    $obj | Add-Member -NotePropertyName 'verification_result' -NotePropertyValue ''
    $changed = $true
  }

  if (-not (Has-Property -Object $obj -Name 'written_by')) {
    $obj | Add-Member -NotePropertyName 'written_by' -NotePropertyValue 'executor-self-report'
    $changed = $true
  }

  if (-not (Has-Property -Object $obj -Name 'written_role')) {
    $obj | Add-Member -NotePropertyName 'written_role' -NotePropertyValue 'subagent-executor'
    $changed = $true
  }

  if ($changed) {
    $obj | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $target -Encoding UTF8
    $updated.Add($target) | Out-Null
  }
}

$payload = [ordered]@{
  updated = $updated.ToArray()
  count = $updated.Count
}
if ($Json) { $payload | ConvertTo-Json -Depth 6 } else { $payload }
