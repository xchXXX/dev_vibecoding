$ErrorActionPreference = 'Stop'

function Read-HookPayload {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw 'empty_hook_payload'
    }

    return ($raw | ConvertFrom-Json -AsHashtable)
}

function Test-BashWriteRisk {
    param([string]$CommandText)

    if ([string]::IsNullOrWhiteSpace($CommandText)) {
        return $false
    }

    $patterns = @(
        '(?i)\b(Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item)\b',
        '(?i)(^|[;&|]\s*)(rm|mv|cp|mkdir|touch)\b',
        '(?i)\b(git\s+(apply|am|commit|merge|rebase|cherry-pick))\b',
        '(?i)\b(sed|perl)\s+-i\b',
        '(^|[^>])>(?!>)',
        '>>'
    )

    foreach ($pattern in $patterns) {
        if ($CommandText -match $pattern) {
            return $true
        }
    }

    return $false
}

function Get-RepoRoot {
    param([hashtable]$Payload)

    $cwd = $Payload['cwd']
    if ([string]::IsNullOrWhiteSpace($cwd)) {
        throw 'missing_cwd'
    }

    Push-Location -LiteralPath $cwd
    try {
        $gitRoot = (& git rev-parse --show-toplevel 2>$null)
        if (-not [string]::IsNullOrWhiteSpace($gitRoot)) {
            return $gitRoot.Trim()
        }

        return [System.IO.Path]::GetFullPath($cwd)
    } finally {
        Pop-Location
    }
}

function Invoke-DocRoutingValidation {
    param(
        [string]$RepoRoot,
        [string]$ValidateScript
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $ValidateScript -RepoRoot $RepoRoot 2>&1
    $exitCode = $LASTEXITCODE

    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = @($output)
    }
}

function Write-DocRoutingHint {
    param(
        [string]$Details,
        [string]$RepoRoot
    )

    $lines = @(
        '[codex-hook] 文档分流提示：检测到当前仓库存在文档骨架缺口。'
        '[codex-hook] 当前 hook 仅作观测/提示，不保证阻断写入。'
    )

    if (-not [string]::IsNullOrWhiteSpace($Details)) {
        $lines += ('[codex-hook] 详情：{0}' -f $Details)
    }

    if (-not [string]::IsNullOrWhiteSpace($RepoRoot)) {
        $lines += ('[codex-hook] 建议先补齐：{0}' -f (Join-Path $RepoRoot 'docs/modules/<module>/contract'))
        $lines += ('[codex-hook] 建议先补齐：{0}' -f (Join-Path $RepoRoot 'docs/modules/<module>/design'))
        $lines += ('[codex-hook] 建议先补齐：{0}' -f (Join-Path $RepoRoot 'docs/modules/<module>/delivery/code-map'))
        $lines += ('[codex-hook] 建议先补齐：{0}' -f (Join-Path $RepoRoot 'docs/modules/<module>/delivery/engineering'))
    }

    foreach ($line in $lines) {
        [Console]::Error.WriteLine($line)
    }
}

try {
    $payload = Read-HookPayload
    $toolName = [string]$payload['tool_name']
    $toolInput = $payload['tool_input']
    $commandText = ''

    if ($toolInput -is [hashtable] -and $toolInput.ContainsKey('command')) {
        $commandText = [string]$toolInput['command']
    }

    if ($toolName -eq 'Bash' -and -not (Test-BashWriteRisk -CommandText $commandText)) {
        exit 0
    }

    if ($toolName -ne 'Bash' -and $toolName -ne 'apply_patch') {
        exit 0
    }

    $repoRoot = Get-RepoRoot -Payload $payload
    $validateScript = Join-Path $repoRoot 'scripts/validate-doc-routing.ps1'
    if (-not (Test-Path -LiteralPath $validateScript)) {
        Write-DocRoutingHint -Details '文档分流校验脚本缺失。' -RepoRoot $repoRoot
        exit 0
    }

    $result = Invoke-DocRoutingValidation -RepoRoot $repoRoot -ValidateScript $validateScript
    if ($result.ExitCode -ne 0) {
        $details = (($result.Output | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ }) -join ' | ')
        if ([string]::IsNullOrWhiteSpace($details)) {
            $details = '未提供额外错误输出。'
        }

        Write-DocRoutingHint -Details $details -RepoRoot $repoRoot
        exit 0
    }

    exit 0
} catch {
    [Console]::Error.WriteLine(("[codex-hook] PreToolUse 提示脚本执行异常：{0}" -f $_.Exception.Message))
    [Console]::Error.WriteLine('[codex-hook] 当前 hook 仅作观测/提示，不保证阻断写入。')
    exit 0
}
