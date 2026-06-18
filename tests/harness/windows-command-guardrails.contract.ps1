param()

$ErrorActionPreference = 'Stop'

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$GlobalAgentsPath = 'C:\Users\72385\.codex\AGENTS.md'
$RulePathWindows = Join-Path $RepoRoot 'rules/items/policy/命令构造约束.md'
$RulePathNoise = Join-Path $RepoRoot 'rules/items/policy/平台噪音与任务失败判定.md'
$RulePathPwsh = Join-Path $RepoRoot 'rules/items/policy/脚本运行基线.md'
$CompatDocPath = Join-Path $RepoRoot 'docs/CODEX_COMPAT.md'

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-ContainsText {
    param([string]$Text, [string]$Expected, [string]$Message)
    if ([string]::IsNullOrWhiteSpace($Text) -or (-not $Text.Contains($Expected))) {
        throw ('{0} (missing: {1})' -f $Message, $Expected)
    }
}

function Run-TestCase {
    param([string]$Name, [scriptblock]$Body)
    try {
        & $Body
        $script:PassCount += 1
        Write-Host ('PASS {0}' -f $Name)
    } catch {
        $script:Failures.Add(('{0}: {1}' -f $Name, $_.Exception.Message)) | Out-Null
        Write-Host ('FAIL {0}' -f $Name)
        Write-Host ('  {0}' -f $_.Exception.Message)
    }
}

function Test-GlobalAgentsPreferences {
    Assert-True (Test-Path -LiteralPath $GlobalAgentsPath) 'global AGENTS.md must exist'
    $content = Get-Content -LiteralPath $GlobalAgentsPath -Raw -Encoding UTF8
    Assert-ContainsText -Text $content -Expected '说明性内容默认使用中文' -Message 'global AGENTS must keep explanatory language preference'
    Assert-ContainsText -Text $content -Expected '先回答问题，再继续手头工作' -Message 'global AGENTS must require answer-first routing'
    Assert-ContainsText -Text $content -Expected 'quiet long-run' -Message 'global AGENTS must describe quiet long-run behavior'
    Assert-ContainsText -Text $content -Expected '优先避免脆弱的复杂 one-liner' -Message 'global AGENTS must describe Windows one-liner guardrail'
    Assert-ContainsText -Text $content -Expected '优先直接调用 `.py` 或 `.ps1` 入口' -Message 'global AGENTS must prefer direct script entry for complex parameters'
    Assert-ContainsText -Text $content -Expected '`ghost snapshot` / `NUL` 索引失败' -Message 'global AGENTS must classify NUL noise separately'
}

function Test-WindowsCommandRule {
    Assert-True (Test-Path -LiteralPath $RulePathWindows) 'Windows command construction rule must exist'
    $content = Get-Content -LiteralPath $RulePathWindows -Raw -Encoding UTF8
    Assert-ContainsText -Text $content -Expected '复杂 shell 逻辑优先写成一行命令' -Message 'rule must mention complex one-liner prohibition'
    Assert-ContainsText -Text $content -Expected '不要继续走 `.cmd`' -Message 'rule must ban complex parameters from .cmd path'
    Assert-ContainsText -Text $content -Expected '一次性排障或临时分析脚本在完成后应及时清理' -Message 'rule must define temporary script cleanup'
    Assert-ContainsText -Text $content -Expected '`ghost snapshot`、`NUL` 保留名索引失败等平台级异常' -Message 'rule must isolate platform noise from ordinary command failure'
}

function Test-PlatformNoiseRule {
    Assert-True (Test-Path -LiteralPath $RulePathNoise) 'platform noise rule must exist'
    $content = Get-Content -LiteralPath $RulePathNoise -Raw -Encoding UTF8
    Assert-ContainsText -Text $content -Expected '默认先视为“平台噪音候选”' -Message 'platform noise rule must define noise candidate default'
    Assert-ContainsText -Text $content -Expected '第一段：先看用户目标命令本身是否失败' -Message 'platform noise rule must define first-stage command result check'
    Assert-ContainsText -Text $content -Expected '第二段：再看 `ghost snapshot` / `NUL` 是否来自目标命令自己' -Message 'platform noise rule must define source attribution check'
    Assert-ContainsText -Text $content -Expected '第三段：最后看产物是否完整' -Message 'platform noise rule must define artifact completeness check'
    Assert-ContainsText -Text $content -Expected '应提升为“可疑状态”' -Message 'platform noise rule must define suspicious-state escalation'
    Assert-ContainsText -Text $content -Expected '不得自动触发普通命令失败闭环' -Message 'platform noise rule must block keyword-only auto failure'
}

function Test-PwshBaselineRuleAndCompatDoc {
    Assert-True (Test-Path -LiteralPath $RulePathPwsh) 'PowerShell 7 baseline rule must exist'
    $ruleContent = Get-Content -LiteralPath $RulePathPwsh -Raw -Encoding UTF8
    Assert-ContainsText -Text $ruleContent -Expected 'PowerShell 7，不再把 Windows PowerShell 5.1 作为默认兼容目标' -Message 'pwsh baseline rule must reject 5.1 as default baseline'
    Assert-ContainsText -Text $ruleContent -Expected '`pwsh -NoProfile -ExecutionPolicy Bypass -File ...`' -Message 'pwsh baseline rule must require pwsh invocation examples'
    Assert-ContainsText -Text $ruleContent -Expected '`#requires -Version 7.0`' -Message 'pwsh baseline rule must mention explicit version guard'

    Assert-True (Test-Path -LiteralPath $CompatDocPath) 'CODEX_COMPAT.md must exist'
    $compatContent = Get-Content -LiteralPath $CompatDocPath -Raw -Encoding UTF8
    Assert-ContainsText -Text $compatContent -Expected '不假设“已经切到 `pwsh7`”就等于 Windows 命令不再有 quoting' -Message 'compat doc must reject the pwsh7-is-enough assumption'
    Assert-ContainsText -Text $compatContent -Expected 'Windows 默认执行基线统一为 `pwsh` / PowerShell 7。' -Message 'compat doc must state pwsh baseline'
    Assert-ContainsText -Text $compatContent -Expected '`.cmd` 只作为简单参数兼容入口' -Message 'compat doc must constrain .cmd usage'
    Assert-ContainsText -Text $compatContent -Expected '`ghost snapshot` 的 `NUL` 保留名索引失败默认先视为平台噪音候选' -Message 'compat doc must isolate NUL noise as candidate first'
    Assert-ContainsText -Text $compatContent -Expected '应先判为“可疑状态”并补最小验证' -Message 'compat doc must require suspicious-state validation before final verdict'
}

Run-TestCase -Name 'Global AGENTS must define long-term user preferences for Windows collaboration' -Body { Test-GlobalAgentsPreferences }
Run-TestCase -Name 'Project rule must constrain Windows command construction' -Body { Test-WindowsCommandRule }
Run-TestCase -Name 'Project rule must define platform noise vs task failure boundary' -Body { Test-PlatformNoiseRule }
Run-TestCase -Name 'Project rule and compat doc must keep pwsh7 baseline' -Body { Test-PwshBaselineRuleAndCompatDoc }

Write-Host ('TOTAL PASS {0}' -f $script:PassCount)
if ($script:Failures.Count -gt 0) {
    Write-Host ('TOTAL FAIL {0}' -f $script:Failures.Count)
    foreach ($failure in $script:Failures) {
        Write-Host ('  {0}' -f $failure)
    }
    exit 1
}

Write-Host 'ALL TESTS PASSED'
exit 0
