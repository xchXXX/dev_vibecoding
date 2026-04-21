param()

$ErrorActionPreference = "Stop"

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw "This integration suite requires Windows junction/reparse-point support."
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$TempRoot = Join-Path $env:TEMP ("ai-harness-phase5-tests-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

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

function Assert-Contains {
    param(
        [object]$Collection,
        [string]$ExpectedValue,
        [string]$Message
    )
    if ($Collection -is [string]) {
        if ($Collection -notlike ("*{0}*" -f $ExpectedValue)) {
            throw ("{0} (missing: {1})" -f $Message, $ExpectedValue)
        }
        return
    }
    $values = @($Collection)
    if ($values -notcontains $ExpectedValue) {
        throw ("{0} (missing: {1})" -f $Message, $ExpectedValue)
    }
}

function Get-CompressedJson {
    param([object]$Data)
    return ($Data | ConvertTo-Json -Depth 64 -Compress)
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

function Get-StringSha256 {
    param([string]$Content)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha256.ComputeHash($bytes)
    } finally {
        $sha256.Dispose()
    }
    return ([BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
}

function Read-Json {
    param([string]$PathValue)
    return (Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-Json {
    param(
        [string]$PathValue,
        [object]$Data
    )
    Set-Content -LiteralPath $PathValue -Value ($Data | ConvertTo-Json -Depth 64) -Encoding UTF8
}

function Get-FileSha256 {
    param([string]$PathValue)
    return (Get-FileHash -LiteralPath $PathValue -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-DoctorHooksHashFromRuntimeSettings {
    param([string]$RuntimeSettingsPath)
    $raw = Get-Content -LiteralPath $RuntimeSettingsPath -Raw -Encoding UTF8
    $normalized = ConvertTo-NormalizedMap -InputObject ($raw | ConvertFrom-Json)
    return Get-StringSha256 -Content (Get-CompressedJson -Data $normalized["hooks"])
}

function Invoke-PowerShellFile {
    param(
        [string]$FilePath,
        [object[]]$Arguments = @(),
        [hashtable]$Environment = @{}
    )
    $restores = @{}
    foreach ($key in $Environment.Keys) {
        $restores[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
        [Environment]::SetEnvironmentVariable($key, [string]$Environment[$key], "Process")
    }
    try {
        $stdoutPath = Join-Path $TempRoot ([guid]::NewGuid().ToString("N") + ".stdout.log")
        $stderrPath = Join-Path $TempRoot ([guid]::NewGuid().ToString("N") + ".stderr.log")
        $quotedArguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $FilePath)
        $quotedArguments += $Arguments
        $argumentLine = ($quotedArguments | ForEach-Object {
            $value = [string]$_
            if ($value -match '[\s"]') {
                '"' + ($value -replace '"', '\"') + '"'
            } else {
                $value
            }
        }) -join " "
        $process = Start-Process -FilePath (Get-Command powershell.exe).Source -ArgumentList $argumentLine -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        $output = @()
        if (Test-Path -LiteralPath $stdoutPath) {
            $output += @(Get-Content -LiteralPath $stdoutPath -Encoding UTF8)
        }
        if (Test-Path -LiteralPath $stderrPath) {
            $output += @(Get-Content -LiteralPath $stderrPath -Encoding UTF8)
        }
        return [PSCustomObject]@{
            ExitCode = $process.ExitCode
            Lines    = $output
            Text     = ($output -join "`n")
        }
    } finally {
        foreach ($path in @($stdoutPath, $stderrPath)) {
            if ($path -and (Test-Path -LiteralPath $path)) {
                Remove-Item -LiteralPath $path -Force
            }
        }
        foreach ($key in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable($key, $restores[$key], "Process")
        }
    }
}

function Invoke-PowerShellFileWithStdin {
    param(
        [string]$FilePath,
        [string]$StdinText = "",
        [object[]]$Arguments = @()
    )
    $stdoutPath = Join-Path $TempRoot ([guid]::NewGuid().ToString("N") + ".stdout.log")
    $stderrPath = Join-Path $TempRoot ([guid]::NewGuid().ToString("N") + ".stderr.log")
    $quotedArguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $FilePath)
    $quotedArguments += $Arguments
    $argumentLine = ($quotedArguments | ForEach-Object {
        $value = [string]$_
        if ($value -match '[\s"]') {
            '"' + ($value -replace '"', '\"') + '"'
        } else {
            $value
        }
    }) -join " "

    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = (Get-Command powershell.exe).Source
    $processInfo.Arguments = $argumentLine
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $processInfo
    try {
        $null = $process.Start()
        if ($null -ne $StdinText) {
            $process.StandardInput.Write($StdinText)
        }
        $process.StandardInput.Close()
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        Set-Content -LiteralPath $stdoutPath -Value $stdout -Encoding UTF8
        Set-Content -LiteralPath $stderrPath -Value $stderr -Encoding UTF8
        return [PSCustomObject]@{
            ExitCode = $process.ExitCode
            StdOut   = $stdout
            StdErr   = $stderr
        }
    } finally {
        $process.Dispose()
        foreach ($path in @($stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Force
            }
        }
    }
}

function New-Scenario {
    param([string]$Name)
    $scenarioRoot = Join-Path $TempRoot $Name
    $harnessPath = Join-Path $scenarioRoot "harness"
    Copy-Item -LiteralPath $HarnessRoot -Destination $harnessPath -Recurse -Force
    $claudeHomePath = Join-Path $scenarioRoot "claude-home"
    return [PSCustomObject]@{
        Root        = $scenarioRoot
        HarnessPath = $harnessPath
        ClaudeHome  = $claudeHomePath
    }
}

function Get-ScriptPaths {
    param([object]$Scenario)
    return [PSCustomObject]@{
        Install = Join-Path $Scenario.HarnessPath "scripts\install-claude-hooks.ps1"
        Sync    = Join-Path $Scenario.HarnessPath "scripts\sync-claude-hooks.ps1"
        Doctor  = Join-Path $Scenario.HarnessPath "scripts\doctor-core.ps1"
    }
}

function Get-ClaudePaths {
    param([string]$ClaudeHomePath)
    $runtimeRoot = Join-Path $ClaudeHomePath ".ai-harness\hooks\claude"
    return [PSCustomObject]@{
        ClaudeHome      = $ClaudeHomePath
        RuntimeRoot     = $runtimeRoot
        SettingsPath    = Join-Path $ClaudeHomePath "settings.json"
        ReceiptPath     = Join-Path $ClaudeHomePath ".ai-harness\claude-hooks.receipt.json"
        RuntimeSettings = Join-Path $runtimeRoot "settings.runtime.json"
        HookCommonPath  = Join-Path $runtimeRoot "scripts\HookCommon.ps1"
        SessionPath     = Join-Path $runtimeRoot "scripts\session_start.ps1"
    }
}

function Install-ClaudeHooks {
    param(
        [object]$Scenario,
        [string]$ClaudeHomeOverride = ""
    )
    $scripts = Get-ScriptPaths -Scenario $Scenario
    $claudeHome = if ([string]::IsNullOrWhiteSpace($ClaudeHomeOverride)) { $Scenario.ClaudeHome } else { $ClaudeHomeOverride }
    return Invoke-PowerShellFile -FilePath $scripts.Install -Arguments @("-ClaudeHome", $claudeHome, "-Json")
}

function Sync-ClaudeHooks {
    param(
        [object]$Scenario,
        [object[]]$ExtraArguments = @(),
        [hashtable]$Environment = @{},
        [string]$HarnessRootOverride = "",
        [string]$ClaudeHomeOverride = ""
    )
    $scripts = Get-ScriptPaths -Scenario $Scenario
    $claudeHome = if ([string]::IsNullOrWhiteSpace($ClaudeHomeOverride)) { $Scenario.ClaudeHome } else { $ClaudeHomeOverride }
    $arguments = @("-ClaudeHome", $claudeHome)
    if (-not [string]::IsNullOrWhiteSpace($HarnessRootOverride)) {
        $arguments += @("-HarnessRoot", $HarnessRootOverride)
    }
    $arguments += $ExtraArguments
    return Invoke-PowerShellFile -FilePath $scripts.Sync -Arguments $arguments -Environment $Environment
}

function Invoke-Doctor {
    param(
        [object]$Scenario,
        [string]$ClaudeHomeOverride = ""
    )
    $scripts = Get-ScriptPaths -Scenario $Scenario
    $claudeHome = if ([string]::IsNullOrWhiteSpace($ClaudeHomeOverride)) { $Scenario.ClaudeHome } else { $ClaudeHomeOverride }
    $result = Invoke-PowerShellFile -FilePath $scripts.Doctor -Arguments @("-ClaudeHome", $claudeHome, "-Json")
    return [PSCustomObject]@{
        ExitCode = $result.ExitCode
        Json     = ($result.Text | ConvertFrom-Json)
        Text     = $result.Text
    }
}

function New-Junction {
    param(
        [string]$PathValue,
        [string]$TargetPath
    )
    if (Test-Path -LiteralPath $PathValue) {
        Remove-Item -LiteralPath $PathValue -Recurse -Force
    }
    New-Item -ItemType Junction -Path $PathValue -Target $TargetPath | Out-Null
}

function Update-CommandPathAndReceipt {
    param(
        [string]$ClaudeHomePath,
        [string]$EventName,
        [string]$CommandPath
    )
    $paths = Get-ClaudePaths -ClaudeHomePath $ClaudeHomePath
    $runtimeSettings = Read-Json -PathValue $paths.RuntimeSettings
    $settings = Read-Json -PathValue $paths.SettingsPath
    $commandText = ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $CommandPath)
    $runtimeSettings.hooks.$EventName[0].hooks[0].command = $commandText
    $settings.hooks.$EventName[0].hooks[0].command = $commandText
    Write-Json -PathValue $paths.RuntimeSettings -Data $runtimeSettings
    Write-Json -PathValue $paths.SettingsPath -Data $settings

    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.settings.managed_hooks_sha256 = Get-DoctorHooksHashFromRuntimeSettings -RuntimeSettingsPath $paths.RuntimeSettings
    foreach ($managedFile in @($receipt.managed_files)) {
        if ($managedFile.target -eq "settings.runtime.json") {
            $managedFile.sha256 = Get-FileSha256 -PathValue $paths.RuntimeSettings
        }
    }
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
}

function Get-AllowedEventNames {
    return @("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SubagentStop")
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

Run-TestCase -Name "HarnessRoot junction sync succeeds" -Body {
    $scenario = New-Scenario -Name "positive-harness-root-junction"
    $aliasHarness = Join-Path $scenario.Root "harness-link"
    New-Junction -PathValue $aliasHarness -TargetPath $scenario.HarnessPath
    $result = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json") -HarnessRootOverride $aliasHarness
    Assert-Equal 0 $result.ExitCode "sync should succeed when HarnessRoot is a junction path"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    Assert-True (Test-Path -LiteralPath $paths.RuntimeRoot) "runtime root should exist"
    Assert-True (Test-Path -LiteralPath $paths.RuntimeSettings) "runtime settings should exist"
    Assert-True (Test-Path -LiteralPath $paths.ReceiptPath) "receipt should exist"
}

Run-TestCase -Name "ClaudeHome junction install and doctor succeed" -Body {
    $scenario = New-Scenario -Name "positive-claude-home-junction"
    $realHome = Join-Path $scenario.Root "real-home"
    New-Item -ItemType Directory -Path $realHome -Force | Out-Null
    $aliasHome = Join-Path $scenario.Root "home-link"
    New-Junction -PathValue $aliasHome -TargetPath $realHome
    $install = Install-ClaudeHooks -Scenario $scenario -ClaudeHomeOverride $aliasHome
    Assert-Equal 0 $install.ExitCode "install should succeed through ClaudeHome junction"
    $paths = Get-ClaudePaths -ClaudeHomePath $aliasHome
    foreach ($required in @(
        "manifest.json",
        "settings.template.json",
        "settings.runtime.json",
        "scripts\HookCommon.ps1",
        "scripts\session_start.ps1",
        "scripts\user_prompt_submit.ps1",
        "scripts\pre_tool_use.ps1",
        "scripts\post_tool_use.ps1",
        "scripts\stop.ps1",
        "scripts\subagent_stop.ps1")) {
        Assert-True (Test-Path -LiteralPath (Join-Path $paths.RuntimeRoot $required)) ("missing runtime file {0}" -f $required)
    }
    $doctor = Invoke-Doctor -Scenario $scenario -ClaudeHomeOverride $aliasHome
    Assert-Equal 0 $doctor.ExitCode "doctor should succeed through ClaudeHome junction"
    Assert-True ([bool]$doctor.Json.ok) "doctor should report ok=true through ClaudeHome junction"
    $issues = @($doctor.Json.claude_hooks_audit.receipt_issues | ForEach-Object { $_.type })
    Assert-True ($issues -notcontains "receipt_runtime_root_mismatch") "doctor must not report receipt_runtime_root_mismatch"
    Assert-True ($issues -notcontains "receipt_target_out_of_runtime_root") "doctor must not report receipt_target_out_of_runtime_root"
    $commandIssues = @($doctor.Json.claude_hooks_audit.command_path_issues | ForEach-Object { $_.issue })
    Assert-True ($commandIssues -notcontains "command_file_outside_runtime_root") "doctor must not report command_file_outside_runtime_root"
}

Run-TestCase -Name "Doctor accepts junction alias to expected runtime script" -Body {
    $scenario = New-Scenario -Name "positive-command-alias"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $aliasScripts = Join-Path $paths.RuntimeRoot "scripts-alias"
    New-Junction -PathValue $aliasScripts -TargetPath (Join-Path $paths.RuntimeRoot "scripts")
    $aliasCommandPath = Join-Path $aliasScripts "session_start.ps1"
    Update-CommandPathAndReceipt -ClaudeHomePath $scenario.ClaudeHome -EventName "SessionStart" -CommandPath $aliasCommandPath
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Equal 0 $doctor.ExitCode "doctor should succeed for canonical alias command path"
    Assert-True ([bool]$doctor.Json.ok) "doctor should accept canonical alias command path"
    $commandIssues = @($doctor.Json.claude_hooks_audit.command_path_issues | ForEach-Object { $_.issue })
    Assert-True ($commandIssues.Count -eq 0) "doctor should not report command path issues for canonical alias path"
}

Run-TestCase -Name "Manifest source internal junction is accepted" -Body {
    $scenario = New-Scenario -Name "manifest-source-internal-junction"
    $internalAlias = Join-Path $scenario.HarnessPath "hooks\claude\linked-in"
    New-Junction -PathValue $internalAlias -TargetPath (Join-Path $scenario.HarnessPath "hooks\claude\scripts")
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.items[0].source = "hooks/claude/linked-in/SessionStart.ps1"
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-Equal 0 $sync.ExitCode "sync should accept manifest source through internal junction"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Equal 0 $doctor.ExitCode "doctor should accept manifest source through internal junction"
    Assert-True ([bool]$doctor.Json.ok) "doctor should report ok=true for internal manifest source alias"
    $sourceIssueTypes = @($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })
    Assert-True ($sourceIssueTypes -notcontains "source_manifest_source_out_of_root") "doctor must not report source out-of-root for internal junction"
    $missingSourceScriptIds = @($doctor.Json.claude_hooks_audit.missing_source_scripts | ForEach-Object { $_.id })
    Assert-True ($missingSourceScriptIds -notcontains "SessionStart") "missing_source_scripts must not include SessionStart"
}

Run-TestCase -Name "Doctor rejects in-root non-expected runtime command path" -Body {
    $scenario = New-Scenario -Name "doctor-in-root-wrong-script"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $wrongPath = Join-Path $paths.RuntimeRoot "scripts\stop.ps1"
    Update-CommandPathAndReceipt -ClaudeHomePath $scenario.ClaudeHome -EventName "SessionStart" -CommandPath $wrongPath
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should reject in-root wrong script path"
    $mismatch = @($doctor.Json.claude_hooks_audit.command_path_issues | Where-Object { $_.issue -eq "command_file_path_mismatch" -and $_.event -eq "SessionStart" })
    Assert-True ($mismatch.Count -gt 0) "doctor must report command_file_path_mismatch for SessionStart"
    Assert-Equal $wrongPath $mismatch[0].resolved_path "resolved_path should point to the wrong in-root script"
    Assert-Equal (Join-Path $paths.RuntimeRoot "scripts\session_start.ps1") $mismatch[0].expected_path "expected_path should point to SessionStart script"
    $outsideIssues = @($doctor.Json.claude_hooks_audit.command_path_issues | ForEach-Object { $_.issue })
    Assert-True ($outsideIssues -notcontains "command_file_outside_runtime_root") "doctor must not classify in-root wrong script as outside runtime root"
}

Run-TestCase -Name "Doctor rejects internal alias to wrong runtime script" -Body {
    $scenario = New-Scenario -Name "doctor-internal-alias-wrong-script"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $wrongAlias = Join-Path $paths.RuntimeRoot "scripts-alias-wrong"
    New-Junction -PathValue $wrongAlias -TargetPath (Join-Path $paths.RuntimeRoot "scripts")
    $wrongAliasPath = Join-Path $wrongAlias "stop.ps1"
    Update-CommandPathAndReceipt -ClaudeHomePath $scenario.ClaudeHome -EventName "SessionStart" -CommandPath $wrongAliasPath
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should reject alias to wrong runtime script"
    $issueTypes = @($doctor.Json.claude_hooks_audit.command_path_issues | ForEach-Object { $_.issue })
    Assert-Contains $issueTypes "command_file_path_mismatch" "doctor must report path mismatch for alias to wrong script"
    Assert-True ($issueTypes -notcontains "command_file_outside_runtime_root") "doctor must not classify internal alias to wrong script as outside runtime root"
}

Run-TestCase -Name "Manifest source dotdot escape is rejected" -Body {
    $scenario = New-Scenario -Name "negative-source-dotdot"
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.items[0].source = "..\outside.ps1"
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail for source dotdot escape"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail for source dotdot escape"
    Assert-Contains (@($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })) "source_manifest_source_out_of_root" "doctor must report source out-of-root"
}

Run-TestCase -Name "Manifest source junction escape is rejected" -Body {
    $scenario = New-Scenario -Name "negative-source-junction"
    $outside = Join-Path $scenario.Root "outside-source"
    New-Item -ItemType Directory -Path $outside -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $outside "evil.ps1") -Value "Write-Output 'evil'" -Encoding UTF8
    New-Junction -PathValue (Join-Path $scenario.HarnessPath "hooks\claude\linked-out") -TargetPath $outside
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.items[0].source = "hooks/claude/linked-out/evil.ps1"
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail for source junction escape"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })) "source_manifest_source_out_of_root" "doctor must report source junction out-of-root"
}

Run-TestCase -Name "Runtime command absolute outside path is rejected" -Body {
    $scenario = New-Scenario -Name "negative-command-absolute-outside"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $outsideScript = Join-Path $scenario.Root "outside.ps1"
    Set-Content -LiteralPath $outsideScript -Value "Write-Output 'outside'" -Encoding UTF8
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $runtimeSettings = Read-Json -PathValue $paths.RuntimeSettings
    $runtimeSettings.hooks.SessionStart[0].hooks[0].command = ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $outsideScript)
    Write-Json -PathValue $paths.RuntimeSettings -Data $runtimeSettings
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.command_path_issues | ForEach-Object { $_.issue })) "command_file_outside_runtime_root" "doctor must report command outside runtime root"
}

