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
$skillRoot = Join-Path $repoRoot 'skills\command-failure-memory'
$skillPath = Join-Path $skillRoot 'SKILL.md'
$openAiYamlPath = Join-Path $skillRoot 'agents\openai.yaml'
$cmdPath = Join-Path $skillRoot 'scripts\command-failure-memory.cmd'
$pyPath = Join-Path $skillRoot 'scripts\command-failure-memory.py'
$ps1Path = Join-Path $skillRoot 'scripts\command-failure-memory.ps1'

Assert-True (Test-Path -LiteralPath $skillPath) 'SKILL.md must exist for command-failure-memory'
Assert-True (Test-Path -LiteralPath $openAiYamlPath) 'agents/openai.yaml must exist for command-failure-memory'
Assert-True (Test-Path -LiteralPath $cmdPath) 'command-failure-memory.cmd must exist for command-failure-memory'
Assert-True (Test-Path -LiteralPath $pyPath) 'command-failure-memory.py must exist for command-failure-memory'
Assert-True (Test-Path -LiteralPath $ps1Path) 'command-failure-memory.ps1 must exist for command-failure-memory'

$skillContent = Get-Content -LiteralPath $skillPath -Raw -Encoding UTF8
$frontmatterMatch = [regex]::Match($skillContent, '(?s)\A---\r?\n(?<frontmatter>.*?)\r?\n---\r?\n')
Assert-True $frontmatterMatch.Success 'SKILL.md must start with YAML frontmatter'

$frontmatter = $frontmatterMatch.Groups['frontmatter'].Value
$descriptionMatch = [regex]::Match($frontmatter, '(?m)^description:\s*(?<value>.+)$')
Assert-True $descriptionMatch.Success 'SKILL.md frontmatter must contain a single-line description'
$description = $descriptionMatch.Groups['value'].Value.Trim()

Assert-True ($description.Length -ge 160) 'description should be detailed enough to drive auto-triggering for command failures'
Assert-Match -Value $description -Pattern 'shell|terminal|PowerShell|test|build|install|script|toolchain|package manager' -Message 'description must mention representative command execution contexts'
Assert-Match -Value $description -Pattern 'non-zero|退出|timeout|超时|未成功完成|failed|failure' -Message 'description must key off execution-failure signals instead of only concrete error strings'
Assert-Match -Value $description -Pattern 'retry|rerun|重试|重跑|等价命令' -Message 'description must mention retry/rerun context'
Assert-Match -Value $description -Pattern 'even if the user did not mention|automatic' -Message 'description must explicitly require automatic use without explicit user mention'
Assert-Match -Value $description -Pattern 'record-failure' -Message 'description must mention record-failure'
Assert-Match -Value $description -Pattern 'query-before-retry' -Message 'description must mention query-before-retry'
Assert-Match -Value $description -Pattern 'record-success' -Message 'description must mention record-success'

Assert-Match -Value $skillContent -Pattern '## Trigger Checklist /' -Message 'SKILL.md must include an explicit trigger checklist section'
Assert-Match -Value $skillContent -Pattern '## Usage /' -Message 'SKILL.md must include a usage section'
Assert-Match -Value $skillContent -Pattern '## Standard Loop /' -Message 'SKILL.md must include the standard failure-memory loop'
Assert-Match -Value $skillContent -Pattern '## Actions /' -Message 'SKILL.md must document the supported actions'
Assert-Match -Value $skillContent -Pattern '\$workspaceRunner = Join-Path \(Get-Location\) ''skills\\command-failure-memory\\scripts\\command-failure-memory\.cmd''' -Message 'SKILL.md must show workspace-local launcher resolution first'
Assert-Match -Value $skillContent -Pattern '\$codexHome = if \(\$env:CODEX_HOME\) \{ \$env:CODEX_HOME \} else \{ Join-Path \$env:USERPROFILE ''.codex'' \}' -Message 'SKILL.md must remain CODEX_HOME-aware when workspace-local launcher is absent'
Assert-Match -Value $skillContent -Pattern '\$runtimeRunner = Join-Path \$codexHome ''skills\\command-failure-memory\\scripts\\command-failure-memory\.cmd''' -Message 'SKILL.md must include the runtime launcher path example'
Assert-Match -Value $skillContent -Pattern '\$fallbackRunner = Join-Path \$env:USERPROFILE ''.codex\\skills\\command-failure-memory\\scripts\\command-failure-memory\.cmd''' -Message 'SKILL.md must include the explicit USERPROFILE fallback path example'
Assert-Match -Value $skillContent -Pattern 'command-failure-memory\.py' -Message 'SKILL.md must explain the compatible Python backend'
Assert-Match -Value $skillContent -Pattern 'command-failure-memory\.ps1' -Message 'SKILL.md must document the PowerShell fallback/backend'
Assert-Match -Value $skillContent -Pattern '-Action record-failure' -Message 'SKILL.md must show record-failure usage'
Assert-Match -Value $skillContent -Pattern '-Action query-before-retry' -Message 'SKILL.md must show query-before-retry usage'
Assert-Match -Value $skillContent -Pattern '-Action record-success' -Message 'SKILL.md must show record-success usage'
Assert-Match -Value $skillContent -Pattern '-Action inspect' -Message 'SKILL.md must show inspect usage'
Assert-Match -Value $skillContent -Pattern 'ScopeKind' -Message 'SKILL.md must explain scope selection'

$openAiYaml = Get-Content -LiteralPath $openAiYamlPath -Raw -Encoding UTF8
Assert-Match -Value $openAiYaml -Pattern 'display_name:\s*"Command Failure Memory"' -Message 'openai.yaml must expose the expected display name'
Assert-Match -Value $openAiYaml -Pattern 'short_description:\s*".*failed command.*retry loops.*querying history.*verified fixes.*"' -Message 'openai.yaml short_description must describe failure-memory retry handling'
Assert-Match -Value $openAiYaml -Pattern 'default_prompt:\s*".*Automatically use.*\.\\\\skills\\\\command-failure-memory\\\\scripts\\\\command-failure-memory\.cmd.*%CODEX_HOME%\\\\skills\\\\command-failure-memory\\\\scripts\\\\command-failure-memory\.cmd.*%USERPROFILE%\\\\.codex\\\\skills\\\\command-failure-memory\\\\scripts\\\\command-failure-memory\.cmd.*record-failure.*query-before-retry.*record-success.*"' -Message 'openai.yaml default_prompt must describe workspace-local, runtime, and fallback launcher resolution plus the full loop'

Write-Host 'PASS: command-failure-memory skill metadata and documentation contract'
