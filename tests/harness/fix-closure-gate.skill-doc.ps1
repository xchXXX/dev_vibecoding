$ErrorActionPreference = 'Stop'

function Assert-True {
  param(
    [bool]$Condition,
    [string]$Message
  )
  if (-not $Condition) {
    throw $Message
  }
}

function Assert-Match {
  param(
    [string]$Value,
    [string]$Pattern,
    [string]$Message
  )
  if ($Value -notmatch $Pattern) {
    throw $Message
  }
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$skillRoot = Join-Path $repoRoot 'skills\fix-closure-gate'
$skillPath = Join-Path $skillRoot 'SKILL.md'
$openAiYamlPath = Join-Path $skillRoot 'agents\openai.yaml'

Assert-True (Test-Path -LiteralPath $skillPath) 'SKILL.md must exist for fix-closure-gate'
Assert-True (Test-Path -LiteralPath $openAiYamlPath) 'agents/openai.yaml must exist for fix-closure-gate'

$skillContent = Get-Content -LiteralPath $skillPath -Raw -Encoding UTF8
$frontmatterMatch = [regex]::Match($skillContent, '(?s)\A---\r?\n(?<frontmatter>.*?)\r?\n---\r?\n')
Assert-True $frontmatterMatch.Success 'SKILL.md must start with YAML frontmatter'

$frontmatter = $frontmatterMatch.Groups['frontmatter'].Value
$descriptionMatch = [regex]::Match($frontmatter, '(?m)^description:\s*(?<value>.+)$')
Assert-True $descriptionMatch.Success 'SKILL.md frontmatter must contain a single-line description'
$description = $descriptionMatch.Groups['value'].Value.Trim()

Assert-True ($description.Length -ge 120) 'description should be detailed enough to drive auto-triggering for fix-closure-gate'
Assert-Match -Value $description -Pattern 'bugfix|缺陷|修复|fallback|catch' -Message 'description must mention representative repair scenarios'
Assert-Match -Value $description -Pattern 'integration|端到端|高成本|review|送审|复审' -Message 'description must mention high-cost or review-gated verification contexts'
Assert-Match -Value $description -Pattern 'minimal_repro' -Message 'description must mention minimal_repro'
Assert-Match -Value $description -Pattern 'hit_proof' -Message 'description must mention hit_proof'
Assert-Match -Value $description -Pattern 'diagnostic_checks' -Message 'description must mention diagnostic_checks'
Assert-Match -Value $description -Pattern 'acceptance_checks' -Message 'description must mention acceptance_checks'
Assert-Match -Value $description -Pattern 'non_goals' -Message 'description must mention non_goals'
Assert-Match -Value $description -Pattern 'review_evidence' -Message 'description must mention review_evidence'
Assert-Match -Value $description -Pattern '跳过|可跳过|skip' -Message 'description must mention skip conditions'

Assert-Match -Value $skillContent -Pattern '## 职责' -Message 'SKILL.md must include a responsibilities section'
Assert-Match -Value $skillContent -Pattern '## 非职责' -Message 'SKILL.md must include a non-responsibilities section'
Assert-Match -Value $skillContent -Pattern '## 触发条件' -Message 'SKILL.md must include trigger conditions'
Assert-Match -Value $skillContent -Pattern '## 跳过条件' -Message 'SKILL.md must include skip conditions'
Assert-Match -Value $skillContent -Pattern '## 最小输入' -Message 'SKILL.md must include minimal input requirements'
Assert-Match -Value $skillContent -Pattern '## 最小输出' -Message 'SKILL.md must include minimal output requirements'
Assert-Match -Value $skillContent -Pattern '## Diagnostic Checks vs Acceptance Checks' -Message 'SKILL.md must distinguish diagnostic and acceptance checks'
Assert-Match -Value $skillContent -Pattern '## Review Evidence 最小槽位' -Message 'SKILL.md must define review evidence slots'
Assert-Match -Value $skillContent -Pattern '## 最小工作流' -Message 'SKILL.md must include a minimal workflow'
Assert-Match -Value $skillContent -Pattern '`minimal_repro`' -Message 'SKILL.md must document minimal_repro'
Assert-Match -Value $skillContent -Pattern '`hit_proof`' -Message 'SKILL.md must document hit_proof'
Assert-Match -Value $skillContent -Pattern '`diagnostic_checks`' -Message 'SKILL.md must document diagnostic_checks'
Assert-Match -Value $skillContent -Pattern '`acceptance_checks`' -Message 'SKILL.md must document acceptance_checks'
Assert-Match -Value $skillContent -Pattern '`non_goals`' -Message 'SKILL.md must document non_goals'
Assert-Match -Value $skillContent -Pattern '`review_evidence`' -Message 'SKILL.md must document review_evidence'
Assert-Match -Value $skillContent -Pattern '根层 `review_evidence` 只列' -Message 'SKILL.md must define root review_evidence as slot names only'
Assert-Match -Value $skillContent -Pattern 'subtask\.result\.review_evidence\.<slot>' -Message 'SKILL.md must route collected evidence to subtask.result.review_evidence.<slot>'
Assert-Match -Value $skillContent -Pattern 'repro_before_fix' -Message 'SKILL.md must define the repro_before_fix review evidence slot'
Assert-Match -Value $skillContent -Pattern 'pass_after_fix' -Message 'SKILL.md must define the pass_after_fix review evidence slot'
Assert-Match -Value $skillContent -Pattern 'hit_proof_observed' -Message 'SKILL.md must define the hit_proof_observed review evidence slot'
Assert-Match -Value $skillContent -Pattern 'relevant_regression_ok' -Message 'SKILL.md must define the relevant_regression_ok review evidence slot'
Assert-Match -Value $skillContent -Pattern 'pre-dev-benchmark' -Message 'SKILL.md must define the boundary with pre-dev-benchmark'
Assert-Match -Value $skillContent -Pattern 'global-task-orchestrator' -Message 'SKILL.md must define the boundary with global-task-orchestrator'

$openAiYaml = Get-Content -LiteralPath $openAiYamlPath -Raw -Encoding UTF8
Assert-Match -Value $openAiYaml -Pattern 'display_name:\s*"修复闭环闸门"' -Message 'openai.yaml must expose the expected display name'
Assert-Match -Value $openAiYaml -Pattern 'short_description:\s*".*命中证明.*诊断检查.*复审证据.*"' -Message 'openai.yaml short_description must describe the closure-gate contract'
Assert-Match -Value $openAiYaml -Pattern 'default_prompt:\s*".*\$fix-closure-gate.*bug.*fallback/catch.*`minimal_repro`.*`hit_proof`.*`diagnostic_checks`.*`acceptance_checks`.*`non_goals`.*`review_evidence`.*pure feature.*copy/style/config.*already frozen.*"' -Message 'openai.yaml default_prompt must cover triggering scenarios, required fields, and skip conditions'
Assert-Match -Value $openAiYaml -Pattern 'root-level `review_evidence` slot names' -Message 'openai.yaml default_prompt must describe root review_evidence as slot names'
Assert-Match -Value $openAiYaml -Pattern 'subtask\.result\.review_evidence\.<slot>' -Message 'openai.yaml default_prompt must route actual evidence to subtask.result.review_evidence.<slot>'

Write-Host 'PASS: fix-closure-gate skill metadata and documentation contract'