Run-TestCase -Name "Runtime command junction escape is rejected" -Body {
    $scenario = New-Scenario -Name "negative-command-junction-outside"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $outsideDir = Join-Path $scenario.Root "outside-runtime"
    New-Item -ItemType Directory -Path $outsideDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $outsideDir "evil.ps1") -Value "Write-Output 'outside'" -Encoding UTF8
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $linkPath = Join-Path $paths.RuntimeRoot "linked-out"
    New-Junction -PathValue $linkPath -TargetPath $outsideDir
    $runtimeSettings = Read-Json -PathValue $paths.RuntimeSettings
    $runtimeSettings.hooks.SessionStart[0].hooks[0].command = ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $linkPath "evil.ps1"))
    Write-Json -PathValue $paths.RuntimeSettings -Data $runtimeSettings
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.command_path_issues | ForEach-Object { $_.issue })) "command_file_outside_runtime_root" "doctor must report junction escape outside runtime root"
}

Run-TestCase -Name "Invalid target value is rejected" -Body {
    $scenario = New-Scenario -Name "negative-target-invalid"
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.items[0].target = "custom/foo"
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail for invalid target"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })) "source_manifest_invalid_target" "doctor must report invalid target"
}

Run-TestCase -Name "Cross-event target mismatch is rejected" -Body {
    $scenario = New-Scenario -Name "negative-target-cross-event"
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.items[0].target = "user_prompt_submit"
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail for cross-event target mismatch"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })) "source_manifest_invalid_target" "doctor must report cross-event target mismatch"
}

