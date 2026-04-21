param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('new-task','bootstrap','hydrate','hydrate-return','validate','inspect')]
  [string]$Action,
  [string]$RepoRoot = (Get-Location).Path,
  [string]$Topic = '',
  [string]$TaskId = '',
  [string]$PlanId = '',
  [string]$SourcePlanDoc = '',
  [string]$SourcePlanJson = '',
  [string]$Path = '',
  [switch]$Json
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

switch ($Action) {
  'new-task' {
    & (Join-Path $scriptRoot 'allocate-task-id.ps1') -RepoRoot $RepoRoot -Topic $Topic -Json:$Json
  }
  'bootstrap' {
    & (Join-Path $scriptRoot 'bootstrap-task.ps1') -RepoRoot $RepoRoot -TaskId $TaskId -PlanId $PlanId -SourcePlanDoc $SourcePlanDoc -SourcePlanJson $SourcePlanJson -Json:$Json
  }
  'hydrate' {
    & (Join-Path $scriptRoot 'ensure-work-order-fields.ps1') -RepoRoot $RepoRoot -Path $Path -TaskId $TaskId -Json:$Json
  }
  'hydrate-return' {
    & (Join-Path $scriptRoot 'ensure-return-packet-fields.ps1') -Path $Path -TaskId $TaskId -Json:$Json
  }
  'validate' {
    & (Join-Path $scriptRoot 'validate-control-plane.ps1') -RepoRoot $RepoRoot -TaskId $TaskId -Json:$Json
  }
  'inspect' {
    $runDir = Join-Path $RepoRoot ("docs/ai/runs/{0}" -f $TaskId)
    $sessionDir = Join-Path $RepoRoot (".ai/session/{0}" -f $TaskId)
    $workOrderDir = Join-Path $runDir 'work_orders'
    $returnPacketDir = Join-Path $runDir 'return_packets'
    $payload = [ordered]@{
      task_id = $TaskId
      run_exists = (Test-Path $runDir)
      session_exists = (Test-Path $sessionDir)
      run_dir = $runDir
      session_dir = $sessionDir
      work_order_count = if (Test-Path $workOrderDir) { (Get-ChildItem -Path $workOrderDir -Filter *.json -File).Count } else { 0 }
      return_packet_count = if (Test-Path $returnPacketDir) { (Get-ChildItem -Path $returnPacketDir -Filter *.json -File).Count } else { 0 }
    }
    if ($Json) { $payload | ConvertTo-Json -Depth 6 } else { $payload }
  }
}
