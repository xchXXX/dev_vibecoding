param()

$ErrorActionPreference = 'Stop'

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw 'This rules validation integration suite requires Windows.'
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$TempRoot = Join-Path $env:TEMP ('ai-harness-rules-validation-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$null = Register-EngineEvent PowerShell.Exiting -Action {
    if (-not [string]::IsNullOrWhiteSpace($event.MessageData) -and (Test-Path -LiteralPath $event.MessageData)) {
        Remove-Item -LiteralPath $event.MessageData -Recurse -Force -ErrorAction SilentlyContinue
    }
} -MessageData $TempRoot

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

function Cleanup-TempRoot {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

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

function Invoke-PowerShellFile {
    param(
        [string]$FilePath,
        [object[]]$Arguments = @()
    )

    $stdoutPath = Join-Path $TempRoot ('stdout-' + [guid]::NewGuid().ToString('N') + '.log')
    $stderrPath = Join-Path $TempRoot ('stderr-' + [guid]::NewGuid().ToString('N') + '.log')
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $FilePath) + $Arguments
    $process = Start-Process -FilePath (Get-Command pwsh).Source -ArgumentList $argList -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($capturePath in @($stdoutPath, $stderrPath)) {
        if (Test-Path -LiteralPath $capturePath) {
            Get-Content -LiteralPath $capturePath -Encoding UTF8 | ForEach-Object { $lines.Add([string]$_) | Out-Null }
            Remove-Item -LiteralPath $capturePath -Force
        }
    }

    $json = $null
    try {
        if ($lines.Count -gt 0) {
            $json = (($lines.ToArray() -join "`n") | ConvertFrom-Json)
        }
    } catch {
        $json = $null
    }

    return [PSCustomObject]@{
        ExitCode = $process.ExitCode
        Text     = ($lines.ToArray() -join "`n")
        Json     = $json
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

function New-RuleFile {
    param(
        [string]$Root,
        [string]$RelativePath,
        [string]$Content
    )

    $path = Join-Path $Root $RelativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
    Set-Content -LiteralPath $path -Value $Content -Encoding UTF8
    return $path
}

function Get-RuleContent {
    param(
        [string]$Id,
        [string]$Title,
        [string]$Subject,
        [string]$Scope,
        [string]$Kind,
        [int]$Priority,
        [string]$Activation,
        [string[]]$Intents,
        [string]$Owner,
        [string]$Status,
        [string]$Summary,
        [string]$LinkedSkill,
        [string]$Enforcement,
        [bool]$Overrideable,
        [string]$OverrideMode,
        [string[]]$Overrides,
        [string]$OverrideReason,
        [string[]]$Paths = @(),
        [string]$Body = '规则正文'
    )

    $intentsText = '[{0}]' -f (($Intents | ForEach-Object { '"{0}"' -f $_ }) -join ', ')
    $pathsText = '[{0}]' -f (($Paths | ForEach-Object { '"{0}"' -f $_ }) -join ', ')
    $overridesText = '[{0}]' -f (($Overrides | ForEach-Object { '"{0}"' -f $_ }) -join ', ')
    return @"
---
id: $Id
title: $Title
subject: $Subject
scope: $Scope
kind: $Kind
priority: $Priority
activation: $Activation
paths: $pathsText
intents: $intentsText
owner: $Owner
status: $Status
summary: $Summary
linked_skill: $LinkedSkill
enforcement: $Enforcement
overrideable: $($Overrideable.ToString().ToLowerInvariant())
override_mode: $OverrideMode
overrides: $overridesText
override_reason: "$OverrideReason"
---
$Body
"@
}

function New-Scenario {
    param([string]$Name)

    $root = Join-Path $TempRoot $Name
    $repoRoot = Join-Path $root 'repo'
    $globalRoot = Join-Path $root 'global'
    New-Item -ItemType Directory -Path $repoRoot, $globalRoot -Force | Out-Null
    return [PSCustomObject]@{
        RepoRoot   = $repoRoot
        GlobalRoot = $globalRoot
    }
}

function Invoke-ValidateRules {
    param(
        [string]$RepoRoot,
        [string[]]$GlobalRulesRoot = @()
    )

    $scriptPath = Join-Path $HarnessRoot 'scripts/validate-rules.ps1'
    $args = @('-RepoRoot', $RepoRoot, '-Json')
    foreach ($root in $GlobalRulesRoot) {
        $args += @('-GlobalRulesRoot', $root)
    }

    return Invoke-PowerShellFile -FilePath $scriptPath -Arguments $args
}

function Test-ValidationWarningOnly {
    $scenario = New-Scenario -Name 'warning-only'
    New-Item -ItemType Directory -Path (Join-Path $scenario.RepoRoot 'skills/command-failure-memory') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.RepoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    $longSummary = ('这是一段用于验证 summary warning 的超长摘要。' * 8)
    $rule = Get-RuleContent `
        -Id 'project.policy.命令失败闭环' `
        -Title '命令失败闭环' `
        -Subject 'command-failure-memory' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary $longSummary `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/命令失败闭环.md' -Content $rule

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'validate-rules should pass when only warnings exist'
    Assert-True ($null -ne $result.Json) 'validate-rules should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'warning-only scenario should keep ok=true'
    Assert-True (@($result.Json.warnings).Count -gt 0) 'warning-only scenario should emit warnings'
    Assert-ContainsText -Text $result.Text -Expected 'summary 长度超过建议阈值 120' -Message 'warning text should mention summary threshold'
}

function Test-KindDirectoryMismatchFails {
    $scenario = New-Scenario -Name 'kind-mismatch'
    New-Item -ItemType Directory -Path (Join-Path $scenario.RepoRoot 'skills/command-failure-memory') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.RepoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    $rule = Get-RuleContent `
        -Id 'project.policy.命令失败闭环' `
        -Title '命令失败闭环' `
        -Subject 'command-failure-memory' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/style/命令失败闭环.md' -Content $rule

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'kind mismatch should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '目录 kind 与 frontmatter kind 不一致' -Message 'validation should report kind mismatch'
}

function Test-EnglishFileNameFails {
    $scenario = New-Scenario -Name 'english-file-name'
    New-Item -ItemType Directory -Path (Join-Path $scenario.RepoRoot 'skills/command-failure-memory') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.RepoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    $rule = Get-RuleContent `
        -Id 'project.policy.failure-loop' `
        -Title '失败闭环' `
        -Subject 'command-failure-memory' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/failure-loop.md' -Content $rule

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'English file name should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '规则文件名必须为中文' -Message 'validation should enforce Chinese file names'
}

function Test-MissingLinkedSkillFails {
    $scenario = New-Scenario -Name 'missing-linked-skill'
    $rule = Get-RuleContent `
        -Id 'project.policy.命令失败闭环' `
        -Title '命令失败闭环' `
        -Subject 'command-failure-memory' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/命令失败闭环.md' -Content $rule

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'missing linked skill should fail validation'
    Assert-ContainsText -Text $result.Text -Expected 'linked_skill 目标不存在' -Message 'validation should report missing linked_skill target'
}

function Test-MissingOverrideTargetFails {
    $scenario = New-Scenario -Name 'missing-override-target'
    New-Item -ItemType Directory -Path (Join-Path $scenario.RepoRoot 'skills/command-failure-memory') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.RepoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    $rule = Get-RuleContent `
        -Id 'project.policy.命令失败闭环' `
        -Title '命令失败闭环' `
        -Subject 'command-failure-memory' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @('global.policy.不存在') `
        -OverrideReason '显式覆盖测试。'
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/命令失败闭环.md' -Content $rule

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'missing override target should fail validation'
    Assert-ContainsText -Text $result.Text -Expected 'overrides 目标不存在' -Message 'validation should report missing override targets'
}

function Test-OverrideNonOverrideableGlobalFails {
    $scenario = New-Scenario -Name 'override-non-overrideable'
    New-Item -ItemType Directory -Path (Join-Path $scenario.RepoRoot 'skills/command-failure-memory'), (Join-Path $scenario.GlobalRoot 'skills/shared-skill') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.RepoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $scenario.GlobalRoot 'skills/shared-skill/SKILL.md') -Value '# skill' -Encoding UTF8
    $globalRule = Get-RuleContent `
        -Id 'global.policy.不可覆盖规则' `
        -Title '全局不可覆盖规则' `
        -Subject 'base-policy' `
        -Scope 'global' `
        -Kind 'policy' `
        -Priority 10 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'governance' `
        -Status 'active' `
        -Summary '摘要。' `
        -LinkedSkill 'shared-skill' `
        -Enforcement 'advisory' `
        -Overrideable $false `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.GlobalRoot -RelativePath 'rules/items/policy/全局不可覆盖规则.md' -Content $globalRule

    $projectRule = Get-RuleContent `
        -Id 'project.policy.命令失败闭环' `
        -Title '命令失败闭环' `
        -Subject 'command-failure-memory' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @('global.policy.不可覆盖规则') `
        -OverrideReason '项目尝试覆盖。'
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/命令失败闭环.md' -Content $projectRule

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot -GlobalRulesRoot @($scenario.GlobalRoot)
    Assert-True ($result.ExitCode -ne 0) 'overrideing non-overrideable global rule should fail validation'
    Assert-ContainsText -Text $result.Text -Expected 'overrideable=false' -Message 'validation should reject overrides of overrideable=false targets'
}

function Test-SubjectConflictWithoutOverridesFails {
    $scenario = New-Scenario -Name 'subject-conflict-without-overrides'
    New-Item -ItemType Directory -Path (Join-Path $scenario.RepoRoot 'skills/command-failure-memory'), (Join-Path $scenario.GlobalRoot 'skills/shared-skill') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.RepoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $scenario.GlobalRoot 'skills/shared-skill/SKILL.md') -Value '# skill' -Encoding UTF8

    $globalRule = Get-RuleContent `
        -Id 'global.policy.共享规则' `
        -Title '共享规则' `
        -Subject 'shared-policy' `
        -Scope 'global' `
        -Kind 'policy' `
        -Priority 10 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'governance' `
        -Status 'active' `
        -Summary '全局摘要。' `
        -LinkedSkill 'shared-skill' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.GlobalRoot -RelativePath 'rules/items/policy/共享规则.md' -Content $globalRule

    $projectRule = Get-RuleContent `
        -Id 'project.policy.本地规则' `
        -Title '本地规则' `
        -Subject 'shared-policy' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '项目摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/本地规则.md' -Content $projectRule

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot -GlobalRulesRoot @($scenario.GlobalRoot)
    Assert-True ($result.ExitCode -ne 0) 'same-subject cross-scope rules without overrides should fail validation'
    Assert-ContainsText -Text $result.Text -Expected 'subject 冲突但未显式 overrides' -Message 'validation should reject unresolved subject conflicts'
}

function Test-ScalarArrayFieldFails {
    $scenario = New-Scenario -Name 'scalar-array-field'
    New-Item -ItemType Directory -Path (Join-Path $scenario.RepoRoot 'skills/command-failure-memory') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.RepoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8

    $content = @"
---
id: project.policy.命令失败闭环
title: 命令失败闭环
subject: command-failure-memory
scope: project
kind: policy
priority: 100
activation: always_on
paths: []
intents: shell
owner: ai-governance
status: active
summary: 摘要。
linked_skill: command-failure-memory
enforcement: advisory
overrideable: true
override_mode: replace
overrides: []
override_reason: ""
---
规则正文
"@
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/命令失败闭环.md' -Content $content

    $result = Invoke-ValidateRules -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'scalar array field should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '字段 intents 必须使用数组语法' -Message 'validation should reject scalar intents syntax'
}

Run-TestCase -Name 'Warning only: length threshold emits warning but does not fail' -Body { Test-ValidationWarningOnly }
Run-TestCase -Name 'Bad path: kind directory mismatch should fail validate' -Body { Test-KindDirectoryMismatchFails }
Run-TestCase -Name 'Bad path: English file name should fail validate' -Body { Test-EnglishFileNameFails }
Run-TestCase -Name 'Bad path: missing linked_skill should fail validate' -Body { Test-MissingLinkedSkillFails }
Run-TestCase -Name 'Bad path: missing overrides target should fail validate' -Body { Test-MissingOverrideTargetFails }
Run-TestCase -Name 'Bad path: overrideable=false target should fail validate' -Body { Test-OverrideNonOverrideableGlobalFails }
Run-TestCase -Name 'Bad path: same-subject conflict without overrides should fail validate' -Body { Test-SubjectConflictWithoutOverridesFails }
Run-TestCase -Name 'Bad path: scalar array syntax should fail validate' -Body { Test-ScalarArrayFieldFails }

Write-Host ('TOTAL PASS {0}' -f $script:PassCount)
if ($script:Failures.Count -gt 0) {
    Write-Host ('TOTAL FAIL {0}' -f $script:Failures.Count)
    foreach ($failure in $script:Failures) {
        Write-Host ('  {0}' -f $failure)
    }
    Cleanup-TempRoot
    exit 1
}

Write-Host 'ALL TESTS PASSED'
Cleanup-TempRoot
exit 0
