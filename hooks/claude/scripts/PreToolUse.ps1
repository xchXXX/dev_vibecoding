$ErrorActionPreference = "Stop"
$script:ScriptPathValue = if (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
. (Join-Path (Split-Path -Parent $script:ScriptPathValue) "HookCommon.ps1")

$payload = Read-StdinJson
$allowedTools = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$null = $allowedTools.Add("Bash")
$null = $allowedTools.Add("Write")
$null = $allowedTools.Add("Edit")
$null = $allowedTools.Add("MultiEdit")

$parseError = [string](Get-FieldValue -InputObject $payload -Name "_parse_error")
$toolName = Resolve-ToolName -Payload $payload
$reason = ""
$decision = "allow"
$exitCode = 0

if (-not [string]::IsNullOrWhiteSpace($parseError)) {
    $decision = "block"
    $reason = "stdin_json_parse_error"
    $exitCode = 2
} elseif ([string]::IsNullOrWhiteSpace($toolName)) {
    $decision = "block"
    $reason = "missing_tool_name"
    $exitCode = 2
} elseif (-not $allowedTools.Contains($toolName)) {
    $decision = "block"
    $reason = "tool_not_allowed"
    $exitCode = 2
}

$auditResult = TryWrite-AuditRecord -ScriptPathValue $script:ScriptPathValue -EventName "PreToolUse" -Decision $decision -Reason $reason -Payload $payload
if (-not $auditResult.success) {
    [Console]::Error.WriteLine(("PreToolUse audit warning: {0}" -f $auditResult.error))
}
if ($exitCode -ne 0) {
    [Console]::Error.WriteLine(("PreToolUse blocked: {0}; tool={1}" -f $reason, $toolName))
}
exit $exitCode
