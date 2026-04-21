param()

$ErrorActionPreference = "Stop"

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw "This Codex integration suite requires Windows."
}

$HarnessRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$TempRoot = Join-Path $env:TEMP ("ai-harness-codex-tests-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:PassCount = 0

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param([object]$Expected, [object]$Actual, [string]$Message)
    if ($Expected -ne $Actual) {
        throw ("{0} (expected: {1}; actual: {2})" -f $Message, $Expected, $Actual)
    }
}

function Assert-Contains {
    param([object]$Collection, [string]$ExpectedValue, [string]$Message)
    $values = @($Collection)
    if ($values -notcontains $ExpectedValue) {
        throw ("{0} (missing: {1})" -f $Message, $ExpectedValue)
    }
}

function Read-Json {
    param([string]$PathValue)
    return (Get-Content -LiteralPath $PathValue -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-Json {
    param([string]$PathValue, [object]$Data)
    Set-Content -LiteralPath $PathValue -Value ($Data | ConvertTo-Json -Depth 64) -Encoding UTF8
}

function Import-ScriptPrefix {
    param(
        [string]$ScriptPath,
        [string]$CutMarker
    )
    $content = Get-Content -LiteralPath $ScriptPath -Raw -Encoding UTF8
    $cutIndex = $content.IndexOf($CutMarker)
    if ($cutIndex -lt 0) {
        throw ("cut marker not found in script: {0}" -f $ScriptPath)
    }
    $prefix = $content.Substring(0, $cutIndex)
    $prefix = $prefix.Replace('$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path', ('$ScriptRoot = ''{0}''' -f (Split-Path -Parent $ScriptPath)))
    return [scriptblock]::Create($prefix)
}

function Get-SyncLockNameForTest {
    param(
        [string]$ScriptPath,
        [string]$CodexHomeValue
    )
    . (Import-ScriptPrefix -ScriptPath $ScriptPath -CutMarker '$HarnessRoot = Normalize-UserPath -PathValue $HarnessRoot')
    return (Get-SyncLockName -CodexHomeValue $CodexHomeValue)
}

function Get-FileSha256 {
    param([string]$PathValue)
    return (Get-FileHash -LiteralPath $PathValue -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-RelativeTreeHashes {
    param([string]$RootPath)
    $map = [ordered]@{}
    if (-not (Test-Path -LiteralPath $RootPath)) {
        return $map
    }
    Get-ChildItem -LiteralPath $RootPath -Recurse -File | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring([System.IO.Path]::GetFullPath($RootPath).Length).TrimStart('\') -replace '\\', '/'
        $map[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $map
}

function Invoke-PowerShellFile {
    param(
        [string]$FilePath,
        [object[]]$Arguments = @(),
        [hashtable]$Environment = @{}
    )
    $stdoutPath = Join-Path $TempRoot ([guid]::NewGuid().ToString("N") + ".stdout.log")
    $stderrPath = Join-Path $TempRoot ([guid]::NewGuid().ToString("N") + ".stderr.log")
    $argumentLine = (@("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $FilePath) + $Arguments | ForEach-Object {
        $value = [string]$_
        if ($value -match '[\s"]') { '"' + ($value -replace '"', '\"') + '"' } else { $value }
    }) -join " "
    $envBackup = @{}
    try {
        foreach ($key in @($Environment.Keys)) {
            $envBackup[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
            [Environment]::SetEnvironmentVariable($key, [string]$Environment[$key], "Process")
        }
        $process = Start-Process -FilePath (Get-Command powershell.exe).Source -ArgumentList $argumentLine -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        $output = @()
        if (Test-Path -LiteralPath $stdoutPath) { $output += @(Get-Content -LiteralPath $stdoutPath -Encoding UTF8) }
        if (Test-Path -LiteralPath $stderrPath) { $output += @(Get-Content -LiteralPath $stderrPath -Encoding UTF8) }
        return [PSCustomObject]@{
            ExitCode = $process.ExitCode
            Text     = ($output -join "`n")
            Lines    = $output
        }
    } finally {
        foreach ($key in @($Environment.Keys)) {
            [Environment]::SetEnvironmentVariable($key, $envBackup[$key], "Process")
        }
        foreach ($path in @($stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Force
            }
        }
    }
}

function Run-TestCase {
    param([string]$Name, [scriptblock]$Body)
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

function Copy-HarnessRoot {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot
    )
    $excludedTopLevelNames = @('.ai', '.tmp', '.tmp-tests')
    New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    Get-ChildItem -LiteralPath $SourceRoot -Force | Where-Object {
        $excludedTopLevelNames -notcontains $_.Name
    } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $DestinationRoot $_.Name) -Recurse -Force
    }
}

function New-Scenario {
    param([string]$Name)
    $scenarioRoot = Join-Path $TempRoot $Name
    $scenarioHarness = Join-Path $scenarioRoot "harness"
    Copy-HarnessRoot -SourceRoot $HarnessRoot -DestinationRoot $scenarioHarness
    return [PSCustomObject]@{
        Root = $scenarioRoot
        Harness = $scenarioHarness
        CodexHome = Join-Path $scenarioRoot "codex-home"
    }
}

function Get-CodexPaths {
    param([object]$Scenario)
    $skillsRoot = Join-Path $Scenario.CodexHome "skills"
    $orchestratorSkillDir = Join-Path $skillsRoot "global-task-orchestrator"
    $failureMemorySkillDir = Join-Path $skillsRoot "command-failure-memory"
    $benchmarkSkillDir = Join-Path $skillsRoot "pre-dev-benchmark"
    return [PSCustomObject]@{
        SkillsRoot = $skillsRoot
        ManagedSkillDir = $orchestratorSkillDir
        OrchestratorSkillDir = $orchestratorSkillDir
        FailureMemorySkillDir = $failureMemorySkillDir
        BenchmarkSkillDir = $benchmarkSkillDir
        ReceiptPath = Join-Path $Scenario.CodexHome ".ai-harness\codex-sync.receipt.json"
        PluginsRoot = Join-Path $Scenario.CodexHome "plugins"
    }
}

function Get-ScriptPaths {
    param([object]$Scenario)
    return [PSCustomObject]@{
        Sync = Join-Path $Scenario.Harness "scripts\sync-codex.ps1"
        Doctor = Join-Path $Scenario.Harness "scripts\doctor-core.ps1"
    }
}

function Invoke-CodexSync {
    param(
        [object]$Scenario,
        [object[]]$ExtraArguments = @(),
        [hashtable]$Environment = @{}
    )
    $scripts = Get-ScriptPaths -Scenario $Scenario
    return Invoke-PowerShellFile -FilePath $scripts.Sync -Arguments (@("-HarnessRoot", $Scenario.Harness, "-CodexHome", $Scenario.CodexHome, "-Json") + $ExtraArguments) -Environment $Environment
}

function Invoke-CodexDoctor {
    param(
        [object]$Scenario,
        [hashtable]$Environment = @{}
    )
    $scripts = Get-ScriptPaths -Scenario $Scenario
    $result = Invoke-PowerShellFile -FilePath $scripts.Doctor -Arguments @("-Root", $Scenario.Harness, "-CodexHome", $Scenario.CodexHome, "-AuditTarget", "codex_minimal", "-Json") -Environment $Environment
    $json = $null
    if (-not [string]::IsNullOrWhiteSpace($result.Text)) {
        try {
            $json = ($result.Text | ConvertFrom-Json)
        } catch {
            $json = $null
        }
    }
    return [PSCustomObject]@{
        ExitCode = $result.ExitCode
        Json = $json
        Text = $result.Text
    }
}

function Get-ManagedIssueTypes {
    param([object]$DoctorJson)
    return @($DoctorJson.codex_audit.source_issues + $DoctorJson.codex_audit.runtime_issues + $DoctorJson.codex_audit.receipt_issues | ForEach-Object { $_.type })
}

Run-TestCase -Name "Sync installs only frozen managed skill and ignores extra source skills" -Body {
    $scenario = New-Scenario -Name "sync-frozen-managed-only"
    $extraSkillPath = Join-Path $scenario.Harness "skills\experimental-skill"
    New-Item -ItemType Directory -Path $extraSkillPath -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $extraSkillPath "SKILL.md") -Value "# experimental" -Encoding UTF8
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    Assert-True (Test-Path -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md")) "managed skill should be installed"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $paths.SkillsRoot "experimental-skill"))) "experimental-skill must not be installed to runtime"
}

Run-TestCase -Name "Sync preserves runtime .system and unmanaged skill directories" -Body {
    $scenario = New-Scenario -Name "sync-preserves-runtime-system"
    $paths = Get-CodexPaths -Scenario $scenario
    foreach ($name in @(".system\openai-docs", "mcp-builder", "Planning_with_files")) {
        $dir = Join-Path $paths.SkillsRoot $name
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $dir "sentinel.txt") -Value $name -Encoding UTF8
    }
    $before = Get-RelativeTreeHashes -RootPath $paths.SkillsRoot
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "sync should succeed"
    $after = Get-RelativeTreeHashes -RootPath $paths.SkillsRoot
    foreach ($key in @(" .system/openai-docs/sentinel.txt","mcp-builder/sentinel.txt","Planning_with_files/sentinel.txt")) { }
    Assert-Equal $before[".system/openai-docs/sentinel.txt"] $after[".system/openai-docs/sentinel.txt"] ".system sentinel must stay unchanged"
    Assert-Equal $before["mcp-builder/sentinel.txt"] $after["mcp-builder/sentinel.txt"] "mcp-builder sentinel must stay unchanged"
    Assert-Equal $before["Planning_with_files/sentinel.txt"] $after["Planning_with_files/sentinel.txt"] "Planning_with_files sentinel must stay unchanged"
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $targets = @($receipt.managed_files | ForEach-Object { $_.target })
    Assert-True ($targets -notcontains ".system/openai-docs/sentinel.txt") "receipt must not include .system skill"
    Assert-True ($targets -notcontains "mcp-builder/sentinel.txt") "receipt must not include unmanaged skill"
}

Run-TestCase -Name "Sync does not touch ~/.codex/plugins while managing skills" -Body {
    $scenario = New-Scenario -Name "sync-preserves-plugins"
    $paths = Get-CodexPaths -Scenario $scenario
    New-Item -ItemType Directory -Path (Join-Path $paths.PluginsRoot "sample-plugin") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $paths.PluginsRoot "marketplace.json") -Value '{ "sentinel": true }' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $paths.PluginsRoot "sample-plugin\plugin.json") -Value '{ "name": "sample" }' -Encoding UTF8
    $before = Get-RelativeTreeHashes -RootPath $paths.PluginsRoot
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "sync should succeed"
    $after = Get-RelativeTreeHashes -RootPath $paths.PluginsRoot
    Assert-Equal $before["marketplace.json"] $after["marketplace.json"] "plugins marketplace must stay unchanged"
    Assert-Equal $before["sample-plugin/plugin.json"] $after["sample-plugin/plugin.json"] "plugin file must stay unchanged"
}

Run-TestCase -Name "Bootstrap install writes managed runtime skill, receipt, and doctor passes" -Body {
    $scenario = New-Scenario -Name "bootstrap-install"
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "bootstrap sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $sourceOrchestratorSkill = Join-Path $scenario.Harness "skills\global-task-orchestrator"
    $sourceFailureMemorySkill = Join-Path $scenario.Harness "skills\command-failure-memory"
    $sourceBenchmarkSkill = Join-Path $scenario.Harness "skills\pre-dev-benchmark"
    foreach ($relative in @("SKILL.md", "agents/openai.yaml", "scripts/bootstrap-task.ps1")) {
        Assert-True (Test-Path -LiteralPath (Join-Path $paths.OrchestratorSkillDir $relative)) ("orchestrator runtime missing {0}" -f $relative)
        Assert-Equal (Get-FileSha256 -PathValue (Join-Path $sourceOrchestratorSkill $relative)) (Get-FileSha256 -PathValue (Join-Path $paths.OrchestratorSkillDir $relative)) ("orchestrator runtime file {0} must match source" -f $relative)
    }
    foreach ($relative in @("SKILL.md", "scripts/command-failure-memory.cmd", "scripts/command-failure-memory.py", "scripts/command-failure-memory.ps1")) {
        Assert-True (Test-Path -LiteralPath (Join-Path $paths.FailureMemorySkillDir $relative)) ("failure-memory runtime missing {0}" -f $relative)
        Assert-Equal (Get-FileSha256 -PathValue (Join-Path $sourceFailureMemorySkill $relative)) (Get-FileSha256 -PathValue (Join-Path $paths.FailureMemorySkillDir $relative)) ("failure-memory runtime file {0} must match source" -f $relative)
    }
    foreach ($relative in @("SKILL.md", "agents/openai.yaml", "references/benchmark-design.md", "assets/benchmark-plan.template.md", "scripts/scaffold_benchmark.py")) {
        Assert-True (Test-Path -LiteralPath (Join-Path $paths.BenchmarkSkillDir $relative)) ("pre-dev-benchmark runtime missing {0}" -f $relative)
        Assert-Equal (Get-FileSha256 -PathValue (Join-Path $sourceBenchmarkSkill $relative)) (Get-FileSha256 -PathValue (Join-Path $paths.BenchmarkSkillDir $relative)) ("pre-dev-benchmark runtime file {0} must match source" -f $relative)
    }
    Assert-True (Test-Path -LiteralPath $paths.ReceiptPath) "receipt must exist"
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    Assert-Contains @($receipt.managed_skills) "global-task-orchestrator" "receipt must list orchestrator skill"
    Assert-Contains @($receipt.managed_skills) "command-failure-memory" "receipt must list failure-memory skill"
    Assert-Contains @($receipt.managed_skills) "pre-dev-benchmark" "receipt must list pre-dev-benchmark skill"
    Assert-True (@($receipt.managed_files | ForEach-Object { $_.target }) -contains "command-failure-memory/scripts/command-failure-memory.cmd") "receipt must track failure-memory launcher"
    Assert-True (@($receipt.managed_files | ForEach-Object { $_.target }) -contains "command-failure-memory/scripts/command-failure-memory.py") "receipt must track failure-memory Python backend"
    Assert-True (@($receipt.managed_files | ForEach-Object { $_.target }) -contains "command-failure-memory/scripts/command-failure-memory.ps1") "receipt must track independent failure-memory script"
    Assert-True (@($receipt.managed_files | ForEach-Object { $_.target }) -contains "pre-dev-benchmark/scripts/scaffold_benchmark.py") "receipt must track pre-dev-benchmark scaffold script"
    Assert-True (@($receipt.managed_files | ForEach-Object { $_.source }) -contains "skills/pre-dev-benchmark/scripts/scaffold_benchmark.py") "receipt must preserve pre-dev-benchmark source path"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-Equal 0 $doctor.ExitCode "codex doctor should succeed after bootstrap"
    Assert-True ([bool]$doctor.Json.ok) "codex doctor should report ok=true after bootstrap"
}

Run-TestCase -Name "Sync still succeeds when native path canonicalization is unavailable but no reparse point is present" -Body {
    $scenario = New-Scenario -Name "sync-native-path-fallback"
    $sync = Invoke-CodexSync -Scenario $scenario -Environment @{ AI_HARNESS_DISABLE_NATIVE_PATH = "1" }
    Assert-Equal 0 $sync.ExitCode "sync should keep working when native path canonicalization is unavailable and no reparse point is traversed"
}

Run-TestCase -Name "Doctor still succeeds when native path canonicalization is unavailable but no reparse point is present" -Body {
    $scenario = New-Scenario -Name "doctor-native-path-fallback"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "bootstrap sync should succeed before doctor fail-closed check"
    $doctor = Invoke-CodexDoctor -Scenario $scenario -Environment @{ AI_HARNESS_DISABLE_NATIVE_PATH = "1" }
    Assert-Equal 0 $doctor.ExitCode "doctor should keep working when native path canonicalization is unavailable and no reparse point is traversed"
    Assert-True ([bool]$doctor.Json.ok) "doctor should still report ok=true under safe fallback mode"
}

Run-TestCase -Name "Concurrent syncs serialize and leave runtime healthy" -Body {
    $scenario = New-Scenario -Name "parallel-sync-lock"
    $scripts = Get-ScriptPaths -Scenario $scenario
    $jobs = @()
    try {
        foreach ($index in 1..4) {
            $jobs += Start-Job -ScriptBlock {
                param($SyncPath, $HarnessPath, $CodexHomePath)
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SyncPath -HarnessRoot $HarnessPath -CodexHome $CodexHomePath -Json | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    throw ("sync worker exited with code {0}" -f $LASTEXITCODE)
                }
            } -ArgumentList $scripts.Sync, $scenario.Harness, $scenario.CodexHome
        }
        $null = Wait-Job -Job $jobs -Timeout 180
        foreach ($job in $jobs) {
            Assert-Equal "Completed" ([string]$job.State) "parallel sync worker should succeed"
        }
    } finally {
        foreach ($job in $jobs) {
            if ($null -ne $job) {
                try {
                    Receive-Job -Job $job -Keep | Out-Null
                } catch {
                }
                Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
            }
        }
    }
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-Equal 0 $doctor.ExitCode "doctor should succeed after parallel sync workers"
    Assert-True ([bool]$doctor.Json.ok) "doctor should report ok=true after parallel sync workers"
}

Run-TestCase -Name "Sync lock name normalizes CodexHome case on Windows" -Body {
    $syncScriptPath = Join-Path $HarnessRoot "scripts\sync-codex.ps1"
    $pathLower = (Join-Path $TempRoot "lock-case\codex-home").ToLowerInvariant()
    $pathUpper = $pathLower.ToUpperInvariant()
    $lowerLock = Get-SyncLockNameForTest -ScriptPath $syncScriptPath -CodexHomeValue $pathLower
    $upperLock = Get-SyncLockNameForTest -ScriptPath $syncScriptPath -CodexHomeValue $pathUpper
    Assert-Equal $lowerLock $upperLock "sync lock name should stay stable across path casing differences on Windows"
}

Run-TestCase -Name "Repeated sync is idempotent when source tree is unchanged" -Body {
    $scenario = New-Scenario -Name "idempotent-sync"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $runtimeHashesBefore = Get-RelativeTreeHashes -RootPath $paths.ManagedSkillDir
    $receiptHashBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    $second = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $second.ExitCode "unchanged sync should succeed"
    $runtimeHashesAfter = Get-RelativeTreeHashes -RootPath $paths.ManagedSkillDir
    $receiptHashAfter = Get-FileSha256 -PathValue $paths.ReceiptPath
    Assert-Equal ($runtimeHashesBefore | ConvertTo-Json -Compress) ($runtimeHashesAfter | ConvertTo-Json -Compress) "runtime hashes must stay unchanged"
    Assert-Equal $receiptHashBefore $receiptHashAfter "receipt hash must stay unchanged on idempotent sync"
}

Run-TestCase -Name "Managed source file change is propagated to runtime and receipt" -Body {
    $scenario = New-Scenario -Name "managed-source-update"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $runtimeSkillMd = Join-Path $paths.ManagedSkillDir "SKILL.md"
    $receiptHashBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    Add-Content -LiteralPath (Join-Path $scenario.Harness "skills\global-task-orchestrator\SKILL.md") -Value "`nsource update" -Encoding UTF8
    $runtimeHashBefore = Get-FileSha256 -PathValue $runtimeSkillMd
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "sync should propagate source updates"
    Assert-True ((Get-FileSha256 -PathValue $runtimeSkillMd) -ne $runtimeHashBefore) "runtime SKILL.md should change after source update"
    Assert-True ((Get-FileSha256 -PathValue $paths.ReceiptPath) -ne $receiptHashBefore) "receipt should update after source update"
    Assert-True ([bool](Invoke-CodexDoctor -Scenario $scenario).Json.ok) "doctor should pass after source update sync"
}

Run-TestCase -Name "Independent managed skill source change is propagated to runtime and receipt" -Body {
    $scenario = New-Scenario -Name "independent-managed-source-update"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $runtimeScript = Join-Path $paths.FailureMemorySkillDir "scripts\command-failure-memory.py"
    $receiptHashBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    Add-Content -LiteralPath (Join-Path $scenario.Harness "skills\command-failure-memory\scripts\command-failure-memory.py") -Value "`n# source update" -Encoding UTF8
    $runtimeHashBefore = Get-FileSha256 -PathValue $runtimeScript
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "sync should propagate independent skill updates"
    Assert-True ((Get-FileSha256 -PathValue $runtimeScript) -ne $runtimeHashBefore) "runtime command-failure-memory script should change after source update"
    Assert-True ((Get-FileSha256 -PathValue $paths.ReceiptPath) -ne $receiptHashBefore) "receipt should update after independent skill source update"
    Assert-True ([bool](Invoke-CodexDoctor -Scenario $scenario).Json.ok) "doctor should pass after independent skill update sync"
}

Run-TestCase -Name "Repo-local benchmark managed skill source change is propagated to runtime and receipt" -Body {
    $scenario = New-Scenario -Name "benchmark-managed-source-update"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $runtimeScript = Join-Path $paths.BenchmarkSkillDir "scripts\scaffold_benchmark.py"
    $receiptHashBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    Add-Content -LiteralPath (Join-Path $scenario.Harness "skills\pre-dev-benchmark\scripts\scaffold_benchmark.py") -Value "`n# source update" -Encoding UTF8
    $runtimeHashBefore = Get-FileSha256 -PathValue $runtimeScript
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "sync should propagate repo-local benchmark skill updates"
    Assert-True ((Get-FileSha256 -PathValue $runtimeScript) -ne $runtimeHashBefore) "runtime pre-dev-benchmark script should change after source update"
    Assert-True ((Get-FileSha256 -PathValue $paths.ReceiptPath) -ne $receiptHashBefore) "receipt should update after repo-local benchmark source update"
    Assert-True ([bool](Invoke-CodexDoctor -Scenario $scenario).Json.ok) "doctor should pass after repo-local benchmark skill update sync"
}

Run-TestCase -Name "Default sync refuses unmanaged takeover of target skill directory" -Body {
    $scenario = New-Scenario -Name "refuse-unmanaged-takeover"
    $paths = Get-CodexPaths -Scenario $scenario
    New-Item -ItemType Directory -Path $paths.ManagedSkillDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Value "foreign content" -Encoding UTF8
    $foreignHash = Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "sync should refuse unmanaged takeover by default"
    Assert-Equal $foreignHash (Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")) "foreign runtime content must stay unchanged"
    if (Test-Path -LiteralPath $paths.ReceiptPath) {
        $receipt = Read-Json -PathValue $paths.ReceiptPath
        Assert-True (@($receipt.managed_files | ForEach-Object { $_.target }) -notcontains "global-task-orchestrator/SKILL.md") "receipt must not claim foreign runtime skill"
    }
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail on unmanaged conflict"
}

Run-TestCase -Name "Default sync refuses unmanaged takeover of target skill directory even when content matches source" -Body {
    $scenario = New-Scenario -Name "refuse-unmanaged-takeover-even-if-matches"
    $paths = Get-CodexPaths -Scenario $scenario
    $sourceSkillDir = Join-Path $scenario.Harness "skills\global-task-orchestrator"
    Copy-Item -LiteralPath $sourceSkillDir -Destination $paths.ManagedSkillDir -Recurse -Force
    $runtimeBefore = Get-RelativeTreeHashes -RootPath $paths.ManagedSkillDir
    Assert-True (-not (Test-Path -LiteralPath $paths.ReceiptPath)) "receipt must not exist before sync"
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "default sync should refuse unmanaged takeover even when runtime content matches source"
    Assert-True (-not (Test-Path -LiteralPath $paths.ReceiptPath)) "sync must not generate receipt for unmanaged matching runtime content"
    Assert-Equal ($runtimeBefore | ConvertTo-Json -Compress) ((Get-RelativeTreeHashes -RootPath $paths.ManagedSkillDir) | ConvertTo-Json -Compress) "runtime directory content must stay unchanged after refused takeover"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when matching runtime content is still unmanaged"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "runtime_unmanaged_conflict" "doctor must report unmanaged runtime conflict for matching unmanaged runtime content"
}

Run-TestCase -Name "Default sync preserves unmanaged sibling runtime skills" -Body {
    $scenario = New-Scenario -Name "preserve-unmanaged-sibling"
    $paths = Get-CodexPaths -Scenario $scenario
    $siblingPath = Join-Path $paths.SkillsRoot "third-party-skill"
    New-Item -ItemType Directory -Path $siblingPath -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $siblingPath "SKILL.md") -Value "third party" -Encoding UTF8
    $siblingHash = Get-FileSha256 -PathValue (Join-Path $siblingPath "SKILL.md")
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "sync should succeed with unmanaged sibling"
    Assert-Equal $siblingHash (Get-FileSha256 -PathValue (Join-Path $siblingPath "SKILL.md")) "unmanaged sibling runtime skill must stay unchanged"
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    Assert-True (@($receipt.managed_files | ForEach-Object { $_.target }) -notcontains "third-party-skill/SKILL.md") "receipt must not include unmanaged sibling skill"
}

Run-TestCase -Name "Unmanaged receipt target does not authorize managed skill takeover" -Body {
    $scenario = New-Scenario -Name "receipt-unmanaged-target-blocks-takeover"
    $paths = Get-CodexPaths -Scenario $scenario
    $thirdPartyPath = Join-Path $paths.SkillsRoot "third-party-skill"
    New-Item -ItemType Directory -Path $thirdPartyPath -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $thirdPartyPath "x.txt") -Value "third party" -Encoding UTF8
    New-Item -ItemType Directory -Path $paths.ManagedSkillDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Value "foreign content" -Encoding UTF8
    $foreignHash = Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")
    New-Item -ItemType Directory -Path (Split-Path -Parent $paths.ReceiptPath) -Force | Out-Null
    Write-Json -PathValue $paths.ReceiptPath -Data ([ordered]@{
        schema_version = "2.0"
        harness_root = $scenario.Harness
        codex_home = $scenario.CodexHome
        runtime_root = $paths.SkillsRoot
        managed_skills = @("third-party-skill")
        managed_files = @(
            [ordered]@{
                source = "skills/third-party-skill/x.txt"
                target = "third-party-skill/x.txt"
                sha256 = Get-FileSha256 -PathValue (Join-Path $thirdPartyPath "x.txt")
            }
        )
    })
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "sync should reject receipt that only trusts unmanaged target"
    $summary = ($sync.Text | ConvertFrom-Json)
    Assert-Contains @($summary.conflicts) "receipt_unmanaged_skill_target" "sync conflict summary should surface unmanaged receipt target"
    Assert-Equal $foreignHash (Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")) "managed runtime content must stay unchanged when receipt target is unmanaged"
}

Run-TestCase -Name "Disguised unmanaged receipt target does not authorize managed skill takeover" -Body {
    $scenario = New-Scenario -Name "receipt-disguised-unmanaged-target-blocks-takeover"
    $paths = Get-CodexPaths -Scenario $scenario
    $thirdPartyPath = Join-Path $paths.SkillsRoot "third-party-skill"
    New-Item -ItemType Directory -Path $thirdPartyPath -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $thirdPartyPath "x.txt") -Value "third party" -Encoding UTF8
    New-Item -ItemType Directory -Path $paths.ManagedSkillDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Value "foreign content" -Encoding UTF8
    $foreignHash = Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")
    New-Item -ItemType Directory -Path (Split-Path -Parent $paths.ReceiptPath) -Force | Out-Null
    Write-Json -PathValue $paths.ReceiptPath -Data ([ordered]@{
        schema_version = "2.0"
        harness_root = $scenario.Harness
        codex_home = $scenario.CodexHome
        runtime_root = $paths.SkillsRoot
        managed_skills = @("global-task-orchestrator")
        managed_files = @(
            [ordered]@{
                source = "skills/global-task-orchestrator/x.txt"
                target = "global-task-orchestrator/../third-party-skill/x.txt"
                sha256 = Get-FileSha256 -PathValue (Join-Path $thirdPartyPath "x.txt")
            }
        )
    })
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "sync should reject disguised unmanaged receipt target"
    $summary = ($sync.Text | ConvertFrom-Json)
    Assert-Contains @($summary.conflicts) "receipt_unmanaged_skill_target" "sync conflict summary should surface disguised unmanaged receipt target"
    Assert-Equal $foreignHash (Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")) "managed runtime content must stay unchanged when receipt target escapes managed namespace after canonicalization"
}

Run-TestCase -Name "Trusted receipt allows stale managed file cleanup after source removal" -Body {
    $scenario = New-Scenario -Name "trusted-stale-cleanup"
    $obsoletePath = Join-Path $scenario.Harness "skills\global-task-orchestrator\obsolete.txt"
    Set-Content -LiteralPath $obsoletePath -Value "obsolete" -Encoding UTF8
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    Assert-True (Test-Path -LiteralPath (Join-Path $paths.ManagedSkillDir "obsolete.txt")) "obsolete runtime file should exist after first sync"
    Remove-Item -LiteralPath $obsoletePath -Force
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-Equal 0 $sync.ExitCode "trusted sync should remove stale managed file"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $paths.ManagedSkillDir "obsolete.txt"))) "obsolete runtime file should be removed"
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    Assert-True (@($receipt.managed_files | ForEach-Object { $_.target }) -notcontains "global-task-orchestrator/obsolete.txt") "receipt must remove stale target"
    Assert-True ([bool](Invoke-CodexDoctor -Scenario $scenario).Json.ok) "doctor should pass after trusted stale cleanup"
}