Run-TestCase -Name "Manifest missing event is rejected by sync and doctor" -Body {
    $scenario = New-Scenario -Name "manifest-missing-event"
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.items = @($manifest.items | Where-Object { $_.id -ne "Stop" })
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail when manifest misses Stop"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when manifest misses Stop"
    $missingStop = @($doctor.Json.claude_hooks_audit.source_issues | Where-Object { $_.type -eq "source_manifest_missing_event" -and $_.event -eq "Stop" })
    Assert-True ($missingStop.Count -gt 0) "doctor must report source_manifest_missing_event for Stop"
}

Run-TestCase -Name "Manifest duplicate event is rejected by sync and doctor" -Body {
    $scenario = New-Scenario -Name "manifest-duplicate-event"
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.items += $manifest.items[0]
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail when manifest duplicates SessionStart"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when manifest duplicates SessionStart"
    $duplicateIssue = @($doctor.Json.claude_hooks_audit.source_issues | Where-Object { $_.type -eq "source_manifest_duplicate_id" -and $_.id -eq "SessionStart" })
    Assert-True ($duplicateIssue.Count -gt 0) "doctor must report duplicate SessionStart"
}

Run-TestCase -Name "Staged commit rolls back on settings-stage failure" -Body {
    $scenario = New-Scenario -Name "rollback-settings"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    Add-Content -LiteralPath (Join-Path $scenario.HarnessPath "hooks\claude\scripts\SessionStart.ps1") -Value "`n# settings rollback test" -Encoding UTF8
    $runtimeHashBefore = Get-FileSha256 -PathValue $paths.SessionPath
    $settingsHashBefore = Get-FileSha256 -PathValue $paths.SettingsPath
    $receiptHashBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-Json") -Environment @{ AI_HARNESS_TEST_FAIL_STAGE = "settings" }
    Assert-True ($sync.ExitCode -ne 0) "sync should fail at injected settings stage"
    Assert-Equal $runtimeHashBefore (Get-FileSha256 -PathValue $paths.SessionPath) "runtime script should roll back on settings-stage failure"
    Assert-Equal $settingsHashBefore (Get-FileSha256 -PathValue $paths.SettingsPath) "settings.json should roll back on settings-stage failure"
    Assert-Equal $receiptHashBefore (Get-FileSha256 -PathValue $paths.ReceiptPath) "receipt should roll back on settings-stage failure"
}

