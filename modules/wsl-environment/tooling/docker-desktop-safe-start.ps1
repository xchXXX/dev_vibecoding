[CmdletBinding()]
param(
    [ValidateSet("Start", "RepairOnly", "Install", "Status")]
    [string]$Action = "Start",
    [string]$LocalAppDataRoot = $env:LOCALAPPDATA,
    [string]$CodexHome = "",
    [string]$TaskName = "AI Harness Docker Safe Start",
    [string]$DockerCliPath = "",
    [string]$DockerDesktopPath = "",
    [int]$StartupTimeoutSeconds = 180,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SourceRelativePath = "modules/wsl-environment/tooling/docker-desktop-safe-start.ps1"
$InstalledRelativePath = ".ai-harness/runtime/windows-external/docker-desktop-safe-start.ps1"
$ReceiptRelativePath = ".ai-harness/docker-safe-start.receipt.json"
$DefaultTaskName = "AI Harness Docker Safe Start"
$AllowedSocketNames = @{
    "DockerRun" = @(
        "dockerEthernetVfkit",
        "dockerInference",
        "sailor-ingest.sock",
        "userAnalyticsOtlpHttp.sock"
    )
    "SecretsEngine" = @("engine.sock")
}

function Resolve-CodexHome {
    if (-not [string]::IsNullOrWhiteSpace($CodexHome)) {
        return [System.IO.Path]::GetFullPath($CodexHome)
    }
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        return [System.IO.Path]::GetFullPath($env:CODEX_HOME)
    }
    return Join-Path $env:USERPROFILE ".codex"
}

