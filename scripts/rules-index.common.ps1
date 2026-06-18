Set-StrictMode -Version Latest

$script:RuleKinds = @('policy', 'workflow', 'architecture', 'quality', 'stack', 'style')
$script:RuleScopes = @('global', 'project', 'path')
$script:RuleActivations = @('always_on', 'model_decision', 'path', 'manual')
$script:RuleStatuses = @('active', 'deprecated', 'draft')
$script:RuleEnforcements = @('advisory', 'executable_backed')
$script:RuleOverrideModes = @('merge', 'replace')
$script:RuleArrayFields = @('paths', 'intents', 'overrides')
$script:RequiredRuleFields = @(
    'id', 'title', 'subject', 'scope', 'kind', 'priority', 'activation', 'paths',
    'intents', 'owner', 'status', 'summary', 'linked_skill', 'enforcement',
    'overrideable', 'override_mode', 'overrides', 'override_reason'
)

function New-RulesValidationState {
    return [PSCustomObject]@{
        Errors   = New-Object System.Collections.ArrayList
        Warnings = New-Object System.Collections.ArrayList
    }
}

function Add-RulesError {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][string]$Message
    )

    [void]$State.Errors.Add($Message)
}

function Add-RulesWarning {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][string]$Message
    )

    [void]$State.Warnings.Add($Message)
}

function Get-RulesRepoRoot {
    param(
        [string]$RepoRoot,
        [string]$ScriptPath
    )

    if (-not [string]::IsNullOrWhiteSpace($RepoRoot)) {
        return [System.IO.Path]::GetFullPath($RepoRoot)
    }

    return [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $ScriptPath) '..'))
}