Run-TestCase -Name "Untrusted receipt blocks managed file update and leaves runtime unchanged" -Body {
    $scenario = New-Scenario -Name "untrusted-receipt-update"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $receiptBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    $runtimeBefore = Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.harness_root = "C:\foreign\root"
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $receiptTamperedHash = Get-FileSha256 -PathValue $paths.ReceiptPath
    Add-Content -LiteralPath (Join-Path $scenario.Harness "skills\global-task-orchestrator\SKILL.md") -Value "`nsource change" -Encoding UTF8
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "sync should fail with untrusted receipt"
    Assert-Equal $runtimeBefore (Get-FileSha256 -PathValue (Join-Path $paths.ManagedSkillDir "SKILL.md")) "runtime skill must stay unchanged"
    Assert-Equal $receiptTamperedHash (Get-FileSha256 -PathValue $paths.ReceiptPath) "receipt must not be rewritten after blocked sync"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_harness_root_mismatch" "doctor must report receipt_harness_root_mismatch"
}

Run-TestCase -Name "Untrusted receipt blocks stale managed delete and keeps previously tracked file" -Body {
    $scenario = New-Scenario -Name "untrusted-receipt-stale-delete"
    $obsoletePath = Join-Path $scenario.Harness "skills\global-task-orchestrator\obsolete.txt"
    Set-Content -LiteralPath $obsoletePath -Value "obsolete" -Encoding UTF8
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    Remove-Item -LiteralPath $obsoletePath -Force
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.runtime_root = "C:\foreign\skills"
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $receiptTamperedHash = Get-FileSha256 -PathValue $paths.ReceiptPath
    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "sync should fail when untrusted receipt would stale-delete file"
    Assert-True (Test-Path -LiteralPath (Join-Path $paths.ManagedSkillDir "obsolete.txt")) "tracked stale file must remain when receipt is untrusted"
    Assert-Equal $receiptTamperedHash (Get-FileSha256 -PathValue $paths.ReceiptPath) "receipt must remain untouched after blocked stale delete"
}

