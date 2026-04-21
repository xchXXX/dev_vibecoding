param(
  [string]$RepoRoot = (Get-Location).Path,
  [Parameter(Mandatory = $true)]
  [string]$Topic,
  [string]$Prefix = '',
  [switch]$Json
)

$slug = $Topic.ToLower() -replace '[^a-z0-9]+', '-' -replace '^-+', '' -replace '-+$', ''
if ([string]::IsNullOrWhiteSpace($slug)) { $slug = 'task' }
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$chars = 'abcdefghijklmnopqrstuvwxyz0123456789'.ToCharArray()
$rand = -join (1..4 | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
$base = if ($Prefix) { "$Prefix-$slug-$timestamp-$rand" } else { "$slug-$timestamp-$rand" }
$taskId = $base
$runDir = Join-Path $RepoRoot ("docs/ai/runs/{0}" -f $taskId)
$sessionDir = Join-Path $RepoRoot (".ai/session/{0}" -f $taskId)
$payload = [ordered]@{
  task_id = $taskId
  slug = $slug
  run_dir = $runDir
  session_dir = $sessionDir
}
if ($Json) { $payload | ConvertTo-Json -Depth 6 } else { $payload }
