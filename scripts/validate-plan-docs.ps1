param(
    [string]$RepoRoot = '',
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

function Get-ResolvedRepoRoot {
    param(
        [string]$InputRepoRoot,
        [string]$ScriptPath
    )

    if (-not [string]::IsNullOrWhiteSpace($InputRepoRoot)) {
        return [System.IO.Path]::GetFullPath($InputRepoRoot)
    }

    return [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $ScriptPath) '..'))
}

function New-DocRule {
    param(
        [string]$Kind,
        [string]$Label,
        [string]$FileName,
        [string[]]$RequiredHeadings,
        [string[]]$RequiredNonEmptyHeadings = @()
    )

    return [PSCustomObject]@{
        Kind             = $Kind
        Label            = $Label
        FileName         = $FileName
        RequiredHeadings = $RequiredHeadings
        RequiredNonEmptyHeadings = $RequiredNonEmptyHeadings
    }
}

function Get-HeadingMap {
    param([string]$PathValue)

    $content = Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8
    $matches = [regex]::Matches($content, '(?m)^(#{1,2})\s+(.+?)\s*$')
    $headingMap = @{}
    for ($i = 0; $i -lt $matches.Count; $i++) {
        $match = $matches[$i]
        $heading = $match.Groups[2].Value.Trim()
        if (-not [string]::IsNullOrWhiteSpace($heading)) {
            $bodyStart = $match.Index + $match.Length
            $bodyEnd = $content.Length
            if ($i + 1 -lt $matches.Count) {
                $bodyEnd = $matches[$i + 1].Index
            }

            $body = ''
            if ($bodyEnd -gt $bodyStart) {
                $body = $content.Substring($bodyStart, $bodyEnd - $bodyStart)
            }

            $headingMap[$heading] = [PSCustomObject]@{
                title = $heading
                body  = $body
            }
        }
    }

    return $headingMap
}

function Test-SectionHasMeaningfulContent {
    param([string]$Body)

    $normalized = ($Body -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return $false
    }

    $lines = @($Body -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lines.Count -eq 0) {
        return $false
    }

    $placeholderLinePatterns = @(
        '^(?:[-*]\s*)?(?i:TODO|TBD)\s*$',
        '^(?:[-*]\s*)?待补(?:[:：].*)?\s*$',
        '^(?:[-*]\s*)?占位(?:[:：].*)?\s*$',
        '^(?:[-*]\s*)?待填写(?:[:：].*)?\s*$'
    )

    $allLinesArePlaceholders = $true
    foreach ($line in $lines) {
        $isPlaceholderLine = $false
        foreach ($pattern in $placeholderLinePatterns) {
            if ($line -match $pattern) {
                $isPlaceholderLine = $true
                break
            }
        }
        if (-not $isPlaceholderLine) {
            $allLinesArePlaceholders = $false
            break
        }
    }

    if ($allLinesArePlaceholders) {
        return $false
    }

    return $true
}

function Resolve-PlanDocuments {
    param(
        [string]$RepoRootValue,
        [object[]]$Rules
    )

    $tasksRoot = Join-Path $RepoRootValue 'docs/tasks'
    $documents = New-Object System.Collections.Generic.List[object]
    $taskDirs = New-Object System.Collections.Generic.List[object]

    if (-not (Test-Path -LiteralPath $tasksRoot)) {
        return [PSCustomObject]@{
            TaskDirs   = @()
            Documents  = @()
        }
    }

    foreach ($taskDir in @(Get-ChildItem -LiteralPath $tasksRoot -Directory -ErrorAction SilentlyContinue)) {
        $taskDirs.Add($taskDir) | Out-Null
        foreach ($rule in $Rules) {
            $docPath = Join-Path $taskDir.FullName $rule.FileName
            $documents.Add([PSCustomObject]@{
                TaskId = $taskDir.Name
                Path   = $docPath
                Exists = (Test-Path -LiteralPath $docPath -PathType Leaf)
                Rule   = $rule
            }) | Out-Null
        }
    }

    return [PSCustomObject]@{
        TaskDirs  = $taskDirs.ToArray()
        Documents = $documents.ToArray()
    }
}