Run-TestCase -Name "Staged commit rolls back on receipt-stage failure" -Body {
    $scenario = New-Scenario -Name "rollback-receipt"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    Add-Content -LiteralPath (Join-Path $scenario.HarnessPath "hooks\claude\scripts\SessionStart.ps1") -Value "`n# receipt rollback test" -Encoding UTF8
    $runtimeHashBefore = Get-FileSha256 -PathValue $paths.SessionPath
    $settingsHashBefore = Get-FileSha256 -PathValue $paths.SettingsPath
    $receiptHashBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-Json") -Environment @{ AI_HARNESS_TEST_FAIL_STAGE = "receipt" }
    Assert-True ($sync.ExitCode -ne 0) "sync should fail at injected receipt stage"
    Assert-Equal $runtimeHashBefore (Get-FileSha256 -PathValue $paths.SessionPath) "runtime script should roll back on receipt-stage failure"
    Assert-Equal $settingsHashBefore (Get-FileSha256 -PathValue $paths.SettingsPath) "settings.json should roll back on receipt-stage failure"
    Assert-Equal $receiptHashBefore (Get-FileSha256 -PathValue $paths.ReceiptPath) "receipt should roll back on receipt-stage failure"
}

Run-TestCase -Name "Untrusted receipt blocks runtime tracked update" -Body {
    $scenario = New-Scenario -Name "untrusted-receipt-runtime-update"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    Add-Content -LiteralPath (Join-Path $scenario.HarnessPath "hooks\claude\scripts\SessionStart.ps1") -Value "`n# runtime tracked update should be blocked" -Encoding UTF8
    $runtimeHashBefore = Get-FileSha256 -PathValue $paths.SessionPath
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.harness_root = "C:\foreign\root"
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should block runtime update when receipt is untrusted"
    Assert-Equal $runtimeHashBefore (Get-FileSha256 -PathValue $paths.SessionPath) "runtime file should stay unchanged under untrusted receipt"
}

