param()

$ErrorActionPreference = 'Stop'

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw 'This rules index integration suite requires Windows.'
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$TempRoot = Join-Path $env:TEMP ('ai-harness-rules-index-tests-' + [guid]::NewGuid().ToString('N'))
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

function Assert-Equal {
    param([object]$Expected, [object]$Actual, [string]$Message)
    if ($Expected -ne $Actual) {
        throw ('{0} (expected: {1}; actual: {2})' -f $Message, $Expected, $Actual)
    }
}

function Assert-ContainsText {
    param([string]$Text, [string]$Expected, [string]$Message)
    if ([string]::IsNullOrWhiteSpace($Text) -or (-not $Text.Contains($Expected))) {
        throw ('{0} (missing: {1})' -f $Message, $Expected)
    }
}

function Read-Json {
    param([string]$PathValue)
    return (Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json)
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

function New-Scenario {
    param([string]$Name)

    $root = Join-Path $TempRoot $Name
    $repoRoot = Join-Path $root 'repo'
    $globalRoot = Join-Path $root 'global'
    New-Item -ItemType Directory -Path $repoRoot, $globalRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $repoRoot 'rules/items/policy'), (Join-Path $repoRoot 'rules/items/style'), (Join-Path $repoRoot 'skills/command-failure-memory') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $globalRoot 'rules/items/policy'), (Join-Path $globalRoot 'skills/shared-skill') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $repoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $globalRoot 'skills/shared-skill/SKILL.md') -Value '# skill' -Encoding UTF8

    return [PSCustomObject]@{
        RepoRoot   = $repoRoot
        GlobalRoot = $globalRoot
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

function Test-GenerateArtifactsAndResolvedView {
    $scenario = New-Scenario -Name 'generate-artifacts'
    $globalRule = Get-RuleContent `
        -Id 'global.policy.基础规则' `
        -Title '全局基础规则' `
        -Subject 'base-policy' `
        -Scope 'global' `
        -Kind 'policy' `
        -Priority 10 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'governance' `
        -Status 'active' `
        -Summary '全局规则摘要。' `
        -LinkedSkill 'shared-skill' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.GlobalRoot -RelativePath 'rules/items/policy/全局基础规则.md' -Content $globalRule

    $projectPolicy = Get-RuleContent `
        -Id 'project.policy.命令失败闭环' `
        -Title '命令失败闭环' `
        -Subject 'command-failure-memory' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell', 'retry') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '命令失败后先记录，重试前先查询，成功后回写。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'executable_backed' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @('global.policy.基础规则') `
        -OverrideReason '项目需要更严格的失败闭环。'
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/命令失败闭环.md' -Content $projectPolicy

    $styleRule = Get-RuleContent `
        -Id 'project.style.说明默认使用中文' `
        -Title '说明默认使用中文' `
        -Subject 'language-default' `
        -Scope 'project' `
        -Kind 'style' `
        -Priority 20 `
        -Activation 'always_on' `
        -Intents @('answer') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '说明性内容默认使用中文。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'merge' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/style/说明默认使用中文.md' -Content $styleRule

    $scriptPath = Join-Path $HarnessRoot 'scripts/generate-rules-index.ps1'
    $result = Invoke-PowerShellFile -FilePath $scriptPath -Arguments @('-RepoRoot', $scenario.RepoRoot, '-GlobalRulesRoot', $scenario.GlobalRoot, '-Json')
    Assert-Equal 0 $result.ExitCode 'generate-rules-index should succeed on valid fixture'
    Assert-True ($null -ne $result.Json) 'generate-rules-index should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'generate-rules-index should report ok=true'

    $registryRoot = Join-Path $scenario.RepoRoot 'rules/registry'
    $indexJsonPath = Join-Path $registryRoot 'RULES_INDEX.json'
    $indexMdPath = Join-Path $registryRoot 'RULES_INDEX.md'
    $resolvedJsonPath = Join-Path $registryRoot 'RULES_RESOLVED.json'
    Assert-True (Test-Path -LiteralPath $indexJsonPath) 'RULES_INDEX.json should exist'
    Assert-True (Test-Path -LiteralPath $indexMdPath) 'RULES_INDEX.md should exist'
    Assert-True (Test-Path -LiteralPath $resolvedJsonPath) 'RULES_RESOLVED.json should exist'

    $indexJson = Read-Json -PathValue $indexJsonPath
    $resolvedJson = Read-Json -PathValue $resolvedJsonPath
    $indexMd = Get-Content -LiteralPath $indexMdPath -Raw -Encoding UTF8

    Assert-Equal 2 @($indexJson.rules).Count 'RULES_INDEX.json should only include local rules'
    Assert-ContainsText -Text $indexMd -Expected 'project.policy.命令失败闭环' -Message 'RULES_INDEX.md should list local policy rule'
    Assert-ContainsText -Text $indexMd -Expected 'project.style.说明默认使用中文' -Message 'RULES_INDEX.md should list local style rule'
    Assert-True ((@($resolvedJson.override_relations).Count) -eq 1) 'RULES_RESOLVED.json should record one override relation'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'global.policy.基础规则' }).Count) -eq 0) 'resolved view should suppress overridden global rule'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'project.policy.命令失败闭环' }).Count) -eq 1) 'resolved view should retain overriding local rule'
    $localResolvedRule = @($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'project.policy.命令失败闭环' })[0]
    Assert-True ($localResolvedRule.paths -is [System.Collections.IEnumerable]) 'resolved rule paths should remain an array'
    Assert-Equal 0 @($localResolvedRule.paths).Count 'empty paths should stay as one-dimensional empty array'
    Assert-True (@($localResolvedRule.intents).Count -eq 2) 'resolved rule intents should stay as one-dimensional array'
    Assert-Equal 'shell' ([string]@($localResolvedRule.intents)[0]) 'resolved rule intents should not gain extra nesting'
}

function New-AutoDiscoveryScenario {
    param([string]$Name)

    $root = Join-Path $TempRoot $Name
    $repoRoot = Join-Path $root 'project-repo'
    $aiHarnessRoot = Join-Path $root 'ai-harness'
    New-Item -ItemType Directory -Path $repoRoot, $aiHarnessRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $repoRoot 'rules/items/policy'), (Join-Path $repoRoot 'skills/command-failure-memory') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $aiHarnessRoot 'rules/items/policy'), (Join-Path $aiHarnessRoot 'skills/shared-skill') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $repoRoot 'skills/command-failure-memory/SKILL.md') -Value '# skill' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $aiHarnessRoot 'skills/shared-skill/SKILL.md') -Value '# skill' -Encoding UTF8

    return [PSCustomObject]@{
        RepoRoot = $repoRoot
        AiHarnessRoot = $aiHarnessRoot
    }
}

function Test-AutoDiscoveryIncludesSiblingAiHarness {
    $scenario = New-AutoDiscoveryScenario -Name 'auto-discovery'

    $globalRule = Get-RuleContent `
        -Id 'global.policy.共享规范' `
        -Title '共享规范' `
        -Subject 'shared-policy' `
        -Scope 'global' `
        -Kind 'policy' `
        -Priority 10 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'governance' `
        -Status 'active' `
        -Summary '共享规则摘要。' `
        -LinkedSkill 'shared-skill' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.AiHarnessRoot -RelativePath 'rules/items/policy/共享规范.md' -Content $globalRule

    $localRule = Get-RuleContent `
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
        -Summary '本地规则摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/命令失败闭环.md' -Content $localRule

    $scriptPath = Join-Path $HarnessRoot 'scripts/generate-rules-index.ps1'
    $result = Invoke-PowerShellFile -FilePath $scriptPath -Arguments @('-RepoRoot', $scenario.RepoRoot, '-Json')
    Assert-Equal 0 $result.ExitCode 'generate-rules-index should auto-discover sibling ai-harness'

    $resolvedJson = Read-Json -PathValue (Join-Path $scenario.RepoRoot 'rules/registry/RULES_RESOLVED.json')
    Assert-Equal 'auto_sibling_ai_harness' ([string]$resolvedJson.global_rules.mode) 'resolved view should record auto discovery mode'
    Assert-Equal $true ([bool]$resolvedJson.global_rules.discovered) 'auto discovery should mark discovered=true'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'global.policy.共享规范' }).Count) -eq 1) 'resolved view should include discovered global rule'
}

function Test-MergeOverrideProducesMergedResolvedRule {
    $scenario = New-Scenario -Name 'merge-override'

    $globalRule = Get-RuleContent `
        -Id 'global.policy.基础规则' `
        -Title '全局基础规则' `
        -Subject 'shared-policy' `
        -Scope 'global' `
        -Kind 'policy' `
        -Priority 10 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'governance' `
        -Status 'active' `
        -Summary '全局规则摘要。' `
        -LinkedSkill 'shared-skill' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason '' `
        -Body '全局正文'
    New-RuleFile -Root $scenario.GlobalRoot -RelativePath 'rules/items/policy/全局基础规则.md' -Content $globalRule

    $projectRule = Get-RuleContent `
        -Id 'project.policy.项目补充规则' `
        -Title '项目补充规则' `
        -Subject 'shared-policy' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('retry') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '项目规则摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'merge' `
        -Overrides @('global.policy.基础规则') `
        -OverrideReason '项目在全局基础上追加要求。' `
        -Body '项目正文'
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/项目补充规则.md' -Content $projectRule

    $scriptPath = Join-Path $HarnessRoot 'scripts/generate-rules-index.ps1'
    $result = Invoke-PowerShellFile -FilePath $scriptPath -Arguments @('-RepoRoot', $scenario.RepoRoot, '-GlobalRulesRoot', $scenario.GlobalRoot, '-Json')
    Assert-Equal 0 $result.ExitCode 'generate-rules-index should support merge override'

    $resolvedJson = Read-Json -PathValue (Join-Path $scenario.RepoRoot 'rules/registry/RULES_RESOLVED.json')
    $mergedRule = @($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'project.policy.项目补充规则' })
    Assert-Equal 1 $mergedRule.Count 'resolved view should retain merged project rule'
    Assert-ContainsText -Text ($mergedRule[0].body) -Expected '全局正文' -Message 'merged rule should keep base body content'
    Assert-ContainsText -Text ($mergedRule[0].body) -Expected '项目正文' -Message 'merged rule should append overlay body content'
    Assert-True ((@($mergedRule[0].merged_from_ids).Count) -ge 2) 'merged rule should expose merged_from_ids'
    Assert-Equal 'global.policy.基础规则' ([string]@($mergedRule[0].merged_from_ids)[0]) 'merged_from_ids should remain one-dimensional string array'
}