function Resolve-RulesRootPath {
    param(
        [Parameter(Mandatory = $true)][string]$BaseRoot,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    return [System.IO.Path]::GetFullPath((Join-Path $BaseRoot $RelativePath))
}

function Get-RelativePathForJson {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $rootUri = [System.Uri](([System.IO.Path]::GetFullPath($RootPath).TrimEnd('\')) + '\')
    $targetUri = [System.Uri]([System.IO.Path]::GetFullPath($TargetPath))
    return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($targetUri).ToString()).Replace('/', '\')
}

function ConvertFrom-RuleScalar {
    param([string]$Text)

    if ($null -eq $Text) {
        return $null
    }

    $trimmed = $Text.Trim()
    if ($trimmed -eq '') {
        return ''
    }

    if (($trimmed.StartsWith('"') -and $trimmed.EndsWith('"')) -or ($trimmed.StartsWith("'") -and $trimmed.EndsWith("'"))) {
        return $trimmed.Substring(1, $trimmed.Length - 2)
    }

    if ($trimmed -eq 'true') {
        return $true
    }

    if ($trimmed -eq 'false') {
        return $false
    }

    $intValue = 0
    if ([int]::TryParse($trimmed, [ref]$intValue)) {
        return $intValue
    }

    return $trimmed
}

function ConvertFrom-RuleArrayLiteral {
    param([Parameter(Mandatory = $true)][string]$Text)

    $trimmed = $Text.Trim()
    if ($trimmed -eq '[]') {
        return ,([object[]]@())
    }

    try {
        $parsed = $trimmed.Replace("'", '"') | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw ("无法解析数组值: {0}" -f $trimmed)
    }

    if ($parsed -is [string] -or $null -eq $parsed) {
        return ,([object[]]@($parsed))
    }

    $items = New-Object System.Collections.ArrayList
    foreach ($item in $parsed) {
        [void]$items.Add($item)
    }

    return ,([object[]]$items.ToArray())
}

function Parse-RuleFrontmatter {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath
    )

    $raw = Get-Content -LiteralPath $FilePath -Raw -Encoding UTF8
    if (-not $raw.StartsWith("---`n") -and -not $raw.StartsWith("---`r`n")) {
        throw ("文件缺少 frontmatter 起始分隔符: {0}" -f $FilePath)
    }

    $match = [regex]::Match($raw, '(?ms)^---\r?\n(.*?)\r?\n---\r?\n?')
    if (-not $match.Success) {
        throw ("文件缺少完整 frontmatter: {0}" -f $FilePath)
    }

    $frontmatterText = $match.Groups[1].Value
    $body = $raw.Substring($match.Length)
    $values = @{}
    $arraySyntax = @{}
    $pendingArrayKey = $null

    foreach ($line in ($frontmatterText -split "`r?`n")) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        if ($line -match '^\s+-\s*(.+?)\s*$') {
            if ($null -eq $pendingArrayKey) {
                throw ("frontmatter 数组项缺少对应字段: {0}" -f $FilePath)
            }

            if ($values[$pendingArrayKey] -isnot [System.Collections.IList]) {
                $values[$pendingArrayKey] = New-Object System.Collections.ArrayList
            }

            [void]$values[$pendingArrayKey].Add((ConvertFrom-RuleScalar -Text $Matches[1]))
            continue
        }

        if ($line -notmatch '^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$') {
            throw ("frontmatter 行格式非法: {0}" -f $line)
        }

        $key = $Matches[1]
        $valueText = $Matches[2]
        if ($valueText -eq '') {
            $values[$key] = New-Object System.Collections.ArrayList
            $arraySyntax[$key] = $true
            $pendingArrayKey = $key
            continue
        }

        if ($valueText.Trim().StartsWith('[') -and $valueText.Trim().EndsWith(']')) {
            $values[$key] = (ConvertFrom-RuleArrayLiteral -Text $valueText)
            $arraySyntax[$key] = $true
        } else {
            $values[$key] = ConvertFrom-RuleScalar -Text $valueText
        }

        $pendingArrayKey = $null
    }

    return [PSCustomObject]@{
        Values      = $values
        ArraySyntax = $arraySyntax
        Body        = $body
    }
}

function Test-ChineseFileName {
    param([Parameter(Mandatory = $true)][string]$BaseName)

    if ($BaseName -match '[A-Za-z0-9]') {
        return $false
    }

    return [regex]::IsMatch($BaseName, '[\p{IsCJKUnifiedIdeographs}]')
}

function Get-StringArray {
    param($Value)

    if ($null -eq $Value) {
        return ,([object[]]@())
    }

    if ($Value -is [string]) {
        return ,([object[]]@($Value))
    }

    $items = New-Object System.Collections.ArrayList
    foreach ($item in $Value) {
        [void]$items.Add($item)
    }

    return ,([object[]]$items.ToArray())
}

function Get-UniqueStringArray {
    param([object[]]$Values)

    $seen = @{}
    $result = New-Object System.Collections.ArrayList
    foreach ($item in @($Values)) {
        if ($item -isnot [string]) {
            continue
        }

        if (-not $seen.ContainsKey($item)) {
            $seen[$item] = $true
            [void]$result.Add($item)
        }
    }

    return ,([object[]]$result.ToArray())
}

function Get-ScopeRank {
    param([Parameter(Mandatory = $true)][string]$Scope)

    switch ($Scope) {
        'global' { return 1 }
        'project' { return 2 }
        'path' { return 3 }
        default { return 0 }
    }
}

function Copy-RuleRecord {
    param([Parameter(Mandatory = $true)]$Rule)

    $copy = [ordered]@{}
    foreach ($property in $Rule.PSObject.Properties) {
        $name = $property.Name
        $value = $property.Value
        if ($value -is [hashtable]) {
            $nested = @{}
            foreach ($key in $value.Keys) {
                $nested[$key] = $value[$key]
            }
            $copy[$name] = $nested
        } elseif (($value -is [System.Collections.IEnumerable]) -and ($value -isnot [string])) {
            $items = New-Object System.Collections.ArrayList
            foreach ($item in $value) {
                [void]$items.Add($item)
            }
            $copy[$name] = [object[]]$items.ToArray()
        } else {
            $copy[$name] = $value
        }
    }

    return [PSCustomObject]$copy
}

function Merge-RuleRecord {
    param(
        [Parameter(Mandatory = $true)]$BaseRule,
        [Parameter(Mandatory = $true)]$OverlayRule
    )

    $merged = Copy-RuleRecord -Rule $OverlayRule
    $merged.paths = Get-UniqueStringArray -Values ((Get-StringArray -Value $BaseRule.paths) + (Get-StringArray -Value $OverlayRule.paths))
    $merged.intents = Get-UniqueStringArray -Values ((Get-StringArray -Value $BaseRule.intents) + (Get-StringArray -Value $OverlayRule.intents))
    $merged.overrides = Get-UniqueStringArray -Values (Get-StringArray -Value $OverlayRule.overrides)
    $merged.body = ((@($BaseRule.body, $OverlayRule.body) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join "`r`n`r`n")
    $merged.merged_from_ids = Get-UniqueStringArray -Values ((Get-StringArray -Value $BaseRule.merged_from_ids) + @($BaseRule.id) + (Get-StringArray -Value $OverlayRule.merged_from_ids) + @($OverlayRule.id))
    $merged.source_label = ('merged:{0}<={1}' -f $OverlayRule.id, $BaseRule.id)
    return $merged
}

function Test-RuleFieldType {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$ExpectedType
    )

    switch ($ExpectedType) {
        'string' { return $Value -is [string] }
        'int' { return ($Value -is [int]) -or ($Value -is [long]) }
        'bool' { return $Value -is [bool] }
        'array' { return (($Value -is [System.Collections.IEnumerable]) -and ($Value -isnot [string])) }
        default { throw ("未知字段类型: {0}" -f $ExpectedType) }
    }
}

function ConvertTo-RuleRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$SourceLabel
    )

    $parsed = Parse-RuleFrontmatter -FilePath $FilePath
    $values = $parsed.Values
    $kindDir = Split-Path -Leaf (Split-Path -Parent $FilePath)
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FilePath)
    $relativePath = Get-RelativePathForJson -RootPath $RepoRoot -TargetPath $FilePath
    $bodyText = ($parsed.Body -replace '^\s+|\s+$', '')

    return [PSCustomObject]@{
        id              = $values['id']
        title           = $values['title']
        subject         = $values['subject']
        scope           = $values['scope']
        kind            = $values['kind']
        priority        = $values['priority']
        activation      = $values['activation']
        paths           = $values['paths']
        intents         = $values['intents']
        owner           = $values['owner']
        status          = $values['status']
        summary         = $values['summary']
        linked_skill    = $values['linked_skill']
        enforcement     = $values['enforcement']
        overrideable    = $values['overrideable']
        override_mode   = $values['override_mode']
        overrides       = $values['overrides']
        override_reason = $values['override_reason']
        body            = $bodyText
        file_path       = $relativePath.Replace('\', '/')
        file_name       = [System.IO.Path]::GetFileName($FilePath)
        file_base_name  = $baseName
        kind_dir        = $kindDir
        source_label    = $SourceLabel
        repo_root       = $RepoRoot
        present_fields  = @($values.Keys)
        array_syntax    = $parsed.ArraySyntax
        merged_from_ids = @()
    }
}