Run-TestCase -Name "Doctor fails on runtime hash drift even when paths still exist" -Body {
    $scenario = New-Scenario -Name "doctor-runtime-drift"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    Add-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "scripts\bootstrap-task.ps1") -Value "`n# drift" -Encoding UTF8
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail on runtime hash drift"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_target_sha256_mismatch" "doctor must report receipt target hash mismatch"
    Assert-True ((Get-ManagedIssueTypes -DoctorJson $doctor.Json) -notcontains "runtime_managed_skill_missing") "doctor must not misclassify drift as missing"
}

Run-TestCase -Name "Doctor fails when receipt points outside codex runtime root" -Body {
    $scenario = New-Scenario -Name "doctor-receipt-outside-root"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "initial sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.managed_files[0].target = "../outside.txt"
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when receipt target escapes runtime root"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_target_out_of_runtime_root" "doctor must report target outside runtime root"
}

Run-TestCase -Name "Doctor ignores .system plugins and unmanaged runtime skills when managed skill is healthy" -Body {
    $scenario = New-Scenario -Name "doctor-ignores-unmanaged-runtime"
    $paths = Get-CodexPaths -Scenario $scenario
    foreach ($dir in @(".system\openai-docs", "third-party-skill")) {
        $full = Join-Path $paths.SkillsRoot $dir
        New-Item -ItemType Directory -Path $full -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $full "sentinel.txt") -Value $dir -Encoding UTF8
    }
    New-Item -ItemType Directory -Path (Join-Path $paths.PluginsRoot "sample-plugin") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $paths.PluginsRoot "sample-plugin\plugin.json") -Value "{}" -Encoding UTF8
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True ([bool]$doctor.Json.ok) "doctor should ignore unmanaged runtime skills and plugins when managed skill is healthy"
}

