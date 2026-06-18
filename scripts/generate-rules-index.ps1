param(
    [string]$RepoRoot = '',
    [string[]]$GlobalRulesRoot = @(),
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rules-index.common.ps1')

$resolvedRepoRoot = Get-RulesRepoRoot -RepoRoot $RepoRoot -ScriptPath $MyInvocation.MyCommand.Path
$model = Get-RulesModel -RepoRoot $resolvedRepoRoot -GlobalRulesRoots $GlobalRulesRoot

if (@($model.Errors).Count -gt 0) {
    $result = [ordered]@{
        ok       = $false
        repo_root = $resolvedRepoRoot
        errors   = @($model.Errors)
        warnings = @($model.Warnings)
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
    }

    exit 1
}

$artifacts = Write-RulesArtifacts -Model $model -RepoRoot $resolvedRepoRoot
$result = [ordered]@{
    ok                  = $true
    repo_root           = $resolvedRepoRoot
    local_rule_count    = @($model.LocalRules).Count
    resolved_rule_count = @($model.ResolvedRules).Count
    warnings            = @($model.Warnings)
    outputs             = [ordered]@{
        rules_index_json = $artifacts.IndexJsonPath
        rules_index_md   = $artifacts.IndexMarkdownPath
        rules_resolved   = $artifacts.ResolvedJsonPath
    }
}

if ($Json) {
    $result | ConvertTo-Json -Depth 10
} else {
    Write-Host ("Generated {0} local rules into rules/registry" -f @($model.LocalRules).Count)
    foreach ($warning in @($model.Warnings)) {
        Write-Host ("WARNING {0}" -f $warning)
    }
}

exit 0
