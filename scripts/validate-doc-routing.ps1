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

function Get-ChildDirectories {
    param([string]$PathValue)

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return @()
    }

    return @(Get-ChildItem -LiteralPath $PathValue -Directory -ErrorAction SilentlyContinue)
}

function Test-NotApplicableLineHasReason {
    param([string]$Line)

    $trimmed = $Line.Trim()
    if ($trimmed -notmatch '不适用|N/A|n/a') {
        return $true
    }

    $exampleLabelPattern = '^(?:[-*]\s*)?(?<label>[^:：]+)[:：]\s*(?:N/A|n/a)\s*$'
    if ($trimmed -match $exampleLabelPattern) {
        $label = $Matches['label'].Trim()
        if ($label -match '示例|样例|例子|例如|写法|格式|模板|说明|含义') {
            return $true
        }
    }

    $invalidPlaceholderPatterns = @(
        '^(?:[-*]\s*)?(?:[^:：]+[:：]\s*)?不适用\s*$',
        '^(?:[-*]\s*)?(?:[^:：]+[:：]\s*)?不适用\s*[:：]\s*$',
        '^(?:[-*]\s*)?(?:[^:：]+[:：]\s*)?(?:N/A|n/a)\s*$',
        '^(?:[-*]\s*)?(?:[^:：]+[:：]\s*)?(?:N/A|n/a)\s*[:：]\s*$'
    )

    foreach ($pattern in $invalidPlaceholderPatterns) {
        if ($trimmed -match $pattern) {
            return $false
        }
    }

    return $true
}

function Get-MarkdownFiles {
    param([string[]]$Roots)

    $results = New-Object System.Collections.Generic.List[string]
    foreach ($root in $Roots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        foreach ($file in @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter *.md -ErrorAction SilentlyContinue)) {
            $results.Add($file.FullName) | Out-Null
        }
    }

    return $results.ToArray()
}

$resolvedRepoRoot = Get-ResolvedRepoRoot -InputRepoRoot $RepoRoot -ScriptPath $MyInvocation.MyCommand.Path
$modulesRoot = Join-Path $resolvedRepoRoot 'modules'
$docsModulesRoot = Join-Path $resolvedRepoRoot 'docs/modules'
$docsTasksRoot = Join-Path $resolvedRepoRoot 'docs/tasks'

$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$moduleResults = New-Object System.Collections.Generic.List[object]
$taskResults = New-Object System.Collections.Generic.List[object]
$notApplicableResults = New-Object System.Collections.Generic.List[object]

$requiredModuleDocDirectories = @(
    'contract',
    'design',
    'delivery\code-map',
    'delivery\engineering'
)

foreach ($moduleDir in @(Get-ChildDirectories -PathValue $modulesRoot)) {
    $moduleName = $moduleDir.Name
    $docsModuleDir = Join-Path $docsModulesRoot $moduleName
    $missingPaths = New-Object System.Collections.Generic.List[string]

    if (-not (Test-Path -LiteralPath $docsModuleDir)) {
        $errors.Add(("模块 `{0}` 存在代码目录，但缺少对应长期真源目录 `docs/modules/{0}`。" -f $moduleName)) | Out-Null
        $missingPaths.Add('docs/modules') | Out-Null
    } else {
        foreach ($relativePath in $requiredModuleDocDirectories) {
            $targetPath = Join-Path $docsModuleDir $relativePath
            if (-not (Test-Path -LiteralPath $targetPath)) {
                $missingPaths.Add($relativePath.Replace('\', '/')) | Out-Null
            }
        }

        if ($missingPaths.Count -gt 0) {
            $errors.Add(("模块 `{0}` 缺少最小文档骨架：{1}" -f $moduleName, (($missingPaths.ToArray()) -join ', '))) | Out-Null
        }
    }

    $moduleResults.Add([PSCustomObject]@{
        module_name = $moduleName
        module_path = $moduleDir.FullName
        docs_module_path = $docsModuleDir
        required_paths = @($requiredModuleDocDirectories)
        missing_paths = @($missingPaths)
        ok = ($missingPaths.Count -eq 0)
    }) | Out-Null
}

foreach ($taskDir in @(Get-ChildDirectories -PathValue $docsTasksRoot)) {
    $missingFiles = New-Object System.Collections.Generic.List[string]
    foreach ($requiredFile in @('plan.md', 'execution.md', 'acceptance.md')) {
        $targetPath = Join-Path $taskDir.FullName $requiredFile
        if (-not (Test-Path -LiteralPath $targetPath)) {
            $missingFiles.Add($requiredFile) | Out-Null
        }
    }

    if ($missingFiles.Count -gt 0) {
        $errors.Add(("任务目录 `{0}` 缺少必需文件：{1}" -f $taskDir.FullName, (($missingFiles.ToArray()) -join ', '))) | Out-Null
    }

    $taskResults.Add([PSCustomObject]@{
        task_name = $taskDir.Name
        task_path = $taskDir.FullName
        missing_files = @($missingFiles)
        ok = ($missingFiles.Count -eq 0)
    }) | Out-Null
}

$markdownFiles = Get-MarkdownFiles -Roots @($docsModulesRoot, $docsTasksRoot)
foreach ($filePath in $markdownFiles) {
    $lineNumber = 0
    foreach ($line in @(Get-Content -LiteralPath $filePath -Encoding UTF8)) {
        $lineNumber += 1
        if (-not (Test-NotApplicableLineHasReason -Line $line)) {
            $errors.Add(('{0}:{1} 存在无理由的“不适用”占位，请写成 `不适用：原因...`。' -f $filePath, $lineNumber)) | Out-Null
            $notApplicableResults.Add([PSCustomObject]@{
                path = $filePath
                line_number = $lineNumber
                line = $line
                ok = $false
            }) | Out-Null
        }
    }
}

$result = [PSCustomObject]@{
    ok = ($errors.Count -eq 0)
    repo_root = $resolvedRepoRoot
    checked_module_count = $moduleResults.Count
    checked_task_count = $taskResults.Count
    checked_markdown_count = $markdownFiles.Count
    error_count = $errors.Count
    warning_count = $warnings.Count
    errors = $errors.ToArray()
    warnings = $warnings.ToArray()
    modules = $moduleResults.ToArray()
    tasks = $taskResults.ToArray()
    not_applicable_checks = $notApplicableResults.ToArray()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 10
} else {
    foreach ($errorMessage in @($errors)) {
        Write-Host ('ERROR {0}' -f $errorMessage)
    }
    foreach ($warningMessage in @($warnings)) {
        Write-Host ('WARNING {0}' -f $warningMessage)
    }
    if ($result.ok) {
        Write-Host ('Validation passed for {0} modules and {1} task directories' -f $result.checked_module_count, $result.checked_task_count)
    }
}

if ($result.ok) {
    exit 0
}

exit 1