Run-TestCase -Name "Doctor fails when managed runtime skill is missing but ignores unrelated runtime directories" -Body {
    $scenario = New-Scenario -Name "doctor-managed-runtime-missing"
    $paths = Get-CodexPaths -Scenario $scenario
    New-Item -ItemType Directory -Path (Join-Path $paths.SkillsRoot ".system\openai-docs") -Force | Out-Null
    Assert-True (-not (Test-Path -LiteralPath $paths.ManagedSkillDir)) "managed runtime skill should start missing"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when managed runtime skill is missing"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "runtime_managed_skill_missing" "doctor must report missing managed runtime skill"
}

Run-TestCase -Name "Doctor reports managed skill drift without classifying unmanaged runtime directories as issues" -Body {
    $scenario = New-Scenario -Name "doctor-managed-drift-only"
    $paths = Get-CodexPaths -Scenario $scenario
    New-Item -ItemType Directory -Path (Join-Path $paths.SkillsRoot "third-party-skill") -Force | Out-Null
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    Add-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Value "`n# drift" -Encoding UTF8
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail on managed drift"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_target_sha256_mismatch" "doctor must report managed drift"
}

Run-TestCase -Name "Codex minimal happy path sync and doctor for global-task-orchestrator" -Body {
    $scenario = New-Scenario -Name "codex-minimal-happy-path"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-Equal 0 $doctor.ExitCode "doctor should succeed"
    Assert-True ([bool]$doctor.Json.ok) "doctor should pass for minimal happy path"
}