function Get-RuleFiles {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $itemsRoot = Resolve-RulesRootPath -BaseRoot $RepoRoot -RelativePath 'rules/items'
    if (-not (Test-Path -LiteralPath $itemsRoot)) {
        return @()
    }

    return @(Get-ChildItem -LiteralPath $itemsRoot -Recurse -File -Filter '*.md' | Sort-Object FullName)
}

function Get-GlobalRulesDiscovery {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [string[]]$ExplicitRoots = @()
    )

    $explicit = @($ExplicitRoots | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { [System.IO.Path]::GetFullPath($_) })
    if ($explicit.Count -gt 0) {
        return [PSCustomObject]@{
            mode         = 'explicit'
            roots        = $explicit
            discovered   = $true
            warning      = ''
            searched     = @()
        }
    }

    $parentRoot = Split-Path -Parent $RepoRoot
    if (-not [string]::IsNullOrWhiteSpace($parentRoot)) {
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $parentRoot 'ai-harness'))
        $candidateItems = Resolve-RulesRootPath -BaseRoot $candidate -RelativePath 'rules/items'
        if (($candidate -ne $RepoRoot) -and (Test-Path -LiteralPath $candidateItems)) {
            return [PSCustomObject]@{
                mode         = 'auto_sibling_ai_harness'
                roots        = @($candidate)
                discovered   = $true
                warning      = ''
                searched     = @($candidateItems)
            }
        }

        return [PSCustomObject]@{
            mode         = 'none'
            roots        = @()
            discovered   = $false
            warning      = ('未发现同级 ai-harness/rules/items，已按空全局规则集处理: {0}' -f $candidateItems)
            searched     = @($candidateItems)
        }
    }

    return [PSCustomObject]@{
        mode         = 'none'
        roots        = @()
        discovered   = $false
        warning      = '无法定位仓库父目录，已按空全局规则集处理。'
        searched     = @()
    }
}

