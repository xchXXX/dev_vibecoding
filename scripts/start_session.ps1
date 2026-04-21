param(
  [Parameter(Mandatory = $true)]
  [string]$TaskId,
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  param([string]$InputRoot)
  if ($InputRoot -ne "") {
    return (Resolve-Path $InputRoot).Path
  }
  $scriptDir = $PSScriptRoot
  return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Resolve-TemplateDir {
  param([string]$Root)
  foreach ($candidate in @(
    (Join-Path $Root "templates"),
    (Join-Path $Root "config/ai/templates")
  )) {
    if (Test-Path $candidate) {
      return $candidate
    }
  }
  return (Join-Path $Root "templates")
}

function Get-PlanId {
  param([string]$PlanPath)
  if (-not (Test-Path $PlanPath)) {
    return "<plan-id>"
  }
  try {
    $payload = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -ne $payload.plan_id -and "$($payload.plan_id)".Trim() -ne "") {
      return "$($payload.plan_id)"
    }
  } catch {
  }
  return "<plan-id>"
}

function Render-Template {
  param(
    [string]$Content,
    [string]$TaskId,
    [string]$PlanId,
    [string]$NowStr,
    [string]$Owner
  )
  $rendered = $Content.Replace("<task-id>", $TaskId)
  $rendered = $rendered.Replace("<plan-id>", $PlanId)
  $rendered = $rendered.Replace("2026-03-27 16:00:00", $NowStr)
  $rendered = $rendered.Replace("main-coordinator", $Owner)
  return $rendered
}

$root = Resolve-RepoRoot -InputRoot $RepoRoot
$runDir = Join-Path $root ("docs/ai/runs/{0}" -f $TaskId)
$planPath = Join-Path $runDir "plan.json"
$orchestrationPath = Join-Path $runDir "orchestration_log.md"
$sessionDir = Join-Path $root (".ai/session/{0}" -f $TaskId)

$templateMap = [ordered]@{
  "task_plan.md" = "task_plan.session.example.md"
  "findings.md" = "findings.session.example.md"
  "progress.md" = "progress.session.example.md"
}
$templateDir = Resolve-TemplateDir -Root $root

if (-not (Test-Path $templateDir)) {
  throw "模板目录不存在: $templateDir"
}

$warnings = New-Object System.Collections.Generic.List[string]
if (-not (Test-Path $runDir)) {
  $warnings.Add("run 目录不存在: $runDir") | Out-Null
}
if (-not (Test-Path $planPath)) {
  $warnings.Add("plan.json 不存在: $planPath") | Out-Null
}
if (-not (Test-Path $orchestrationPath)) {
  $warnings.Add("orchestration_log.md 不存在: $orchestrationPath") | Out-Null
}

New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null

$planId = Get-PlanId -PlanPath $planPath
$owner = "$env:USERNAME"
if ($owner -eq "") { $owner = "main-coordinator" }
$nowStr = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$created = New-Object System.Collections.Generic.List[string]
$existing = New-Object System.Collections.Generic.List[string]
$missingTemplates = New-Object System.Collections.Generic.List[string]

foreach ($targetName in $templateMap.Keys) {
  $targetPath = Join-Path $sessionDir $targetName
  if (Test-Path $targetPath) {
    $existing.Add($targetPath.Replace($root + "\", "").Replace("\", "/")) | Out-Null
    continue
  }

  $templateName = $templateMap[$targetName]
  $templatePath = Join-Path $templateDir $templateName
  if (-not (Test-Path $templatePath)) {
    $missingTemplates.Add($templatePath.Replace($root + "\", "").Replace("\", "/")) | Out-Null
    continue
  }

  $raw = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8
  $rendered = Render-Template -Content $raw -TaskId $TaskId -PlanId $planId -NowStr $nowStr -Owner $owner
  Set-Content -LiteralPath $targetPath -Value $rendered -Encoding UTF8
  $created.Add($targetPath.Replace($root + "\", "").Replace("\", "/")) | Out-Null
}

Write-Output "start_session bootstrap"
Write-Output ("task_id: {0}" -f $TaskId)
Write-Output ("repo_root: {0}" -f $root)
Write-Output ("plan_id: {0}" -f $planId)
Write-Output ("session_dir: {0}" -f $sessionDir.Replace($root + "\", "").Replace("\", "/"))

if ($created.Count -gt 0) {
  Write-Output "created_files:"
  foreach ($item in $created) { Write-Output ("  - {0}" -f $item) }
} else {
  Write-Output "created_files: []"
}

if ($existing.Count -gt 0) {
  Write-Output "existing_files:"
  foreach ($item in $existing) { Write-Output ("  - {0}" -f $item) }
} else {
  Write-Output "existing_files: []"
}

if ($missingTemplates.Count -gt 0) {
  Write-Output "missing_templates:"
  foreach ($item in $missingTemplates) { Write-Output ("  - {0}" -f $item) }
} else {
  Write-Output "missing_templates: []"
}

if ($warnings.Count -gt 0) {
  Write-Output "warnings:"
  foreach ($item in $warnings) { Write-Output ("  - {0}" -f $item) }
} else {
  Write-Output "warnings: []"
}

Write-Output "next_steps:"
Write-Output "  1) 补齐 task_plan.md 的 step 与验收"
Write-Output "  2) 写入 findings.md 的首批证据条目"
Write-Output "  3) 追加 progress.md 事件并执行最小 control-plane validate"

if ($missingTemplates.Count -gt 0) {
  exit 1
}

exit 0