function Get-RelativePath {
    param(
        [string]$RepoRootValue,
        [string]$PathValue
    )

    $repoPrefix = [System.IO.Path]::GetFullPath($RepoRootValue)
    $fullPath = [System.IO.Path]::GetFullPath($PathValue)
    if ($fullPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $fullPath.Substring($repoPrefix.Length).TrimStart('\', '/')
        if (-not [string]::IsNullOrWhiteSpace($relative)) {
            return ($relative -replace '\\', '/')
        }
    }

    return $fullPath
}

$resolvedRepoRoot = Get-ResolvedRepoRoot -InputRepoRoot $RepoRoot -ScriptPath $MyInvocation.MyCommand.Path
$rules = @(
    (New-DocRule `
        -Kind 'plan' `
        -Label '方案文档' `
        -FileName 'plan.md' `
        -RequiredHeadings @(
            '任务目标',
            '背景与问题',
            '范围',
            '非目标',
            '约束与依赖',
            '方案摘要',
            '风险与回退',
            '验收标准',
            '阶段划分',
            '需先同步的核心文档与测试'
        ) `
        -RequiredNonEmptyHeadings @(
            '需先同步的核心文档与测试'
        )),
    (New-DocRule `
        -Kind 'implementation' `
        -Label '施工文档' `
        -FileName 'execution.md' `
        -RequiredHeadings @(
            '施工目标',
            '前置条件',
            '执行顺序',
            '文档先行清单',
            '测试同步清单',
            '实施批次',
            '每批写入范围',
            '验证命令',
            '回退方案',
            '审查与返工路径'
        ) `
        -RequiredNonEmptyHeadings @(
            '文档先行清单',
            '测试同步清单',
            '审查与返工路径'
        )),
    (New-DocRule `
        -Kind 'acceptance' `
        -Label '验收文档' `
        -FileName 'acceptance.md' `
        -RequiredHeadings @(
            '验收目标',
            '验收标准',
            '必备证据',
            '未决项',
            '最终结论'
        ) `
        -RequiredNonEmptyHeadings @(
            '验收标准',
            '必备证据',
            '最终结论'
        ))
)

$resolvedDocuments = Resolve-PlanDocuments -RepoRootValue $resolvedRepoRoot -Rules $rules
$documents = @($resolvedDocuments.Documents)
$taskDirs = @($resolvedDocuments.TaskDirs)
$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$docResults = New-Object System.Collections.Generic.List[object]

if ($taskDirs.Count -eq 0) {
    $errors.Add('未发现 docs/tasks/<task-id>/plan.md、execution.md 与 acceptance.md，长任务在正式实施前必须先在 docs/tasks/<task-id>/ 下落盘方案文档、施工文档与验收文档。') | Out-Null
}

foreach ($document in $documents) {
    if (-not $document.Exists) {
        $errors.Add(('{0}: 缺少必需任务文档 {1}' -f (Get-RelativePath -RepoRootValue $resolvedRepoRoot -PathValue (Split-Path -Parent $document.Path)), $document.Rule.FileName)) | Out-Null
        $docResults.Add([PSCustomObject]@{
            task_id            = $document.TaskId
            path               = Get-RelativePath -RepoRootValue $resolvedRepoRoot -PathValue $document.Path
            kind               = $document.Rule.Kind
            label              = $document.Rule.Label
            required_file_name = $document.Rule.FileName
            required_headings  = @($document.Rule.RequiredHeadings)
            required_non_empty_headings = @($document.Rule.RequiredNonEmptyHeadings)
            missing_headings   = @()
            invalid_content_headings = @()
            ok                 = $false
            exists             = $false
        }) | Out-Null
        continue
    }

    $headingMap = Get-HeadingMap -PathValue $document.Path
    $missingHeadings = New-Object System.Collections.Generic.List[string]
    $invalidContentHeadings = New-Object System.Collections.Generic.List[string]

    foreach ($requiredHeading in $document.Rule.RequiredHeadings) {
        if (-not $headingMap.ContainsKey($requiredHeading)) {
            $missingHeadings.Add($requiredHeading) | Out-Null
        }
    }

    if ($missingHeadings.Count -gt 0) {
        $errors.Add(('{0}: 缺少必填章节 {1}' -f (Get-RelativePath -RepoRootValue $resolvedRepoRoot -PathValue $document.Path), (($missingHeadings.ToArray()) -join ', '))) | Out-Null
    }

    foreach ($requiredNonEmptyHeading in $document.Rule.RequiredNonEmptyHeadings) {
        if ($headingMap.ContainsKey($requiredNonEmptyHeading)) {
            if (-not (Test-SectionHasMeaningfulContent -Body $headingMap[$requiredNonEmptyHeading].body)) {
                $invalidContentHeadings.Add($requiredNonEmptyHeading) | Out-Null
            }
        }
    }

    if ($invalidContentHeadings.Count -gt 0) {
        $errors.Add(('{0}: 关键章节正文不能为空或占位 {1}' -f (Get-RelativePath -RepoRootValue $resolvedRepoRoot -PathValue $document.Path), (($invalidContentHeadings.ToArray()) -join ', '))) | Out-Null
    }

    $docResults.Add([PSCustomObject]@{
        task_id            = $document.TaskId
        path               = Get-RelativePath -RepoRootValue $resolvedRepoRoot -PathValue $document.Path
        kind               = $document.Rule.Kind
        label              = $document.Rule.Label
        required_file_name = $document.Rule.FileName
        required_headings  = @($document.Rule.RequiredHeadings)
        required_non_empty_headings = @($document.Rule.RequiredNonEmptyHeadings)
        missing_headings   = @($missingHeadings)
        invalid_content_headings = @($invalidContentHeadings)
        ok                 = (($missingHeadings.Count -eq 0) -and ($invalidContentHeadings.Count -eq 0))
        exists             = $true
    }) | Out-Null
}

$result = [PSCustomObject]@{
    ok                     = ($errors.Count -eq 0)
    repo_root              = $resolvedRepoRoot
    checked_document_count = $documents.Count
    error_count            = $errors.Count
    warning_count          = $warnings.Count
    errors                 = $errors.ToArray()
    warnings               = $warnings.ToArray()
    documents              = $docResults.ToArray()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 10
} else {
    foreach ($error in @($errors)) {
        Write-Host ('ERROR {0}' -f $error)
    }
    foreach ($warning in @($warnings)) {
        Write-Host ('WARNING {0}' -f $warning)
    }
    if ($result.ok) {
        Write-Host ('Validation passed for {0} documents' -f $result.checked_document_count)
    }
}

if ($result.ok) {
    exit 0
}

exit 1