function Get-GlobalRuleFiles {
    param([Parameter(Mandatory = $true)]$Discovery)

    $results = New-Object System.Collections.ArrayList
    foreach ($root in @($Discovery.roots)) {
        $itemsRoot = Resolve-RulesRootPath -BaseRoot $root -RelativePath 'rules/items'
        if (-not (Test-Path -LiteralPath $itemsRoot)) {
            continue
        }

        Get-ChildItem -LiteralPath $itemsRoot -Recurse -File -Filter '*.md' | Sort-Object FullName | ForEach-Object {
            [void]$results.Add([PSCustomObject]@{
                RepoRoot    = $root
                FilePath    = $_.FullName
                SourceLabel = ('global:{0}' -f $root)
            })
        }
    }

    return ,([object[]]$results.ToArray())
}

function Should-ImportAsGlobalRule {
    param([Parameter(Mandatory = $true)]$Rule)

    return ($Rule.scope -ne 'project')
}

function Test-RuleSchema {
    param(
        [Parameter(Mandatory = $true)]$Rule,
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $fieldTypes = @{
        id              = 'string'
        title           = 'string'
        subject         = 'string'
        scope           = 'string'
        kind            = 'string'
        priority        = 'int'
        activation      = 'string'
        paths           = 'array'
        intents         = 'array'
        owner           = 'string'
        status          = 'string'
        summary         = 'string'
        linked_skill    = 'string'
        enforcement     = 'string'
        overrideable    = 'bool'
        override_mode   = 'string'
        overrides       = 'array'
        override_reason = 'string'
    }

    foreach ($field in $script:RequiredRuleFields) {
        if (@($Rule.present_fields) -notcontains $field) {
            Add-RulesError -State $State -Message ("{0}: 缺少字段 {1}" -f $Rule.file_path, $field)
            continue
        }

        $value = $Rule.$field
        $expectedType = $fieldTypes[$field]
        if (($null -eq $value) -and ($expectedType -ne 'array')) {
            Add-RulesError -State $State -Message ("{0}: 字段 {1} 不能为空" -f $Rule.file_path, $field)
            continue
        }

        if ($expectedType -eq 'array') {
            $usedArraySyntax = $false
            if ($Rule.array_syntax.ContainsKey($field)) {
                $usedArraySyntax = [bool]$Rule.array_syntax[$field]
            }

            if (-not $usedArraySyntax) {
                Add-RulesError -State $State -Message ("{0}: 字段 {1} 必须使用数组语法" -f $Rule.file_path, $field)
                continue
            }
        }

        if (-not (Test-RuleFieldType -Value $value -ExpectedType $expectedType)) {
            Add-RulesError -State $State -Message ("{0}: 字段 {1} 类型非法" -f $Rule.file_path, $field)
        }
    }

    if ($script:RuleScopes -notcontains $Rule.scope) {
        Add-RulesError -State $State -Message ("{0}: scope 非法: {1}" -f $Rule.file_path, $Rule.scope)
    }

    if ($script:RuleKinds -notcontains $Rule.kind) {
        Add-RulesError -State $State -Message ("{0}: kind 非法: {1}" -f $Rule.file_path, $Rule.kind)
    }

    if ($script:RuleActivations -notcontains $Rule.activation) {
        Add-RulesError -State $State -Message ("{0}: activation 非法: {1}" -f $Rule.file_path, $Rule.activation)
    }

    if ($script:RuleStatuses -notcontains $Rule.status) {
        Add-RulesError -State $State -Message ("{0}: status 非法: {1}" -f $Rule.file_path, $Rule.status)
    }

    if ($script:RuleEnforcements -notcontains $Rule.enforcement) {
        Add-RulesError -State $State -Message ("{0}: enforcement 非法: {1}" -f $Rule.file_path, $Rule.enforcement)
    }

    if ($script:RuleOverrideModes -notcontains $Rule.override_mode) {
        Add-RulesError -State $State -Message ("{0}: override_mode 非法: {1}" -f $Rule.file_path, $Rule.override_mode)
    }

    if ($Rule.kind_dir -ne $Rule.kind) {
        Add-RulesError -State $State -Message ("{0}: 目录 kind 与 frontmatter kind 不一致" -f $Rule.file_path)
    }

    if (-not (Test-ChineseFileName -BaseName $Rule.file_base_name)) {
        Add-RulesError -State $State -Message ("{0}: 规则文件名必须为中文" -f $Rule.file_path)
    }

    if (($Rule.scope -eq 'path' -or $Rule.activation -eq 'path') -and ((Get-StringArray -Value $Rule.paths).Count -eq 0)) {
        Add-RulesError -State $State -Message ("{0}: scope=path 或 activation=path 时 paths 不能为空" -f $Rule.file_path)
    }

    foreach ($field in $script:RuleArrayFields) {
        foreach ($item in (Get-StringArray -Value $Rule.$field)) {
            if ($item -isnot [string]) {
                Add-RulesError -State $State -Message ("{0}: 字段 {1} 只允许字符串项" -f $Rule.file_path, $field)
                break
            }
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($Rule.linked_skill)) {
        $skillPath = Resolve-RulesRootPath -BaseRoot $RepoRoot -RelativePath ("skills/{0}/SKILL.md" -f $Rule.linked_skill)
        if (-not (Test-Path -LiteralPath $skillPath)) {
            Add-RulesError -State $State -Message ("{0}: linked_skill 目标不存在: {1}" -f $Rule.file_path, $Rule.linked_skill)
        }
    }

    if (((Get-StringArray -Value $Rule.overrides).Count -gt 0) -and [string]::IsNullOrWhiteSpace($Rule.override_reason)) {
        Add-RulesError -State $State -Message ("{0}: overrides 非空时 override_reason 不能为空" -f $Rule.file_path)
    }

    if (($Rule.title -is [string]) -and ($Rule.title.Length -gt 40)) {
        Add-RulesWarning -State $State -Message ("{0}: title 长度超过建议阈值 40" -f $Rule.file_path)
    }

    if (($Rule.summary -is [string]) -and ($Rule.summary.Length -gt 120)) {
        Add-RulesWarning -State $State -Message ("{0}: summary 长度超过建议阈值 120" -f $Rule.file_path)
    }

    if (($Rule.body -is [string]) -and ($Rule.body.Length -gt 4000)) {
        Add-RulesWarning -State $State -Message ("{0}: body 长度超过建议阈值 4000" -f $Rule.file_path)
    }
}

function Resolve-RuleConflicts {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$LocalRules,
        [AllowEmptyCollection()][object[]]$GlobalRules = @(),
        [Parameter(Mandatory = $true)]$State
    )

    $allRules = @($GlobalRules) + @($LocalRules)
    $idMap = @{}
    $candidateMap = @{}
    $suppressedIds = @{}
    $relations = New-Object System.Collections.ArrayList

    foreach ($rule in $allRules) {
        if ($idMap.ContainsKey($rule.id)) {
            Add-RulesError -State $State -Message ("规则 id 重复: {0}" -f $rule.id)
            continue
        }

        $idMap[$rule.id] = $rule
        $candidateMap[$rule.id] = Copy-RuleRecord -Rule $rule
    }

    foreach ($rule in $LocalRules) {
        $effectiveRule = Copy-RuleRecord -Rule $candidateMap[$rule.id]
        foreach ($targetId in (Get-StringArray -Value $rule.overrides)) {
            if (-not $idMap.ContainsKey($targetId)) {
                Add-RulesError -State $State -Message ("{0}: overrides 目标不存在: {1}" -f $rule.file_path, $targetId)
                continue
            }

            $targetRule = $candidateMap[$targetId]
            if (-not [bool]$targetRule.overrideable) {
                Add-RulesError -State $State -Message ("{0}: overrides 命中 overrideable=false 目标: {1}" -f $rule.file_path, $targetId)
                continue
            }

            if ($rule.override_mode -eq 'merge') {
                $effectiveRule = Merge-RuleRecord -BaseRule $targetRule -OverlayRule $effectiveRule
                $candidateMap[$rule.id] = $effectiveRule
            }

            $suppressedIds[$targetId] = $true
            [void]$relations.Add([PSCustomObject]@{
                resolution_kind = 'explicit_override'
                source_id       = $rule.id
                target_id       = $targetId
                override_mode   = $rule.override_mode
                subject         = $rule.subject
                target_source   = $targetRule.source_label
            })
        }
    }

    $subjectMap = @{}
    foreach ($ruleId in $candidateMap.Keys) {
        if ($suppressedIds.ContainsKey($ruleId)) {
            continue
        }

        $rule = $candidateMap[$ruleId]
        $subject = [string]$rule.subject
        if (-not $subjectMap.ContainsKey($subject)) {
            $subjectMap[$subject] = New-Object System.Collections.ArrayList
        }

        [void]$subjectMap[$subject].Add($rule)
    }

    foreach ($subject in $subjectMap.Keys) {
        $group = @($subjectMap[$subject])
        if ($group.Count -le 1) {
            continue
        }

        $scopeWinners = New-Object System.Collections.ArrayList
        foreach ($scopeGroup in ($group | Group-Object -Property scope)) {
            $rulesInScope = @($scopeGroup.Group)
            if ($rulesInScope.Count -eq 1) {
                [void]$scopeWinners.Add($rulesInScope[0])
                continue
            }

            $ordered = @($rulesInScope | Sort-Object -Property @{ Expression = 'priority'; Descending = $true }, @{ Expression = 'id'; Descending = $false })
            $topPriority = [int]$ordered[0].priority
            $topRules = @($ordered | Where-Object { [int]$_.priority -eq $topPriority })
            if ($topRules.Count -gt 1) {
                Add-RulesError -State $State -Message ("subject 冲突且同层同优先级无法消歧: {0} ({1})" -f $subject, (($topRules | ForEach-Object { $_.id }) -join ', '))
                continue
            }

            $winner = $ordered[0]
            [void]$scopeWinners.Add($winner)
            foreach ($loser in @($ordered | Select-Object -Skip 1)) {
                $suppressedIds[$loser.id] = $true
                [void]$relations.Add([PSCustomObject]@{
                    resolution_kind = 'priority'
                    source_id       = $winner.id
                    target_id       = $loser.id
                    override_mode   = 'priority'
                    subject         = $subject
                    target_source   = $loser.source_label
                })
            }
        }

        $remaining = @($scopeWinners | Sort-Object -Property @{ Expression = { Get-ScopeRank -Scope $_.scope } ; Descending = $true }, @{ Expression = 'priority'; Descending = $true })
        if ($remaining.Count -gt 1) {
            Add-RulesError -State $State -Message ("subject 冲突但未显式 overrides: {0} ({1})" -f $subject, (($remaining | ForEach-Object { $_.id }) -join ', '))
        }
    }

    $resolved = @(
        $candidateMap.Keys |
            Where-Object { -not $suppressedIds.ContainsKey($_) } |
            ForEach-Object { $candidateMap[$_] } |
            Sort-Object -Property @{ Expression = { Get-ScopeRank -Scope $_.scope }; Descending = $false }, @{ Expression = 'kind'; Descending = $false }, @{ Expression = 'priority'; Descending = $true }, @{ Expression = 'id'; Descending = $false }
    )

    return [PSCustomObject]@{
        ResolvedRules = $resolved
        Relations     = @($relations)
    }
}

function Get-RulesModel {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [string[]]$GlobalRulesRoots = @()
    )

    $state = New-RulesValidationState
    $discovery = Get-GlobalRulesDiscovery -RepoRoot $RepoRoot -ExplicitRoots $GlobalRulesRoots
    if (-not [string]::IsNullOrWhiteSpace($discovery.warning)) {
        Add-RulesWarning -State $state -Message $discovery.warning
    }

    $localRules = New-Object System.Collections.ArrayList
    foreach ($file in (Get-RuleFiles -RepoRoot $RepoRoot)) {
        try {
            [void]$localRules.Add((ConvertTo-RuleRecord -RepoRoot $RepoRoot -FilePath $file.FullName -SourceLabel 'project'))
        } catch {
            Add-RulesError -State $state -Message $_.Exception.Message
        }
    }

    $globalRules = New-Object System.Collections.ArrayList
    foreach ($descriptor in (Get-GlobalRuleFiles -Discovery $discovery)) {
        try {
            $rule = ConvertTo-RuleRecord -RepoRoot $descriptor.RepoRoot -FilePath $descriptor.FilePath -SourceLabel $descriptor.SourceLabel
            if (Should-ImportAsGlobalRule -Rule $rule) {
                [void]$globalRules.Add($rule)
            } else {
                Add-RulesWarning -State $state -Message ("忽略全局规则根中的 project scope 条目: {0}" -f $rule.file_path)
            }
        } catch {
            Add-RulesError -State $state -Message $_.Exception.Message
        }
    }

    $localRuleArray = @($localRules)
    $globalRuleArray = @($globalRules)
    foreach ($rule in $localRuleArray) {
        Test-RuleSchema -Rule $rule -State $state -RepoRoot $RepoRoot
    }

    foreach ($rule in $globalRuleArray) {
        Test-RuleSchema -Rule $rule -State $state -RepoRoot $rule.repo_root
    }

    $resolvedRules = @()
    $relations = @()
    if ($state.Errors.Count -eq 0) {
        $resolution = Resolve-RuleConflicts -LocalRules $localRuleArray -GlobalRules $globalRuleArray -State $state
        $resolvedRules = @($resolution.ResolvedRules)
        $relations = @($resolution.Relations)
    }

    return [PSCustomObject]@{
        RepoRoot          = $RepoRoot
        LocalRules        = $localRuleArray
        GlobalRules       = $globalRuleArray
        ResolvedRules     = $resolvedRules
        OverrideRelations = $relations
        Errors            = @($state.Errors)
        Warnings          = @($state.Warnings)
        GlobalDiscovery   = [PSCustomObject]@{
            mode       = $discovery.mode
            roots      = @($discovery.roots)
            discovered = [bool]$discovery.discovered
            searched   = @($discovery.searched)
        }
    }
}