Run-TestCase -Name "Codex doctor fails when source skill is missing" -Body {
    $scenario = New-Scenario -Name "doctor-source-skill-missing"
    Remove-Item -LiteralPath (Join-Path $scenario.Harness "skills\global-task-orchestrator") -Recurse -Force
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when source skill is missing"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "source_managed_skill_missing" "doctor must report source skill missing"
}

Run-TestCase -Name "Codex doctor fails when independent command-failure-memory launcher is missing" -Body {
    $scenario = New-Scenario -Name "doctor-source-failure-memory-missing"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "bootstrap sync should succeed before source file removal"
    Remove-Item -LiteralPath (Join-Path $scenario.Harness "skills\command-failure-memory\scripts\command-failure-memory.cmd") -Force
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when command-failure-memory source launcher is missing"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "source_required_file_missing" "doctor must report missing required failure-memory source launcher"
}

Run-TestCase -Name "Codex doctor fails when receipt managed_files is empty" -Body {
    $scenario = New-Scenario -Name "doctor-empty-managed-files"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "bootstrap sync should succeed before receipt tamper"
    $paths = Get-CodexPaths -Scenario $scenario
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.managed_files = @()
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when receipt managed_files is empty"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_managed_files_empty" "doctor must report empty managed_files"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_missing_required_target" "doctor must still report missing required targets when managed_files is empty"
}