Run-TestCase -Name "Untrusted receipt blocks stale delete" -Body {
    $scenario = New-Scenario -Name "untrusted-receipt-stale-delete"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $stalePath = Join-Path $paths.RuntimeRoot "scripts\stale.ps1"
    Set-Content -LiteralPath $stalePath -Value "Write-Output 'stale'" -Encoding UTF8
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.managed_files += [pscustomobject]@{
        id = "stale"
        kind = "script"
        source = "generated:test"
        target = "scripts/stale.ps1"
        sha256 = (Get-FileSha256 -PathValue $stalePath)
    }
    $receipt.harness_root = "C:\foreign\root"
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should block stale delete when receipt is untrusted"
    Assert-True (Test-Path -LiteralPath $stalePath) "stale file must remain under untrusted receipt"
}

Run-TestCase -Name "Untrusted receipt blocks top-level hooks takeover" -Body {
    $scenario = New-Scenario -Name "untrusted-receipt-hooks-takeover"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.harness_root = "C:\foreign\root"
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $settings = Read-Json -PathValue $paths.SettingsPath
    $settings.hooks.SessionStart[0].hooks[0].command = "powershell -File C:\foreign\evil.ps1"
    Write-Json -PathValue $paths.SettingsPath -Data $settings
    $settingsHashBefore = Get-FileSha256 -PathValue $paths.SettingsPath
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should block hooks takeover when receipt is untrusted"
    Assert-Equal $settingsHashBefore (Get-FileSha256 -PathValue $paths.SettingsPath) "settings.json must remain unchanged after blocked takeover"
}