function New-RulesIndexJson {
    param([Parameter(Mandatory = $true)]$Model)

    return [ordered]@{
        generated_at_utc = [DateTime]::UtcNow.ToString('o')
        repo_root        = $Model.RepoRoot
        local_rule_count = @($Model.LocalRules).Count
        global_rules     = $Model.GlobalDiscovery
        rules            = @($Model.LocalRules | Sort-Object kind, id | ForEach-Object {
            [ordered]@{
                id            = $_.id
                title         = $_.title
                subject       = $_.subject
                scope         = $_.scope
                kind          = $_.kind
                priority      = $_.priority
                activation    = $_.activation
                paths         = (Get-StringArray -Value $_.paths)
                intents       = (Get-StringArray -Value $_.intents)
                owner         = $_.owner
                status        = $_.status
                summary       = $_.summary
                linked_skill  = $_.linked_skill
                enforcement   = $_.enforcement
                overrideable  = $_.overrideable
                override_mode = $_.override_mode
                overrides     = (Get-StringArray -Value $_.overrides)
                file_path     = $_.file_path
            }
        })
    }
}

function New-RulesResolvedJson {
    param([Parameter(Mandatory = $true)]$Model)

    return [ordered]@{
        generated_at_utc    = [DateTime]::UtcNow.ToString('o')
        repo_root           = $Model.RepoRoot
        global_rules        = $Model.GlobalDiscovery
        global_rule_count   = @($Model.GlobalRules).Count
        local_rule_count    = @($Model.LocalRules).Count
        resolved_rule_count = @($Model.ResolvedRules).Count
        override_relations  = @($Model.OverrideRelations)
        resolved_rules      = @($Model.ResolvedRules | ForEach-Object {
            [ordered]@{
                id              = $_.id
                title           = $_.title
                subject         = $_.subject
                scope           = $_.scope
                kind            = $_.kind
                priority        = $_.priority
                activation      = $_.activation
                paths           = (Get-StringArray -Value $_.paths)
                intents         = (Get-StringArray -Value $_.intents)
                owner           = $_.owner
                status          = $_.status
                summary         = $_.summary
                linked_skill    = $_.linked_skill
                enforcement     = $_.enforcement
                overrideable    = $_.overrideable
                override_mode   = $_.override_mode
                overrides       = (Get-StringArray -Value $_.overrides)
                override_reason = $_.override_reason
                merged_from_ids = (Get-StringArray -Value $_.merged_from_ids)
                file_path       = $_.file_path
                source_label    = $_.source_label
                body            = $_.body
            }
        })
    }
}