function Resolve-DockerCli {
    if (-not [string]::IsNullOrWhiteSpace($DockerCliPath)) {
        return $DockerCliPath
    }
    $command = Get-Command docker.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    $candidates = @(
        (Join-Path $LocalAppDataRoot "Programs\DockerDesktop\resources\bin\docker.exe"),
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe")
    )
    if ($null -ne $command) {
        $candidates += $command.Source
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $candidates[0]
}

function Resolve-DockerDesktop {
    if (-not [string]::IsNullOrWhiteSpace($DockerDesktopPath)) {
        return $DockerDesktopPath
    }
    $candidates = @(
        (Join-Path $LocalAppDataRoot "Programs\DockerDesktop\Docker Desktop.exe"),
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $candidates[0]
}

function New-CategorizedError {
    param([string]$Category, [string]$Message)
    $exception = New-Object System.InvalidOperationException($Message)
    $exception.Data["Category"] = $Category
    return $exception
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Ensure-PerUserDockerInstallRegistry {
    $perUserInstallRoot = Join-Path $LocalAppDataRoot "Programs\DockerDesktop"
    $resolvedDesktop = Resolve-DockerDesktop
    $normalizedRoot = [System.IO.Path]::GetFullPath($perUserInstallRoot).TrimEnd("\")
    $normalizedDesktop = [System.IO.Path]::GetFullPath($resolvedDesktop)
    if (-not $normalizedDesktop.StartsWith($normalizedRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject]@{ applicable = $false; repaired = $false; path = ""; install_location = "" }
    }
    $registryPath = "HKCU:\SOFTWARE\Docker Inc.\Docker Desktop"
    $repaired = $false
    if (-not (Test-Path -LiteralPath $registryPath)) {
        New-Item -Path $registryPath -Force | Out-Null
        $repaired = $true
    }
    $properties = Get-ItemProperty -LiteralPath $registryPath
    $installLocationProperty = $properties.PSObject.Properties["InstallLocation"]
    $existing = if ($null -ne $installLocationProperty) { [string]$installLocationProperty.Value } else { "" }
    if ([string]::IsNullOrWhiteSpace($existing)) {
        New-ItemProperty -LiteralPath $registryPath -Name "InstallLocation" -PropertyType String -Value $normalizedRoot -Force | Out-Null
        $repaired = $true
    }
    elseif ([System.IO.Path]::GetFullPath($existing).TrimEnd("\") -ne $normalizedRoot) {
        throw (New-CategorizedError -Category "docker_registry_conflict" -Message "Refusing to overwrite Docker Desktop InstallLocation '$existing' with '$normalizedRoot'.")
    }
    return [pscustomobject]@{
        applicable = $true
        repaired = $repaired
        path = $registryPath
        install_location = $normalizedRoot
    }
}

function Get-RepairPlan {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$AllowedNames
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [pscustomobject]@{ path = $Path; repair = $false; entries = @() }
    }
    $entries = @(Get-ChildItem -LiteralPath $Path -Force)
    if ($entries.Count -eq 0) {
        return [pscustomobject]@{ path = $Path; repair = $false; entries = @() }
    }
    $unsafe = @(
        $entries | Where-Object {
            $_.PSIsContainer -or
            $_.Name -notin $AllowedNames -or
            $_.Length -ne 0
        }
    )
    if ($unsafe.Count -gt 0) {
        $details = @($unsafe | ForEach-Object { "{0} ({1} bytes)" -f $_.Name, $_.Length }) -join ", "
        throw (New-CategorizedError -Category "unsafe_directory_content" -Message "Refusing to rotate '$Path'; unexpected content: $details")
    }
    return [pscustomobject]@{
        path = $Path
        repair = $true
        entries = @($entries | ForEach-Object { $_.Name })
    }
}

function Invoke-SocketDirectoryRepair {
    $runPath = Join-Path $LocalAppDataRoot "Docker\run"
    $secretsPath = Join-Path $LocalAppDataRoot "docker-secrets-engine"
    $plans = @(
        Get-RepairPlan -Path $runPath -AllowedNames $AllowedSocketNames.DockerRun
        Get-RepairPlan -Path $secretsPath -AllowedNames $AllowedSocketNames.SecretsEngine
    )
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmssfff"
    $repairs = @()
    foreach ($plan in $plans) {
        if (-not $plan.repair) {
            continue
        }
        $parent = Split-Path -Parent $plan.path
        $leaf = Split-Path -Leaf $plan.path
        $backup = Join-Path $parent ("{0}.stale-{1}" -f $leaf, $timestamp)
        $counter = 0
        while (Test-Path -LiteralPath $backup) {
            $counter += 1
            $backup = Join-Path $parent ("{0}.stale-{1}-{2}" -f $leaf, $timestamp, $counter)
        }
        Move-Item -LiteralPath $plan.path -Destination $backup
        New-Item -ItemType Directory -Path $plan.path -Force | Out-Null
        $repairs += [pscustomobject]@{
            original_path = $plan.path
            backup_path = $backup
            preserved_entries = @($plan.entries)
        }
    }
    return @($repairs)
}

function Test-DockerHealthy {
    param([string]$CliPath)
    if (-not (Test-Path -LiteralPath $CliPath -PathType Leaf)) {
        return $false
    }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & $CliPath info --format "{{.ServerVersion}}" *> $null
        $nativeExitCode = $LASTEXITCODE
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    return $nativeExitCode -eq 0
}

function Test-DockerProcessPresent {
    $names = @("Docker Desktop", "com.docker.backend", "com.docker.build", "com.docker.proxy", "com.docker.vpnkit")
    foreach ($name in $names) {
        if (Get-Process -Name $name -ErrorAction SilentlyContinue) {
            return $true
        }
    }
    return $false
}

function Wait-DockerHealthy {
    param([string]$CliPath, [int]$TimeoutSeconds)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if (Test-DockerHealthy -CliPath $CliPath) {
            return $true
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}

function Stop-UnhealthyDockerProcesses {
    $names = @("Docker Desktop", "com.docker.backend", "com.docker.build", "com.docker.diagnose", "com.docker.proxy", "com.docker.vpnkit")
    foreach ($name in $names) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    $wslPath = Join-Path $env:SystemRoot "System32\wsl.exe"
    if (Test-Path -LiteralPath $wslPath -PathType Leaf) {
        $previousPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            & $wslPath --terminate docker-desktop *> $null
        }
        finally {
            $ErrorActionPreference = $previousPreference
        }
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while ((Test-DockerProcessPresent) -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
    }
    if (Test-DockerProcessPresent) {
        throw (New-CategorizedError -Category "docker_process_stop_failed" -Message "Known Docker Desktop processes did not stop within 20 seconds.")
    }
}

function Write-RunLog {
    param([Parameter(Mandatory = $true)][object]$Payload)
    $homePath = Resolve-CodexHome
    $logPath = Join-Path $homePath ".ai-harness\runtime\windows-external\logs\docker-safe-start.jsonl"
    $logDirectory = Split-Path -Parent $logPath
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    ($Payload | ConvertTo-Json -Depth 8 -Compress) | Add-Content -LiteralPath $logPath -Encoding UTF8
    return $logPath
}

function Invoke-SafeStart {
    $cli = Resolve-DockerCli
    $desktop = Resolve-DockerDesktop
    if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
        throw (New-CategorizedError -Category "docker_cli_missing" -Message "Docker CLI executable not found: $cli")
    }
    if (-not (Test-Path -LiteralPath $desktop -PathType Leaf)) {
        throw (New-CategorizedError -Category "docker_desktop_missing" -Message "Docker Desktop executable not found: $desktop")
    }
    if (Test-DockerHealthy -CliPath $cli) {
        return [ordered]@{ ok = $true; action = "Start"; already_healthy = $true; repaired = $false; repairs = @(); docker_healthy = $true }
    }
    if (Test-DockerProcessPresent) {
        if (Wait-DockerHealthy -CliPath $cli -TimeoutSeconds 30) {
            return [ordered]@{ ok = $true; action = "Start"; already_healthy = $true; repaired = $false; repairs = @(); docker_healthy = $true }
        }
        Stop-UnhealthyDockerProcesses
    }
    $repairs = @(Invoke-SocketDirectoryRepair)
    $launcher = Start-Process -FilePath $desktop -PassThru
    if (-not (Wait-DockerHealthy -CliPath $cli -TimeoutSeconds $StartupTimeoutSeconds)) {
        throw (New-CategorizedError -Category "docker_start_timeout" -Message "Docker Desktop did not become healthy within $StartupTimeoutSeconds seconds.")
    }
    return [ordered]@{
        ok = $true
        action = "Start"
        already_healthy = $false
        repaired = $repairs.Count -gt 0
        repairs = $repairs
        startup_method = "docker_desktop_launcher"
        launcher_pid = $launcher.Id
        docker_healthy = $true
    }
}

function Install-SafeStart {
    $homePath = Resolve-CodexHome
    $installedPath = Join-Path $homePath $InstalledRelativePath
    $receiptPath = Join-Path $homePath $ReceiptRelativePath
    $installedDirectory = Split-Path -Parent $installedPath
    New-Item -ItemType Directory -Path $installedDirectory -Force | Out-Null
    if ([System.IO.Path]::GetFullPath($PSCommandPath) -ne [System.IO.Path]::GetFullPath($installedPath)) {
        Copy-Item -LiteralPath $PSCommandPath -Destination $installedPath -Force
    }
    $registry = Ensure-PerUserDockerInstallRegistry

    $powershellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Action Start -Json' -f $installedPath
    $shortcutPath = Join-Path ([Environment]::GetFolderPath("Programs")) "Docker Desktop Safe Start.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $powershellPath
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = Split-Path -Parent (Resolve-DockerDesktop)
    $shortcut.IconLocation = (Resolve-DockerDesktop)
    $shortcut.Description = "Start Docker Desktop through the AI Harness stale-socket safeguard."
    $shortcut.Save()

    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    $runPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    if (-not (Test-Path -LiteralPath $runPath)) {
        New-Item -Path $runPath -Force | Out-Null
    }
    $startupCommand = '"{0}" {1}' -f $powershellPath, $arguments
    $runProperties = Get-ItemProperty -LiteralPath $runPath
    $existingRunProperty = $runProperties.PSObject.Properties[$TaskName]
    $existingStartupCommand = if ($null -ne $existingRunProperty) { [string]$existingRunProperty.Value } else { "" }
    $previousManagedCommand = ""
    if (Test-Path -LiteralPath $receiptPath -PathType Leaf) {
        $previousReceipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
        $previousNameProperty = $previousReceipt.PSObject.Properties["startup_entry_name"]
        $previousCommandProperty = $previousReceipt.PSObject.Properties["startup_command"]
        if ($null -ne $previousNameProperty -and $null -ne $previousCommandProperty -and [string]$previousNameProperty.Value -eq $TaskName) {
            $previousManagedCommand = [string]$previousCommandProperty.Value
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($existingStartupCommand) -and $existingStartupCommand -ne $startupCommand -and $existingStartupCommand -ne $previousManagedCommand) {
        throw (New-CategorizedError -Category "startup_entry_conflict" -Message "Refusing to overwrite the existing unmanaged HKCU Run value '$TaskName'.")
    }
    New-ItemProperty -LiteralPath $runPath -Name $TaskName -PropertyType String -Value $startupCommand -Force | Out-Null

    $sourceHash = Get-Sha256 -Path $PSCommandPath
    $installedHash = Get-Sha256 -Path $installedPath
    $receipt = [ordered]@{
        schema_version = 1
        installed_at = [DateTime]::UtcNow.ToString("o")
        source_relative_path = $SourceRelativePath
        installed_relative_path = $InstalledRelativePath
        source_sha256 = $sourceHash
        installed_sha256 = $installedHash
        task_name = $TaskName
        task_registered = $false
        startup_entry_name = $TaskName
        startup_entry_registered = $true
        startup_entry_mode = "hkcu_run"
        startup_command = $startupCommand
        registry_path = $registry.path
        registry_install_location = $registry.install_location
        shortcut_path = $shortcutPath
        log_relative_path = ".ai-harness/runtime/windows-external/logs/docker-safe-start.jsonl"
    }
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    return [ordered]@{
        ok = $true
        action = "Install"
        installed_path = $installedPath
        receipt_path = $receiptPath
        task_name = $TaskName
        shortcut_path = $shortcutPath
        scheduled_task_removed = $null -ne $existingTask
        startup_entry_name = $TaskName
        startup_entry_path = $runPath
        startup_command = $startupCommand
        registry_repaired = $registry.repaired
        registry_path = $registry.path
        registry_install_location = $registry.install_location
        source_sha256 = $sourceHash
        installed_sha256 = $installedHash
    }
}

function Get-InstallStatus {
    $homePath = Resolve-CodexHome
    $installedPath = Join-Path $homePath $InstalledRelativePath
    $receiptPath = Join-Path $homePath $ReceiptRelativePath
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $runPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    $startupCommand = ""
    if (Test-Path -LiteralPath $runPath) {
        $runProperties = Get-ItemProperty -LiteralPath $runPath
        $runProperty = $runProperties.PSObject.Properties[$TaskName]
        if ($null -ne $runProperty) {
            $startupCommand = [string]$runProperty.Value
        }
    }
    $installed = Test-Path -LiteralPath $installedPath -PathType Leaf
    $receiptExists = Test-Path -LiteralPath $receiptPath -PathType Leaf
    $cli = Resolve-DockerCli
    $desktop = Resolve-DockerDesktop
    $registryPath = "HKCU:\SOFTWARE\Docker Inc.\Docker Desktop"
    $registryInstallLocation = ""
    if (Test-Path -LiteralPath $registryPath) {
        $properties = Get-ItemProperty -LiteralPath $registryPath
        $installLocationProperty = $properties.PSObject.Properties["InstallLocation"]
        if ($null -ne $installLocationProperty) {
            $registryInstallLocation = [string]$installLocationProperty.Value
        }
    }
    return [ordered]@{
        ok = $installed -and $receiptExists -and -not [string]::IsNullOrWhiteSpace($startupCommand) -and $null -eq $task
        action = "Status"
        installed = $installed
        installed_path = $installedPath
        receipt_exists = $receiptExists
        receipt_path = $receiptPath
        task_registered = $null -ne $task
        task_name = $TaskName
        task_state = if ($null -ne $task) { [string]$task.State } else { "Missing" }
        startup_entry_registered = -not [string]::IsNullOrWhiteSpace($startupCommand)
        startup_entry_path = $runPath
        startup_command = $startupCommand
        docker_cli_path = $cli
        docker_cli_exists = Test-Path -LiteralPath $cli -PathType Leaf
        docker_desktop_path = $desktop
        docker_desktop_exists = Test-Path -LiteralPath $desktop -PathType Leaf
        registry_path = $registryPath
        registry_install_location = $registryInstallLocation
    }
}

$mutex = $null
$result = $null
$exitCode = 0
try {
    if ($Action -in @("Start", "Install")) {
        $mutex = New-Object System.Threading.Mutex($false, "Local\AIHarnessDockerDesktopSafeStart")
        if (-not $mutex.WaitOne([TimeSpan]::FromSeconds(10))) {
            throw (New-CategorizedError -Category "safe_start_already_running" -Message "Another Docker Desktop safe-start operation is already running.")
        }
    }
    switch ($Action) {
        "RepairOnly" {
            $repairs = @(Invoke-SocketDirectoryRepair)
            $result = [ordered]@{ ok = $true; action = "RepairOnly"; repaired = $repairs.Count -gt 0; repairs = $repairs }
        }
        "Start" {
            $result = Invoke-SafeStart
            $result["timestamp"] = [DateTime]::UtcNow.ToString("o")
            $result["log_path"] = Write-RunLog -Payload $result
        }
        "Install" { $result = Install-SafeStart }
        "Status" { $result = Get-InstallStatus }
    }
}
catch {
    $category = "unhandled_error"
    if ($_.Exception.Data.Contains("Category")) {
        $category = [string]$_.Exception.Data["Category"]
    }
    $result = [ordered]@{
        ok = $false
        action = $Action
        error = [ordered]@{ category = $category; message = $_.Exception.Message }
        timestamp = [DateTime]::UtcNow.ToString("o")
    }
    if ($Action -eq "Start") {
        try { $result["log_path"] = Write-RunLog -Payload $result } catch { }
    }
    $exitCode = 1
}
finally {
    if ($null -ne $mutex) {
        try { $mutex.ReleaseMutex() } catch { }
        $mutex.Dispose()
    }
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8 -Compress
}
else {
    $result | Format-List | Out-String | Write-Output
}
exit $exitCode