function Test-ExplicitGlobalRootIgnoresProjectScopedRules {
    $scenario = New-Scenario -Name 'ignore-project-scope-from-global-root'

    $globalRule = Get-RuleContent `
        -Id 'global.style.共享说明默认中文' `
        -Title '共享说明默认中文' `
        -Subject 'shared-language-default' `
        -Scope 'global' `
        -Kind 'style' `
        -Priority 10 `
        -Activation 'always_on' `
        -Intents @('answer') `
        -Owner 'governance' `
        -Status 'active' `
        -Summary '共享说明默认中文。' `
        -LinkedSkill 'shared-skill' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.GlobalRoot -RelativePath 'rules/items/style/共享说明默认中文.md' -Content $globalRule

    $projectOnlyRule = Get-RuleContent `
        -Id 'project.architecture.仅限宿主仓库的入口' `
        -Title '仅限宿主仓库的入口' `
        -Subject 'host-only-entrypoint' `
        -Scope 'project' `
        -Kind 'architecture' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('architecture') `
        -Owner 'governance' `
        -Status 'active' `
        -Summary '这条规则只应留在宿主仓库。' `
        -LinkedSkill '' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.GlobalRoot -RelativePath 'rules/items/architecture/仅限宿主仓库的入口.md' -Content $projectOnlyRule

    $localRule = Get-RuleContent `
        -Id 'project.policy.本地命令规则' `
        -Title '本地命令规则' `
        -Subject 'local-shell-policy' `
        -Scope 'project' `
        -Kind 'policy' `
        -Priority 100 `
        -Activation 'always_on' `
        -Intents @('shell') `
        -Owner 'ai-governance' `
        -Status 'active' `
        -Summary '本地规则摘要。' `
        -LinkedSkill 'command-failure-memory' `
        -Enforcement 'advisory' `
        -Overrideable $true `
        -OverrideMode 'replace' `
        -Overrides @() `
        -OverrideReason ''
    New-RuleFile -Root $scenario.RepoRoot -RelativePath 'rules/items/policy/本地命令规则.md' -Content $localRule

    $scriptPath = Join-Path $HarnessRoot 'scripts/generate-rules-index.ps1'
    $result = Invoke-PowerShellFile -FilePath $scriptPath -Arguments @('-RepoRoot', $scenario.RepoRoot, '-GlobalRulesRoot', $scenario.GlobalRoot, '-Json')
    Assert-Equal 0 $result.ExitCode 'generate-rules-index should ignore project scoped entries from external global root'

    $resolvedJson = Read-Json -PathValue (Join-Path $scenario.RepoRoot 'rules/registry/RULES_RESOLVED.json')
    Assert-Equal 1 ([int]$resolvedJson.global_rule_count) 'only non-project rules from external global root should be imported'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'global.style.共享说明默认中文' }).Count) -eq 1) 'resolved view should include global rule from explicit global root'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'project.architecture.仅限宿主仓库的入口' }).Count) -eq 0) 'resolved view should exclude project scoped rule from explicit global root'
    Assert-ContainsText -Text $result.Text -Expected '忽略全局规则根中的 project scope 条目' -Message 'generation output should mention ignored project scoped entries'
}