function New-RulesIndexMarkdown {
    param([Parameter(Mandatory = $true)]$Model)

    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add('# RULES INDEX')
    [void]$lines.Add('')
    [void]$lines.Add(('- local_rule_count: {0}' -f @($Model.LocalRules).Count))
    [void]$lines.Add(('- global_rules_mode: {0}' -f $Model.GlobalDiscovery.mode))
    [void]$lines.Add(('- warning_count: {0}' -f @($Model.Warnings).Count))
    [void]$lines.Add('')
    [void]$lines.Add('| id | subject | kind | scope | activation | linked_skill | file |')
    [void]$lines.Add('| --- | --- | --- | --- | --- | --- | --- |')
    foreach ($rule in @($Model.LocalRules | Sort-Object kind, id)) {
        [void]$lines.Add(('| {0} | {1} | {2} | {3} | {4} | {5} | {6} |' -f $rule.id, $rule.subject, $rule.kind, $rule.scope, $rule.activation, $rule.linked_skill, $rule.file_path))
    }

    if (@($Model.Warnings).Count -gt 0) {
        [void]$lines.Add('')
        [void]$lines.Add('## Warnings')
        foreach ($warning in @($Model.Warnings)) {
            [void]$lines.Add(('- {0}' -f $warning))
        }
    }

    return ($lines.ToArray() -join "`r`n")
}

function Write-RulesArtifacts {
    param(
        [Parameter(Mandatory = $true)]$Model,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $registryRoot = Resolve-RulesRootPath -BaseRoot $RepoRoot -RelativePath 'rules/registry'
    New-Item -ItemType Directory -Path $registryRoot -Force | Out-Null

    $indexJsonPath = Join-Path $registryRoot 'RULES_INDEX.json'
    $indexMdPath = Join-Path $registryRoot 'RULES_INDEX.md'
    $resolvedJsonPath = Join-Path $registryRoot 'RULES_RESOLVED.json'

    Set-Content -LiteralPath $indexJsonPath -Value ((New-RulesIndexJson -Model $Model) | ConvertTo-Json -Depth 12) -Encoding UTF8
    Set-Content -LiteralPath $indexMdPath -Value (New-RulesIndexMarkdown -Model $Model) -Encoding UTF8
    Set-Content -LiteralPath $resolvedJsonPath -Value ((New-RulesResolvedJson -Model $Model) | ConvertTo-Json -Depth 12) -Encoding UTF8

    return [PSCustomObject]@{
        IndexJsonPath     = $indexJsonPath
        IndexMarkdownPath = $indexMdPath
        ResolvedJsonPath  = $resolvedJsonPath
    }
}
