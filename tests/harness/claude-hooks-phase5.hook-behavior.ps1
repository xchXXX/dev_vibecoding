param()

$ErrorActionPreference = "Stop"

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
. (Join-Path $HarnessRoot "hooks\claude\scripts\HookCommon.ps1")

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

function Assert-Equal {
    param(
        [object]$Expected,
        [object]$Actual,
        [string]$Message
    )
    if ($Expected -ne $Actual) {
        throw ("{0} (expected: {1}; actual: {2})" -f $Message, $Expected, $Actual)
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Run-TestCase {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    try {
        & $Body
        $script:PassCount += 1
        Write-Host ("PASS {0}" -f $Name)
    } catch {
        $script:Failures.Add(("{0}: {1}" -f $Name, $_.Exception.Message)) | Out-Null
        Write-Host ("FAIL {0}" -f $Name)
        Write-Host ("  {0}" -f $_.Exception.Message)
    }
}

Run-TestCase -Name "HookCommon resolves compatible session and tool field variants" -Body {
    $samples = @(
        [ordered]@{
            payload = @{ session_id = "s1"; tool_name = "Bash" }
            expectedSession = "s1"
            expectedTool = "Bash"
        },
        [ordered]@{
            payload = @{ sessionId = "s2"; toolName = "Write" }
            expectedSession = "s2"
            expectedTool = "Write"
        },
        [ordered]@{
            payload = @{ session = @{ id = "s3" }; tool = @{ name = "Edit" } }
            expectedSession = "s3"
            expectedTool = "Edit"
        },
        [ordered]@{
            payload = @{ session = @{ session_id = "s4" }; tool_use = @{ name = "MultiEdit" } }
            expectedSession = "s4"
            expectedTool = "MultiEdit"
        },
        [ordered]@{
            payload = @{ data = @{ sessionId = "s5"; toolName = "Bash" } }
            expectedSession = "s5"
            expectedTool = "Bash"
        },
        [ordered]@{
            payload = @{ request = @{ session_id = "s6"; tool = @{ name = "Write" } } }
            expectedSession = "s6"
            expectedTool = "Write"
        }
    )

    foreach ($sample in $samples) {
        $sessionId = Resolve-SessionId -Payload $sample.payload
        $toolName = Resolve-ToolName -Payload $sample.payload
        $canonicalPayload = Get-CanonicalAuditPayload -Payload $sample.payload
        Assert-Equal $sample.expectedSession $sessionId "Resolve-SessionId should return expected session_id"
        Assert-Equal $sample.expectedTool $toolName "Resolve-ToolName should return expected tool_name"
        Assert-True ($canonicalPayload.PSObject.Properties.Name -contains "session_id" -or $canonicalPayload.Contains("session_id")) "canonical payload must expose top-level session_id"
        Assert-True ($canonicalPayload.PSObject.Properties.Name -contains "tool_name" -or $canonicalPayload.Contains("tool_name")) "canonical payload must expose top-level tool_name"
        Assert-Equal $sample.expectedSession ([string](Get-FieldValue -InputObject $canonicalPayload -Name "session_id")) "canonical payload session_id should match expected value"
        Assert-Equal $sample.expectedTool ([string](Get-FieldValue -InputObject $canonicalPayload -Name "tool_name")) "canonical payload tool_name should match expected value"
    }
}

Write-Host ("TOTAL PASS {0}" -f $script:PassCount)
if ($script:Failures.Count -gt 0) {
    Write-Host ("TOTAL FAIL {0}" -f $script:Failures.Count)
    foreach ($failure in $script:Failures) {
        Write-Host ("  {0}" -f $failure)
    }
    exit 1
}

Write-Host "ALL TESTS PASSED"
exit 0