Run-TestCase -Name "Trusted receipt deletes stale managed file" -Body {
    $scenario = New-Scenario -Name "trusted-receipt-stale-delete"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $stalePath = Join-Path $paths.RuntimeRoot "scripts\stale.ps1"
    Set-Content -LiteralPath $stalePath -Value "Write-Output 'stale'" -Encoding UTF8
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.managed_files += [pscustomobject]@{
        id = "stale"
        kind = "script"
        source = "generated:test"
        target = "scripts/stale.ps1"
        sha256 = (Get-FileSha256 -PathValue $stalePath)
    }
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-Json")
    Assert-Equal 0 $sync.ExitCode "sync should delete stale managed file with trusted receipt"
    Assert-True (-not (Test-Path -LiteralPath $stalePath)) "trusted stale file should be removed"
}

Run-TestCase -Name "Trusted receipt restores missing hooks" -Body {
    $scenario = New-Scenario -Name "trusted-receipt-hooks-update"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $settings = Read-Json -PathValue $paths.SettingsPath
    $settings.PSObject.Properties.Remove("hooks")
    Write-Json -PathValue $paths.SettingsPath -Data $settings
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-Json")
    Assert-Equal 0 $sync.ExitCode "sync should restore missing hooks with trusted receipt"
    $restoredSettings = Read-Json -PathValue $paths.SettingsPath
    Assert-True ($null -ne $restoredSettings.hooks) "hooks should be restored"
}

