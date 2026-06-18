param(
    [string]$RepoRoot = '',
    [string[]]$GlobalRulesRoot = @(),
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rules-index.common.ps1')

$resolvedRepoRoot = Get-RulesRepoRoot -RepoRoot $RepoRoot -ScriptPath $MyInvocation.MyCommand.Path
$model = Get-RulesModel -RepoRoot $resolvedRepoRoot -GlobalRulesRoots $GlobalRulesRoot

$result = [ordered]@{
    ok                  = (@($model.Errors).Count -eq 0)
    repo_root           = $resolvedRepoRoot
    local_rule_count    = @($model.LocalRules).Count
    global_rule_count   = @($model.GlobalRules).Count
    resolved_rule_count = @($model.ResolvedRules).Count
    errors              = @($model.Errors)
    warnings            = @($model.Warnings)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 10
} else {
    foreach ($error in @($model.Errors)) {
        Write-Host ("ERROR {0}" -f $error)
    }
    foreach ($warning in @($model.Warnings)) {
        Write-Host ("WARNING {0}" -f $warning)
    }
    if ($result.ok) {
        Write-Host ("Validation passed for {0} local rules" -f $result.local_rule_count)
    }
}

if ($result.ok) {
    exit 0
}

exit 1
