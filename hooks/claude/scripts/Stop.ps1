$ErrorActionPreference = "Stop"
$script:ScriptPathValue = if (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
. (Join-Path (Split-Path -Parent $script:ScriptPathValue) "HookCommon.ps1")

$payload = Read-StdinJson
$reason = ""
if (-not [string]::IsNullOrWhiteSpace([string](Get-FieldValue -InputObject $payload -Name "_parse_error"))) {
    $reason = "stdin_json_parse_error"
}

$auditResult = TryWrite-AuditRecord -ScriptPathValue $script:ScriptPathValue -EventName "Stop" -Decision "allow" -Reason $reason -Payload $payload
if (-not $auditResult.success) {
    [Console]::Error.WriteLine(("Stop audit warning: {0}" -f $auditResult.error))
}
exit 0
