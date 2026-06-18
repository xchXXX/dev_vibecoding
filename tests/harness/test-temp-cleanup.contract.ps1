param()

$ErrorActionPreference = 'Stop'

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$RulePath = Join-Path $RepoRoot 'rules/items/policy/测试临时文件必须清理.md'
$ScriptPaths = @(
    'tests/harness/rules-validation.integration.ps1',
    'tests/harness/rules-index.integration.ps1',
    'tests/harness/plan-docs.integration.ps1',
    'tests/harness/control-plane.integration.ps1',
    'tests/harness/codex-sync.integration.ps1',
    'tests/harness/claude-hooks-phase5.integration.ps1',
    'tests/harness/codex-failure-memory.integration.ps1',
    'tests/benchmarks/command-failure-memory.forward.ps1',
    'tests/benchmarks/command-failure-memory.autotrigger.ps1'
)

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

function Test-TempCleanupRule {
    Assert-True (Test-Path -LiteralPath $RulePath) 'test temp cleanup rule must exist'
    $content = Get-Content -LiteralPath $RulePath -Raw -Encoding UTF8
    Assert-ContainsText -Text $content -Expected '测试失败也不例外' -Message 'rule must require cleanup on failure path'
    Assert-ContainsText -Text $content -Expected '显式 opt-in 开关' -Message 'rule must constrain debug retention behind explicit opt-in'
    Assert-ContainsText -Text $content -Expected 'PowerShell.Exiting' -Message 'rule must recommend a robust cleanup hook'
}

function Test-ScriptsRegisterTempCleanup {
    foreach ($relativePath in $ScriptPaths) {
        $path = Join-Path $RepoRoot $relativePath
        Assert-True (Test-Path -LiteralPath $path) ("script must exist: {0}" -f $relativePath)
        $content = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        Assert-ContainsText -Text $content -Expected 'Register-EngineEvent PowerShell.Exiting' -Message ("script must register exit cleanup: {0}" -f $relativePath)
        Assert-ContainsText -Text $content -Expected 'Remove-Item -LiteralPath $event.MessageData -Recurse -Force' -Message ("script must remove temp root recursively: {0}" -f $relativePath)
    }
}

Run-TestCase -Name 'Global rule must require cleanup for test temp files' -Body { Test-TempCleanupRule }
Run-TestCase -Name 'Harness and benchmark scripts must register TempRoot cleanup' -Body { Test-ScriptsRegisterTempCleanup }

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