function Test-ThisRepoCanServeAsGlobalRulesRoot {
    $scenario = New-Scenario -Name 'current-repo-as-global-root'
    $scriptPath = Join-Path $HarnessRoot 'scripts/generate-rules-index.ps1'
    $result = Invoke-PowerShellFile -FilePath $scriptPath -Arguments @('-RepoRoot', $scenario.RepoRoot, '-GlobalRulesRoot', $HarnessRoot, '-Json')
    Assert-Equal 0 $result.ExitCode 'current repo should be consumable as explicit global rules root'

    $resolvedJson = Read-Json -PathValue (Join-Path $scenario.RepoRoot 'rules/registry/RULES_RESOLVED.json')
    Assert-True (([int]$resolvedJson.global_rule_count) -ge 16) 'current repo should export the expected global rule set'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'global.style.说明默认使用中文' }).Count) -eq 1) 'consumer repo should receive shared language rule'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'global.workflow.长任务实施顺序' }).Count) -eq 1) 'consumer repo should receive shared long-task workflow rule'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'project.architecture.仓库目录边界' }).Count) -eq 0) 'consumer repo should not import host-only repository boundary rule'
    Assert-True ((@($resolvedJson.resolved_rules | Where-Object { $_.id -eq 'project.architecture.真源入口' }).Count) -eq 0) 'consumer repo should not import host-only entrypoint rule'
}

Run-TestCase -Name 'Generate artifacts and resolved view from local + mock global rules' -Body { Test-GenerateArtifactsAndResolvedView }
Run-TestCase -Name 'Auto discovery: sibling ai-harness should be included in resolved view' -Body { Test-AutoDiscoveryIncludesSiblingAiHarness }
Run-TestCase -Name 'Merge override: merged rule should keep base and overlay content' -Body { Test-MergeOverrideProducesMergedResolvedRule }
Run-TestCase -Name 'Explicit global root: project scoped entries should be ignored' -Body { Test-ExplicitGlobalRootIgnoresProjectScopedRules }
Run-TestCase -Name 'Current repo: should be consumable as global rules root by another project' -Body { Test-ThisRepoCanServeAsGlobalRulesRoot }

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