Run-TestCase -Name "Doctor default output stays hooks-only mode" -Body {
    $scenario = New-Scenario -Name "doctor-default-hooks-only"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Equal 0 $doctor.ExitCode "doctor default output should succeed"
    Assert-Equal "claude_hooks" $doctor.Json.mode "doctor default mode should stay hooks-only"
    Assert-True ($null -ne $doctor.Json.claude_hooks_audit) "doctor default output should contain claude_hooks_audit"
    Assert-True (-not ($doctor.Json.PSObject.Properties.Name -contains "repo_audit")) "doctor default output must not contain repo_audit"
    Assert-Equal $scenario.HarnessPath $doctor.Json.root "doctor default root should resolve to harness root"
}

Run-TestCase -Name "Runtime settings and receipt keep phase5 hook structure" -Body {
    $scenario = New-Scenario -Name "phase5-hook-structure"
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-Equal 0 $sync.ExitCode "sync should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    $runtimeSettings = Read-Json -PathValue $paths.RuntimeSettings
    $userSettings = Read-Json -PathValue $paths.SettingsPath
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $expectedEvents = Get-AllowedEventNames
    $runtimeEvents = @($runtimeSettings.hooks.PSObject.Properties.Name)
    $userEvents = @($userSettings.hooks.PSObject.Properties.Name)
    Assert-Equal 6 $runtimeEvents.Count "runtime hooks should contain exactly six events"
    Assert-Equal 6 $userEvents.Count "user hooks should contain exactly six events"
    foreach ($eventName in $expectedEvents) {
        Assert-Contains $runtimeEvents $eventName "runtime hooks must contain all phase5 events"
        Assert-Contains $userEvents $eventName "user hooks must contain all phase5 events"
    }
    foreach ($eventName in @("PreToolUse", "PostToolUse")) {
        Assert-Equal "^(Bash|Write|Edit|MultiEdit)$" $runtimeSettings.hooks.$eventName[0].matcher "runtime matcher must match phase5 contract"
        Assert-Equal "^(Bash|Write|Edit|MultiEdit)$" $userSettings.hooks.$eventName[0].matcher "user matcher must match phase5 contract"
    }
    foreach ($hooksRoot in @($runtimeSettings.hooks, $userSettings.hooks)) {
        foreach ($eventName in $expectedEvents) {
            foreach ($entry in @($hooksRoot.$eventName)) {
                foreach ($handler in @($entry.hooks)) {
                    Assert-Equal "command" $handler.type "handler type must stay command"
                    Assert-Equal "powershell" $handler.shell "handler shell must stay powershell"
                }
            }
        }
    }
    Assert-Equal "hooks" $receipt.settings.managed_top_level "receipt must manage top-level hooks"
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$receipt.settings.managed_hooks_sha256)) "receipt managed_hooks_sha256 must be non-empty"
    $managedTargets = @($receipt.managed_files | ForEach-Object { $_.target })
    Assert-Contains $managedTargets "scripts/HookCommon.ps1" "receipt managed_files must contain HookCommon"
    Assert-Contains $managedTargets "scripts/session_start.ps1" "receipt managed_files must contain SessionStart"
    Assert-Contains $managedTargets "scripts/user_prompt_submit.ps1" "receipt managed_files must contain UserPromptSubmit"
    Assert-Contains $managedTargets "scripts/pre_tool_use.ps1" "receipt managed_files must contain PreToolUse"
    Assert-Contains $managedTargets "scripts/post_tool_use.ps1" "receipt managed_files must contain PostToolUse"
    Assert-Contains $managedTargets "scripts/stop.ps1" "receipt managed_files must contain Stop"
    Assert-Contains $managedTargets "scripts/subagent_stop.ps1" "receipt managed_files must contain SubagentStop"
}

Run-TestCase -Name "Six-event freeze rejects unknown event" -Body {
    $scenario = New-Scenario -Name "freeze-unknown-event"
    $settingsTemplatePath = Join-Path $scenario.HarnessPath "hooks\claude\settings.json"
    $template = Read-Json -PathValue $settingsTemplatePath
    $template.hooks | Add-Member -NotePropertyName Notification -NotePropertyValue @(@{ hooks = @(@{ type = "command"; shell = "powershell"; command = "pwsh -File hooks/claude/scripts/SessionStart.ps1" }) }) -Force
    Write-Json -PathValue $settingsTemplatePath -Data $template
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail for unknown hook event"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })) "unknown_event" "doctor must report unknown_event"
}