Run-TestCase -Name "Codex doctor fails when receipt root is malformed" -Body {
    $scenario = New-Scenario -Name "doctor-invalid-receipt-root"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "bootstrap sync should succeed before malformed receipt tamper"
    $paths = Get-CodexPaths -Scenario $scenario
    Set-Content -LiteralPath $paths.ReceiptPath -Value '[]' -Encoding UTF8
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when receipt root is malformed"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_invalid" "doctor must report malformed receipt root as invalid receipt"
}

Run-TestCase -Name "Sync refuses takeover when receipt managed_files is empty" -Body {
    $scenario = New-Scenario -Name "sync-empty-managed-files-untrusted"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "bootstrap sync should succeed before receipt tamper"
    $paths = Get-CodexPaths -Scenario $scenario
    $receipt = Read-Json -PathValue $paths.ReceiptPath
    $receipt.managed_files = @()
    Write-Json -PathValue $paths.ReceiptPath -Data $receipt
    Set-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Value "foreign content" -Encoding UTF8

    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "sync should refuse runtime takeover when receipt managed_files is empty"
    Assert-True ($sync.Text -like "*receipt_managed_files_empty*") "sync conflict summary should surface empty managed_files"
    Assert-Equal "foreign content" (Get-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Raw -Encoding UTF8).Trim() "sync must not overwrite foreign runtime content when receipt is untrusted"
}

