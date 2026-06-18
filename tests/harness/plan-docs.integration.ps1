param()

$ErrorActionPreference = 'Stop'

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw 'This plan docs integration suite requires Windows.'
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$TempRoot = Join-Path $env:TEMP ('ai-harness-plan-docs-tests-' + [guid]::NewGuid().ToString('N'))
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

function New-Scenario {
    param([string]$Name)

    $root = Join-Path $TempRoot $Name
    $repoRoot = Join-Path $root 'repo'
    $tasksRoot = Join-Path $repoRoot 'docs\tasks'
    $modulesRoot = Join-Path $repoRoot 'modules'
    $docsModulesRoot = Join-Path $repoRoot 'docs\modules'
    New-Item -ItemType Directory -Path $tasksRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $modulesRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $docsModulesRoot -Force | Out-Null
    return [PSCustomObject]@{
        RepoRoot = $repoRoot
        TasksRoot = $tasksRoot
        ModulesRoot = $modulesRoot
        DocsModulesRoot = $docsModulesRoot
    }
}

function New-ModuleDocSet {
    param(
        [string]$RepoRoot,
        [string]$ModuleName,
        [switch]$WithRequiredDocs
    )

    $moduleRoot = Join-Path $RepoRoot ('modules\' + $ModuleName)
    $docsModuleRoot = Join-Path $RepoRoot ('docs\modules\' + $ModuleName)
    New-Item -ItemType Directory -Path $moduleRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $docsModuleRoot -Force | Out-Null

    if ($WithRequiredDocs) {
        foreach ($relativePath in @('contract', 'design', 'delivery\code-map', 'delivery\engineering')) {
            New-Item -ItemType Directory -Path (Join-Path $docsModuleRoot $relativePath) -Force | Out-Null
        }
    }

    return [PSCustomObject]@{
        ModuleRoot = $moduleRoot
        DocsModuleRoot = $docsModuleRoot
    }
}

function New-TaskDocSet {
    param(
        [string]$TasksRoot,
        [string]$TaskId
    )

    $taskRoot = Join-Path $TasksRoot $TaskId
    New-Item -ItemType Directory -Path $taskRoot -Force | Out-Null
    return [PSCustomObject]@{
        TaskId = $TaskId
        Root   = $taskRoot
        Plan   = Join-Path $taskRoot 'plan.md'
        Execution = Join-Path $taskRoot 'execution.md'
        Acceptance = Join-Path $taskRoot 'acceptance.md'
    }
}

function Get-SamplePlanContent {
    return @"
# 任务目标
收敛任务期文档的校验口径。

## 背景与问题
现有脚本仍停留在旧目录模型。

## 范围
仅修改校验脚本与相关测试。

## 非目标
不迁移全部历史任务文档。

## 约束与依赖
说明性内容默认中文。

## 方案摘要
按 docs/tasks/<task-id>/plan.md 收口方案文档。

## 风险与回退
若校验口径误伤历史结构，则回退本次改动。

## 验收标准
校验脚本与集成测试都基于 docs/tasks 通过。

## 阶段划分
先改校验，再改测试，最后回归。

## 需先同步的核心文档与测试
- scripts/validate-plan-docs.ps1
- tests/harness/plan-docs.integration.ps1
"@
}

function Get-SampleExecutionContent {
    return @"
# 施工目标
把施工文档校验迁到 docs/tasks/<task-id>/execution.md。

## 前置条件
方案文档已定稿。

## 执行顺序
先更新脚本，再更新测试，最后执行回归。

## 文档先行清单
- docs/ARCHITECTURE.md
- docs/PROJECT_TEMPLATE.md

## 测试同步清单
- tests/harness/plan-docs.integration.ps1

## 实施批次
- 批次一：脚本
- 批次二：测试

## 每批写入范围
- scripts/validate-plan-docs.ps1
- tests/harness/plan-docs.integration.ps1

## 验证命令
- pwsh -NoProfile -ExecutionPolicy Bypass -File tests/harness/plan-docs.integration.ps1

## 回退方案
恢复脚本与测试到迁移前版本。

## 审查与返工路径
- 先做局部回归
- 再做审查与返工
"@
}

function Get-SampleAcceptanceContent {
    return @"
# 验收目标
验证任务文档三件套与校验脚本已经统一收口。

## 验收标准
- `plan.md`、`execution.md`、`acceptance.md` 都纳入硬闸门。
- 目录骨架校验与章节校验口径一致。

## 必备证据
- `scripts/validate-doc-routing.ps1`
- `scripts/validate-plan-docs.ps1`
- `tests/harness/plan-docs.integration.ps1`

## 未决项
- 不迁移历史 `docs/plans/` 资产。

## 最终结论
- 当前样例仅用于验证校验脚本合同，最终任务结论由真实执行窗口回填。
"@
}

function Write-TaskDocuments {
    param(
        [string]$TasksRoot,
        [string]$TaskId,
        [switch]$SkipPlan,
        [switch]$SkipExecution,
        [switch]$SkipAcceptance
    )

    $docSet = New-TaskDocSet -TasksRoot $TasksRoot -TaskId $TaskId
    if (-not $SkipPlan) {
        Set-Content -LiteralPath $docSet.Plan -Value (Get-SamplePlanContent) -Encoding UTF8
    }
    if (-not $SkipExecution) {
        Set-Content -LiteralPath $docSet.Execution -Value (Get-SampleExecutionContent) -Encoding UTF8
    }
    if (-not $SkipAcceptance) {
        Set-Content -LiteralPath $docSet.Acceptance -Value (Get-SampleAcceptanceContent) -Encoding UTF8
    }
    return $docSet
}

function Remove-HeadingFromMarkdown {
    param(
        [string]$PathValue,
        [string]$Heading
    )

    $content = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8
    $updated = [regex]::Replace($content, "(?m)^#{1,2}\s+$([regex]::Escape($Heading))\s*\r?\n", '', 1)
    Set-Content -LiteralPath $PathValue -Value $updated -Encoding UTF8
}

function Set-HeadingBody {
    param(
        [string]$PathValue,
        [string]$Heading,
        [string]$Body
    )

    $content = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8
    $pattern = "(?ms)(^#{1,2}\s+$([regex]::Escape($Heading))\s*\r?\n)(.*?)(?=^#{1,2}\s+|\z)"
    $updated = [regex]::Replace($content, $pattern, ('$1' + $Body + "`r`n"), 1)
    Set-Content -LiteralPath $PathValue -Value $updated -Encoding UTF8
}

function Invoke-ValidatePlanDocs {
    param([string]$RepoRoot)

    $scriptPath = Join-Path $HarnessRoot 'scripts/validate-plan-docs.ps1'
    return Invoke-PowerShellFile -FilePath $scriptPath -Arguments @('-RepoRoot', $RepoRoot, '-Json')
}

function Invoke-ValidateDocRouting {
    param([string]$RepoRoot)

    $scriptPath = Join-Path $HarnessRoot 'scripts/validate-doc-routing.ps1'
    return Invoke-PowerShellFile -FilePath $scriptPath -Arguments @('-RepoRoot', $RepoRoot, '-Json')
}

function Test-ValidDocsPass {
    $scenario = New-Scenario -Name 'valid-docs-pass'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' | Out-Null

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'valid docs should pass validation'
    Assert-True ($null -ne $result.Json) 'validator should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'valid docs scenario should keep ok=true'
    Assert-True ([int]$result.Json.checked_document_count -eq 3) 'validator should cover one task directory plan/execution/acceptance triplet'
    Assert-True ((@($result.Json.documents | Where-Object { $_.kind -eq 'plan' }).Count) -eq 1) 'result should include one plan document'
    Assert-True ((@($result.Json.documents | Where-Object { $_.kind -eq 'implementation' }).Count) -eq 1) 'result should include one implementation document'
    Assert-True ((@($result.Json.documents | Where-Object { $_.kind -eq 'acceptance' }).Count) -eq 1) 'result should include one acceptance document'
}

function Test-PlanDocMissingHeadingFails {
    $scenario = New-Scenario -Name 'plan-doc-missing-heading'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Remove-HeadingFromMarkdown -PathValue $docSet.Plan -Heading '验收标准'

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'plan doc missing heading should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '缺少必填章节 验收标准' -Message 'validator should report the missing plan heading'
}

function Test-ImplementationDocMissingHeadingFails {
    $scenario = New-Scenario -Name 'implementation-doc-missing-heading'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Remove-HeadingFromMarkdown -PathValue $docSet.Execution -Heading '验证命令'

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'implementation doc missing heading should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '缺少必填章节 验证命令' -Message 'validator should report the missing implementation heading'
}

function Test-NoDocumentsFails {
    $scenario = New-Scenario -Name 'no-documents-fail'

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'missing all task docs should fail validation'
    Assert-True ($null -ne $result.Json) 'validator should emit parseable JSON when no docs exist'
    Assert-True (-not [bool]$result.Json.ok) 'no-docs scenario should keep ok=false'
    Assert-ContainsText -Text $result.Text -Expected 'docs/tasks/<task-id>/plan.md、execution.md 与 acceptance.md' -Message 'validator should reject zero-doc scenario using the new task-doc path'
}

function Test-MissingPlanFileFails {
    $scenario = New-Scenario -Name 'missing-plan-file-fail'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' -SkipPlan | Out-Null

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'missing plan.md should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '缺少必需任务文档 plan.md' -Message 'validator should report missing plan.md'
}

function Test-MissingExecutionFileFails {
    $scenario = New-Scenario -Name 'missing-execution-file-fail'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' -SkipExecution | Out-Null

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'missing execution.md should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '缺少必需任务文档 execution.md' -Message 'validator should report missing execution.md'
}

function Test-MissingAcceptanceFileFails {
    $scenario = New-Scenario -Name 'missing-acceptance-file-fail'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' -SkipAcceptance | Out-Null

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'missing acceptance.md should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '缺少必需任务文档 acceptance.md' -Message 'validator should report missing acceptance.md'
}

function Test-CriticalSectionPlaceholderFails {
    $scenario = New-Scenario -Name 'critical-section-placeholder'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'

    Set-HeadingBody -PathValue $docSet.Plan -Heading '需先同步的核心文档与测试' -Body 'TODO'
    Set-HeadingBody -PathValue $docSet.Execution -Heading '审查与返工路径' -Body '待补'
    Set-HeadingBody -PathValue $docSet.Acceptance -Heading '最终结论' -Body '待补'

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'placeholder critical sections should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '关键章节正文不能为空或占位' -Message 'validator should report critical section content failure'
    Assert-ContainsText -Text $result.Text -Expected '需先同步的核心文档与测试' -Message 'validator should report invalid plan critical section'
    Assert-ContainsText -Text $result.Text -Expected '审查与返工路径' -Message 'validator should report invalid implementation critical section'
    Assert-ContainsText -Text $result.Text -Expected '最终结论' -Message 'validator should report invalid acceptance critical section'
}

function Test-AcceptanceDocMissingHeadingFails {
    $scenario = New-Scenario -Name 'acceptance-doc-missing-heading'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Remove-HeadingFromMarkdown -PathValue $docSet.Acceptance -Heading '验收标准'

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'acceptance doc missing heading should fail validation'
    Assert-ContainsText -Text $result.Text -Expected '缺少必填章节 验收标准' -Message 'validator should report the missing acceptance heading'
}

function Test-DescriptiveMentionOfPlaceholderDoesNotFail {
    $scenario = New-Scenario -Name 'placeholder-word-mentioned-but-valid'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Set-HeadingBody -PathValue $docSet.Execution -Heading '测试同步清单' -Body @'
- `tests/harness/plan-docs.integration.ps1`：覆盖关键章节占位场景与真实正文场景。
'@

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'descriptive mention of 占位场景 should not fail validation'
    Assert-True ([bool]$result.Json.ok) 'descriptive mention scenario should keep ok=true'
}

function Test-MultipleTaskDirectoriesPass {
    $scenario = New-Scenario -Name 'multiple-task-directories-pass'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' | Out-Null
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-002' | Out-Null

    $result = Invoke-ValidatePlanDocs -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'multiple task directories should still pass validation'
    Assert-True ([bool]$result.Json.ok) 'multiple-task-docs scenario should keep ok=true'
    Assert-True ([int]$result.Json.checked_document_count -eq 6) 'validator should include both task directory triplets'
    Assert-True ((@($result.Json.documents | Where-Object { $_.kind -eq 'plan' }).Count) -eq 2) 'result should include multiple plan documents'
    Assert-True ((@($result.Json.documents | Where-Object { $_.kind -eq 'implementation' }).Count) -eq 2) 'result should include multiple implementation documents'
    Assert-True ((@($result.Json.documents | Where-Object { $_.kind -eq 'acceptance' }).Count) -eq 2) 'result should include multiple acceptance documents'
}

function Test-ValidateDocRoutingPassesWithTriplet {
    $scenario = New-Scenario -Name 'doc-routing-valid-triplet'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' | Out-Null

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'validate-doc-routing should pass when plan/execution/acceptance all exist'
    Assert-True ($null -ne $result.Json) 'validate-doc-routing should emit parseable JSON'
    Assert-True ([bool]$result.Json.ok) 'validate-doc-routing valid scenario should keep ok=true'
}

function Test-ValidateDocRoutingMissingAcceptanceFails {
    $scenario = New-Scenario -Name 'doc-routing-missing-acceptance'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' -SkipAcceptance | Out-Null

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'validate-doc-routing should fail when acceptance.md is missing'
    Assert-ContainsText -Text $result.Text -Expected 'acceptance.md' -Message 'validate-doc-routing should report missing acceptance.md'
}

function Test-ValidateDocRoutingNotApplicablePlaceholderFails {
    $scenario = New-Scenario -Name 'doc-routing-not-applicable-placeholder'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Set-HeadingBody -PathValue $docSet.Acceptance -Heading '未决项' -Body @'
- 某项：不适用
'@

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'validate-doc-routing should fail on bare 不适用 placeholder'
    Assert-ContainsText -Text $result.Text -Expected '无理由的“不适用”占位' -Message 'validate-doc-routing should reject bare 不适用 placeholders'
}

function Test-ValidateDocRoutingNotApplicableWithReasonPasses {
    $scenario = New-Scenario -Name 'doc-routing-not-applicable-with-reason'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Set-HeadingBody -PathValue $docSet.Acceptance -Heading '未决项' -Body @'
- 某项：不适用：本批不涉及对应模块。
'@

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'validate-doc-routing should pass when 不适用 carries a reason'
    Assert-True ([bool]$result.Json.ok) 'validate-doc-routing should keep ok=true when 不适用 has a reason'
}

function Test-ValidateDocRoutingExampleNAStaysValid {
    $scenario = New-Scenario -Name 'doc-routing-example-na-valid'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Set-HeadingBody -PathValue $docSet.Acceptance -Heading '未决项' -Body @'
- 文档示例：N/A
'@

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'validate-doc-routing should not reject descriptive example lines containing N/A'
    Assert-True ([bool]$result.Json.ok) 'descriptive N/A example should keep ok=true'
}

function Test-ValidateDocRoutingForExampleNAStaysValid {
    $scenario = New-Scenario -Name 'doc-routing-for-example-na-valid'
    $docSet = Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001'
    Set-HeadingBody -PathValue $docSet.Acceptance -Heading '未决项' -Body @'
- 例如：N/A
'@

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'validate-doc-routing should not reject 例如：N/A example lines'
    Assert-True ([bool]$result.Json.ok) '例如：N/A example should keep ok=true'
}

function Test-ValidateDocRoutingModuleSkeletonMissingFails {
    $scenario = New-Scenario -Name 'doc-routing-module-skeleton-missing'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' | Out-Null
    New-ModuleDocSet -RepoRoot $scenario.RepoRoot -ModuleName 'alpha' | Out-Null

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -ne 0) 'validate-doc-routing should fail when module docs skeleton is incomplete'
    Assert-ContainsText -Text $result.Text -Expected '模块 alpha 缺少最小文档骨架' -Message 'validate-doc-routing should report incomplete module doc skeleton'
    Assert-ContainsText -Text $result.Text -Expected 'delivery/code-map' -Message 'validate-doc-routing should list the missing module doc directories'
}

function Test-ValidateDocRoutingModuleSkeletonPasses {
    $scenario = New-Scenario -Name 'doc-routing-module-skeleton-pass'
    Write-TaskDocuments -TasksRoot $scenario.TasksRoot -TaskId 'task-001' | Out-Null
    New-ModuleDocSet -RepoRoot $scenario.RepoRoot -ModuleName 'alpha' -WithRequiredDocs | Out-Null

    $result = Invoke-ValidateDocRouting -RepoRoot $scenario.RepoRoot
    Assert-True ($result.ExitCode -eq 0) 'validate-doc-routing should pass when module docs skeleton is complete'
    Assert-True ([bool]$result.Json.ok) 'complete module docs skeleton should keep ok=true'
}

Run-TestCase -Name 'Valid docs: task plan and execution docs should pass' -Body { Test-ValidDocsPass }
Run-TestCase -Name 'Bad path: plan doc missing required heading should fail' -Body { Test-PlanDocMissingHeadingFails }
Run-TestCase -Name 'Bad path: execution doc missing required heading should fail' -Body { Test-ImplementationDocMissingHeadingFails }
Run-TestCase -Name 'Bad path: zero task documents should fail' -Body { Test-NoDocumentsFails }
Run-TestCase -Name 'Bad path: missing plan.md should fail' -Body { Test-MissingPlanFileFails }
Run-TestCase -Name 'Bad path: missing execution.md should fail' -Body { Test-MissingExecutionFileFails }
Run-TestCase -Name 'Bad path: missing acceptance.md should fail' -Body { Test-MissingAcceptanceFileFails }
Run-TestCase -Name 'Bad path: critical sections with placeholders should fail' -Body { Test-CriticalSectionPlaceholderFails }
Run-TestCase -Name 'Bad path: acceptance doc missing required heading should fail' -Body { Test-AcceptanceDocMissingHeadingFails }
Run-TestCase -Name 'Valid docs: descriptive mention of placeholder should not fail' -Body { Test-DescriptiveMentionOfPlaceholderDoesNotFail }
Run-TestCase -Name 'Valid docs: multiple task directories should pass' -Body { Test-MultipleTaskDirectoriesPass }
Run-TestCase -Name 'Valid docs: validate-doc-routing should pass with document triplet' -Body { Test-ValidateDocRoutingPassesWithTriplet }
Run-TestCase -Name 'Bad path: validate-doc-routing missing acceptance.md should fail' -Body { Test-ValidateDocRoutingMissingAcceptanceFails }
Run-TestCase -Name 'Bad path: validate-doc-routing bare 不适用 placeholder should fail' -Body { Test-ValidateDocRoutingNotApplicablePlaceholderFails }
Run-TestCase -Name 'Valid docs: validate-doc-routing 不适用 with reason should pass' -Body { Test-ValidateDocRoutingNotApplicableWithReasonPasses }
Run-TestCase -Name 'Valid docs: validate-doc-routing descriptive N/A example should pass' -Body { Test-ValidateDocRoutingExampleNAStaysValid }
Run-TestCase -Name 'Valid docs: validate-doc-routing 例如 N/A example should pass' -Body { Test-ValidateDocRoutingForExampleNAStaysValid }
Run-TestCase -Name 'Bad path: validate-doc-routing incomplete module doc skeleton should fail' -Body { Test-ValidateDocRoutingModuleSkeletonMissingFails }
Run-TestCase -Name 'Valid docs: validate-doc-routing complete module doc skeleton should pass' -Body { Test-ValidateDocRoutingModuleSkeletonPasses }

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