Run-TestCase -Name "Manifest runtime freeze rejects drift" -Body {
    $scenario = New-Scenario -Name "freeze-runtime"
    $manifestPath = Join-Path $scenario.HarnessPath "hooks\claude\manifest.json"
    $manifest = Read-Json -PathValue $manifestPath
    $manifest.runtime = "other-runtime"
    Write-Json -PathValue $manifestPath -Data $manifest
    $sync = Sync-ClaudeHooks -Scenario $scenario -ExtraArguments @("-AllowBootstrap", "-Json")
    Assert-True ($sync.ExitCode -ne 0) "sync should fail when manifest runtime drifts"
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })) "source_manifest_runtime_mismatch" "doctor must report manifest runtime mismatch"
}

Run-TestCase -Name "PreToolUse guard marker remains enforced" -Body {
    $scenario = New-Scenario -Name "pretool-guard-marker"
    $preToolPath = Join-Path $scenario.HarnessPath "hooks\claude\scripts\PreToolUse.ps1"
    $content = Get-Content -LiteralPath $preToolPath -Raw -Encoding UTF8
    $content = $content -replace "tool_not_allowed", "tool_not_allowx"
    Set-Content -LiteralPath $preToolPath -Value $content -Encoding UTF8
    $doctor = Invoke-Doctor -Scenario $scenario
    Assert-Contains (@($doctor.Json.claude_hooks_audit.source_issues | ForEach-Object { $_.type })) "pre_tool_use_guard_marker_missing" "doctor must report missing PreToolUse guard marker"
}

Run-TestCase -Name "PreToolUse allows whitelisted tool payload" -Body {
    $scenario = New-Scenario -Name "pretool-allows-whitelisted"
    $preToolPath = Join-Path $scenario.HarnessPath "hooks\claude\scripts\PreToolUse.ps1"
    $result = Invoke-PowerShellFileWithStdin -FilePath $preToolPath -StdinText '{"tool_name":"Bash","session_id":"s-1"}'
    Assert-Equal 0 $result.ExitCode "PreToolUse should allow whitelisted tool"
    Assert-True ($result.StdErr -notlike "*PreToolUse blocked:*") "stderr must not contain block message for whitelisted tool"
}

Run-TestCase -Name "PreToolUse blocks invalid stdin json" -Body {
    $scenario = New-Scenario -Name "pretool-invalid-json"
    $preToolPath = Join-Path $scenario.HarnessPath "hooks\claude\scripts\PreToolUse.ps1"
    $result = Invoke-PowerShellFileWithStdin -FilePath $preToolPath -StdinText '{"tool_name":'
    Assert-Equal 2 $result.ExitCode "PreToolUse should block invalid stdin json"
    Assert-Contains $result.StdErr "stdin_json_parse_error" "stderr must contain stdin_json_parse_error"
}

Run-TestCase -Name "PreToolUse blocks payload without tool name" -Body {
    $scenario = New-Scenario -Name "pretool-missing-tool"
    $preToolPath = Join-Path $scenario.HarnessPath "hooks\claude\scripts\PreToolUse.ps1"
    $result = Invoke-PowerShellFileWithStdin -FilePath $preToolPath -StdinText '{"session_id":"s-2"}'
    Assert-Equal 2 $result.ExitCode "PreToolUse should block payload without tool name"
    Assert-Contains $result.StdErr "missing_tool_name" "stderr must contain missing_tool_name"
}

Run-TestCase -Name "PreToolUse blocks non-whitelisted tool" -Body {
    $scenario = New-Scenario -Name "pretool-non-whitelisted"
    $preToolPath = Join-Path $scenario.HarnessPath "hooks\claude\scripts\PreToolUse.ps1"
    $result = Invoke-PowerShellFileWithStdin -FilePath $preToolPath -StdinText '{"toolName":"Read","session_id":"s-3"}'
    Assert-Equal 2 $result.ExitCode "PreToolUse should block non-whitelisted tool"
    Assert-Contains $result.StdErr "tool_not_allowed" "stderr must contain tool_not_allowed"
}

Run-TestCase -Name "Doctor detects HookCommon and runtime script drift" -Body {
    $scenario = New-Scenario -Name "runtime-drift"
    $install = Install-ClaudeHooks -Scenario $scenario
    Assert-Equal 0 $install.ExitCode "install should succeed"
    $paths = Get-ClaudePaths -ClaudeHomePath $scenario.ClaudeHome
    Add-Content -LiteralPath $paths.HookCommonPath -Value "`n# drift" -Encoding UTF8
    Add-Content -LiteralPath $paths.SessionPath -Value "`n# drift" -Encoding UTF8
    $doctor = Invoke-Doctor -Scenario $scenario
    $driftEvents = @($doctor.Json.claude_hooks_audit.runtime_issues | Where-Object { $_.type -eq "runtime_script_drift" } | ForEach-Object { $_.event })
    Assert-Contains $driftEvents "HookCommon" "doctor must report HookCommon runtime drift"
    Assert-Contains $driftEvents "SessionStart" "doctor must report SessionStart runtime drift"
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