Run-TestCase -Name "Sync refuses takeover when receipt root is malformed" -Body {
    $scenario = New-Scenario -Name "sync-invalid-receipt-root"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "bootstrap sync should succeed before malformed receipt tamper"
    $paths = Get-CodexPaths -Scenario $scenario
    Set-Content -LiteralPath $paths.ReceiptPath -Value '[]' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Value "foreign content" -Encoding UTF8

    $sync = Invoke-CodexSync -Scenario $scenario
    Assert-True ($sync.ExitCode -ne 0) "sync should refuse runtime takeover when receipt root is malformed"
    Assert-True ($sync.Text -like "*receipt_invalid_json_root*") "sync conflict summary should surface malformed receipt root"
    Assert-Equal "foreign content" (Get-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "SKILL.md") -Raw -Encoding UTF8).Trim() "sync must not overwrite foreign runtime content when receipt root is malformed"
}

Run-TestCase -Name "Codex doctor fails when runtime skill is missing" -Body {
    $scenario = New-Scenario -Name "doctor-runtime-skill-missing"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail when runtime skill is missing"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "runtime_managed_skill_missing" "doctor must report runtime skill missing"
}

Run-TestCase -Name "Codex doctor detects key file drift between source and runtime" -Body {
    $scenario = New-Scenario -Name "doctor-key-file-drift"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    Add-Content -LiteralPath (Join-Path $paths.ManagedSkillDir "agents\openai.yaml") -Value "`n# drift" -Encoding UTF8
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True (-not [bool]$doctor.Json.ok) "doctor should fail on key file drift"
    Assert-Contains (Get-ManagedIssueTypes -DoctorJson $doctor.Json) "receipt_target_sha256_mismatch" "doctor must report key file drift"
}

