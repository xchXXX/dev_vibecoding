param(
  [string]$RepoRoot = (Get-Location).Path,
  [string]$Path = '',
  [string]$RoleSourcePath = '',
  [string]$RoleMapPath = '',
  [switch]$IncludeRoleContext,
  [switch]$Json,
  [switch]$WriteBack
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot 'control-plane-common.ps1')

if ([string]::IsNullOrWhiteSpace($Path)) {
  throw 'compile-dispatch-message.ps1 requires -Path.'
}

$targets = New-Object System.Collections.Generic.List[string]
if (Test-Path -LiteralPath $Path) {
  $item = Get-Item -LiteralPath $Path
  if ($item.PSIsContainer) {
    Get-ChildItem -LiteralPath $item.FullName -Filter *.json -File | ForEach-Object { $targets.Add($_.FullName) | Out-Null }
  } else {
    $targets.Add($item.FullName) | Out-Null
  }
} else {
  throw ("Path not found: {0}" -f $Path)
}

$results = New-Object System.Collections.Generic.List[object]
$updated = New-Object System.Collections.Generic.List[string]
$errors = New-Object System.Collections.Generic.List[string]
$hadErrors = $false

if ($targets.Count -eq 0) {
  $errors.Add(("compile-dispatch-message 未找到任何 work_order JSON: {0}" -f $Path)) | Out-Null
  $hadErrors = $true
}

foreach ($target in $targets) {
  $workOrder = Read-JsonFile -TargetPath $target
  if ($null -eq $workOrder) {
    $results.Add([ordered]@{ path = $target; ok = $false; errors = @('无法解析 work_order。') }) | Out-Null
    $hadErrors = $true
    continue
  }

  if (-not [string]::IsNullOrWhiteSpace($RoleSourcePath)) {
    if (-not (Has-Property -Object $workOrder -Name 'role_source_path')) {
      $workOrder | Add-Member -NotePropertyName 'role_source_path' -NotePropertyValue $RoleSourcePath
    } else {
      $workOrder.role_source_path = $RoleSourcePath
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($RoleMapPath)) {
    if (-not (Has-Property -Object $workOrder -Name 'role_map_path')) {
      $workOrder | Add-Member -NotePropertyName 'role_map_path' -NotePropertyValue $RoleMapPath
    } else {
      $workOrder.role_map_path = $RoleMapPath
    }
  }

  $dispatchPacketResult = Get-DispatchPacketLoadResult -RepoRoot $RepoRoot -WorkOrder $workOrder -SourcePath $target
  $effectiveIncludeRoleContext = $IncludeRoleContext -or (Should-IncludeRoleContext -WorkOrder $workOrder) -or (-not [string]::IsNullOrWhiteSpace($RoleSourcePath)) -or (-not [string]::IsNullOrWhiteSpace($RoleMapPath))
  $result = if (@($dispatchPacketResult.errors).Count -gt 0) {
    [ordered]@{
      ok = $false
      errors = @($dispatchPacketResult.errors)
      text = ''
    }
  } else {
    Get-DispatchMessageCompilation -WorkOrder $workOrder -DispatchPacket $dispatchPacketResult.packet -IncludeRoleContext:$effectiveIncludeRoleContext
  }
  $payload = [ordered]@{
    path = $target
    ok = $result.ok
    errors = $result.errors
  }

  if ($result.ok) {
    $payload.dispatch_message_raw = $result.text
    if ($WriteBack) {
      if (-not (Has-Property -Object $workOrder -Name 'dispatch_message_raw')) {
        $workOrder | Add-Member -NotePropertyName 'dispatch_message_raw' -NotePropertyValue $result.text
      } else {
        $workOrder.dispatch_message_raw = $result.text
      }
      $workOrder | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $target -Encoding UTF8
      $updated.Add($target) | Out-Null
    }
  } else {
    $hadErrors = $true
  }

  $results.Add($payload) | Out-Null
}

$response = [ordered]@{
  results = $results.ToArray()
  updated = $updated.ToArray()
  count = $updated.Count
  target_count = $targets.Count
  errors = $errors.ToArray()
}

if ($Json) {
  $response | ConvertTo-Json -Depth 10
} else {
  $response
}

if ($hadErrors) {
  $host.SetShouldExit(1)
}


