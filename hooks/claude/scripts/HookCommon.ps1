$ErrorActionPreference = "Stop"

function Read-StdinJson {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [ordered]@{}
    }
    try {
        return ($raw | ConvertFrom-Json)
    } catch {
        return [ordered]@{
            _parse_error = $_.Exception.Message
            _raw         = $raw
        }
    }
}

function ConvertTo-NormalizedMap {
    param([object]$InputObject)
    if ($null -eq $InputObject) {
        return $null
    }
    if ($InputObject -is [System.Collections.IDictionary]) {
        $map = [ordered]@{}
        foreach ($key in $InputObject.Keys) {
            $map[$key] = ConvertTo-NormalizedMap -InputObject $InputObject[$key]
        }
        return $map
    }
    if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
        $items = @()
        foreach ($item in $InputObject) {
            $items += ,(ConvertTo-NormalizedMap -InputObject $item)
        }
        return $items
    }
    if ($InputObject -is [pscustomobject]) {
        $map = [ordered]@{}
        foreach ($prop in $InputObject.PSObject.Properties) {
            $map[$prop.Name] = ConvertTo-NormalizedMap -InputObject $prop.Value
        }
        return $map
    }
    return $InputObject
}

function Get-FieldValue {
    param(
        [object]$InputObject,
        [string]$Name
    )
    if ($null -eq $InputObject) { return $null }
    if ($InputObject -is [System.Collections.IDictionary]) {
        return $InputObject[$Name]
    }
    $prop = $InputObject.PSObject.Properties[$Name]
    if ($null -ne $prop) { return $prop.Value }
    return $null
}

function Get-PathValue {
    param(
        [object]$InputObject,
        [string[]]$PathParts
    )
    $current = $InputObject
    foreach ($part in $PathParts) {
        if ($null -eq $current) { return $null }
        $current = Get-FieldValue -InputObject $current -Name $part
    }
    return $current
}

function Get-FirstNonEmptyString {
    param(
        [object]$InputObject,
        [string[][]]$CandidatePaths
    )
    foreach ($pathParts in $CandidatePaths) {
        $value = Get-PathValue -InputObject $InputObject -PathParts $pathParts
        $text = [string]$value
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            return $text
        }
    }
    return ""
}

function Resolve-SessionId {
    param([object]$Payload)
    $candidatePaths = @(
        @("session_id"),
        @("sessionId"),
        @("session", "id"),
        @("session", "session_id"),
        @("data", "session_id"),
        @("data", "sessionId"),
        @("request", "session_id"),
        @("request", "sessionId")
    )
    return (Get-FirstNonEmptyString -InputObject $Payload -CandidatePaths $candidatePaths)
}

function Resolve-ToolName {
    param([object]$Payload)
    $candidatePaths = @(
        @("tool_name"),
        @("toolName"),
        @("tool", "name"),
        @("tool_use", "name"),
        @("toolUse", "name"),
        @("data", "tool_name"),
        @("data", "toolName"),
        @("data", "tool", "name"),
        @("request", "tool_name"),
        @("request", "toolName"),
        @("request", "tool", "name")
    )
    return (Get-FirstNonEmptyString -InputObject $Payload -CandidatePaths $candidatePaths)
}

function Get-CanonicalAuditPayload {
    param([object]$Payload)
    $map = ConvertTo-NormalizedMap -InputObject $Payload
    if (-not ($map -is [System.Collections.IDictionary])) {
        $map = [ordered]@{ payload = $map }
    }
    $sessionId = Resolve-SessionId -Payload $Payload
    $toolName = Resolve-ToolName -Payload $Payload
    if ([string]::IsNullOrWhiteSpace([string](Get-FieldValue -InputObject $map -Name "session_id")) -and -not [string]::IsNullOrWhiteSpace($sessionId)) {
        $map["session_id"] = $sessionId
    }
    if ([string]::IsNullOrWhiteSpace([string](Get-FieldValue -InputObject $map -Name "tool_name")) -and -not [string]::IsNullOrWhiteSpace($toolName)) {
        $map["tool_name"] = $toolName
    }
    return $map
}

function TryWrite-AuditRecord {
    param(
        [string]$ScriptPathValue,
        [string]$EventName,
        [string]$Decision,
        [string]$Reason,
        [object]$Payload
    )
    try {
        if ([string]::IsNullOrWhiteSpace($ScriptPathValue)) {
            throw "script_path_missing"
        }
        $runtimeRoot = Split-Path -Parent (Split-Path -Parent $ScriptPathValue)
        $auditDir = Join-Path $runtimeRoot "audit"
        if (-not (Test-Path -LiteralPath $auditDir)) {
            New-Item -ItemType Directory -Path $auditDir -Force | Out-Null
        }
        $auditPayload = Get-CanonicalAuditPayload -Payload $Payload
        $record = [ordered]@{
            timestamp  = (Get-Date).ToString("o")
            event      = $EventName
            decision   = $Decision
            reason     = $Reason
            session_id = [string](Get-FieldValue -InputObject $auditPayload -Name "session_id")
            tool_name  = [string](Get-FieldValue -InputObject $auditPayload -Name "tool_name")
            pid        = $PID
            payload    = $auditPayload
        }
        $line = $record | ConvertTo-Json -Depth 32 -Compress
        Add-Content -LiteralPath (Join-Path $auditDir "hooks.audit.jsonl") -Value $line -Encoding UTF8
        return [ordered]@{ success = $true; error = "" }
    } catch {
        return [ordered]@{ success = $false; error = $_.Exception.Message }
    }
}