Run-TestCase -Name "Codex sync keeps unmanaged sibling runtime skill untouched" -Body {
    $scenario = New-Scenario -Name "codex-preserve-sibling-runtime-skill"
    $paths = Get-CodexPaths -Scenario $scenario
    $sibling = Join-Path $paths.SkillsRoot "third-party-skill"
    New-Item -ItemType Directory -Path $sibling -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $sibling "SKILL.md") -Value "third-party" -Encoding UTF8
    $before = Get-FileSha256 -PathValue (Join-Path $sibling "SKILL.md")
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    Assert-Equal $before (Get-FileSha256 -PathValue (Join-Path $sibling "SKILL.md")) "unmanaged sibling runtime skill must stay untouched"
}

Run-TestCase -Name "Codex sync does not take over .system or plugin paths" -Body {
    $scenario = New-Scenario -Name "codex-no-takeover-system-plugin"
    $paths = Get-CodexPaths -Scenario $scenario
    New-Item -ItemType Directory -Path (Join-Path $paths.SkillsRoot ".system\openai-docs") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $paths.SkillsRoot ".system\openai-docs\sentinel.txt") -Value "system" -Encoding UTF8
    New-Item -ItemType Directory -Path (Join-Path $paths.PluginsRoot "sample-plugin") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $paths.PluginsRoot "sample-plugin\plugin.json") -Value '{"ok":true}' -Encoding UTF8
    $systemHash = Get-FileSha256 -PathValue (Join-Path $paths.SkillsRoot ".system\openai-docs\sentinel.txt")
    $pluginHash = Get-FileSha256 -PathValue (Join-Path $paths.PluginsRoot "sample-plugin\plugin.json")
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    Assert-Equal $systemHash (Get-FileSha256 -PathValue (Join-Path $paths.SkillsRoot ".system\openai-docs\sentinel.txt")) ".system content must remain untouched"
    Assert-Equal $pluginHash (Get-FileSha256 -PathValue (Join-Path $paths.PluginsRoot "sample-plugin\plugin.json")) "plugin content must remain untouched"
}

Run-TestCase -Name "Codex doctor ignores Claude runtime and settings" -Body {
    $scenario = New-Scenario -Name "codex-doctor-ignores-claude"
    New-Item -ItemType Directory -Path (Join-Path $scenario.Harness ".claude") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.Harness ".claude\settings.json") -Value "{ bad-json" -Encoding UTF8
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True ([bool]$doctor.Json.ok) "codex doctor must ignore Claude runtime and settings"
}

Run-TestCase -Name "Codex doctor does not expand to project cleanup checks" -Body {
    $scenario = New-Scenario -Name "codex-doctor-no-project-cleanup"
    Set-Content -LiteralPath (Join-Path $scenario.Harness "AGENTS.md") -Value "legacy agents" -Encoding UTF8
    New-Item -ItemType Directory -Path (Join-Path $scenario.Harness ".claude") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.Harness ".claude\settings.local.json") -Value "{}" -Encoding UTF8
    New-Item -ItemType Directory -Path (Join-Path $scenario.Harness "project-skill-mirror") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scenario.Harness "project-skill-mirror\SKILL.md") -Value "legacy mirror" -Encoding UTF8
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-True ([bool]$doctor.Json.ok) "codex doctor must ignore project cleanup artifacts"
}

Run-TestCase -Name "Codex doctor reports only fixed managed skill targets" -Body {
    $scenario = New-Scenario -Name "codex-doctor-managed-target-only"
    $extraSkillPath = Join-Path $scenario.Harness "skills\experimental-skill"
    New-Item -ItemType Directory -Path $extraSkillPath -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $extraSkillPath "SKILL.md") -Value "# experimental" -Encoding UTF8
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "sync should succeed"
    $doctor = Invoke-CodexDoctor -Scenario $scenario
    Assert-Contains @($doctor.Json.codex_audit.managed_skills) "global-task-orchestrator" "doctor must report orchestrator as managed skill target"
    Assert-Contains @($doctor.Json.codex_audit.managed_skills) "command-failure-memory" "doctor must report failure-memory as managed skill target"
    Assert-Contains @($doctor.Json.codex_audit.managed_skills) "pre-dev-benchmark" "doctor must report pre-dev-benchmark as managed skill target"
    $issueText = $doctor.Text
    Assert-True ($issueText -notlike "*experimental-skill*") "doctor output must not expand managed scope to experimental skill"
}

Run-TestCase -Name "Codex sync supports install then unchanged sync" -Body {
    $scenario = New-Scenario -Name "codex-install-then-unchanged"
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "install sync should succeed"
    $paths = Get-CodexPaths -Scenario $scenario
    $receiptBefore = Get-FileSha256 -PathValue $paths.ReceiptPath
    $runtimeBefore = Get-RelativeTreeHashes -RootPath $paths.ManagedSkillDir
    Assert-Equal 0 (Invoke-CodexSync -Scenario $scenario).ExitCode "unchanged sync should succeed"
    Assert-Equal $receiptBefore (Get-FileSha256 -PathValue $paths.ReceiptPath) "receipt must stay unchanged on second sync"
    Assert-Equal ($runtimeBefore | ConvertTo-Json -Compress) ((Get-RelativeTreeHashes -RootPath $paths.ManagedSkillDir) | ConvertTo-Json -Compress) "runtime tree must stay unchanged on second sync"
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
