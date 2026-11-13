#Requires -Version 5.1
<#
.SYNOPSIS
Keep an SSH tunnel from this workstation to the relay-hosted GitHub proxy.

.DESCRIPTION
The network path between this workstation and the relay host resets plain TCP
connections to high ports, but SSH works.  This script therefore exposes the
relay-side CONNECT proxy on 127.0.0.1:<Port> through an SSH local forward:

    workstation 127.0.0.1:<Port>  ->  (ssh)  ->  relay 127.0.0.1:<Port>

A hidden supervisor process owns the ssh child and restarts it when the tunnel
drops.  All state lives in %USERPROFILE%\.operon\github-proxy-tunnel.

Actions:
  start           start the supervisor and wait for the forwarded port
  stop            stop the supervisor and the ssh child
  restart         stop then start
  status          report supervisor, ssh and port state
  ensure          start only when the tunnel is not already up (default)
  run             internal supervisor loop; do not call directly
  install-startup add a per-user Run entry that calls ensure at logon
  remove-startup  delete that Run entry
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'restart', 'status', 'ensure', 'run', 'install-startup', 'remove-startup')]
    [string]$Action = 'ensure',

    [string]$SshConfig = (Join-Path $env:USERPROFILE '.ssh\config'),
    [string]$HostAlias = 'srv',
    [int]$Port = 18080,
    [string]$StateDir = (Join-Path $env:USERPROFILE '.operon\github-proxy-tunnel')
)

$ErrorActionPreference = 'Stop'

$SupervisorPidFile = Join-Path $StateDir 'supervisor.pid'
$SshPidFile = Join-Path $StateDir 'ssh.pid'
$StopFlag = Join-Path $StateDir 'stop.flag'
$SshOutLog = Join-Path $StateDir 'ssh.out.log'
$SshErrLog = Join-Path $StateDir 'ssh.err.log'
$SupervisorLog = Join-Path $StateDir 'supervisor.log'
$RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$RunValueName = 'OperonGithubProxyTunnel'

function Write-Log {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date).ToString('s'), $Message
    Add-Content -LiteralPath $SupervisorLog -Value $line
}

function Get-SshExe {
    $candidate = 'C:\Windows\System32\OpenSSH\ssh.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    $command = Get-Command ssh.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw 'ssh.exe not found'
}

function Read-Pid {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $text = (Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue).Trim()
    if (-not $text) { return $null }
    $value = 0
    if ([int]::TryParse($text, [ref]$value)) { return $value }
    return $null
}

function Test-Process {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Test-TunnelPort {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(750)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-TunnelPort {
    param([int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TunnelPort) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Stop-SshProcess {
    $sshPid = Read-Pid $SshPidFile
    if ($sshPid -and (Test-Process $sshPid)) {
        Stop-Process -Id $sshPid -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $SshPidFile -ErrorAction SilentlyContinue
}

function Stop-PortOwner {
    try {
        $connections = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    } catch {
        return
    }
    foreach ($connection in @($connections)) {
        $owner = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($owner -and $owner.ProcessName -eq 'ssh') {
            Stop-Process -Id $owner.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Start-Supervisor {
    if (Test-TunnelPort) {
        $supervisor = Read-Pid $SupervisorPidFile
        if (-not ($supervisor -and (Test-Process $supervisor))) {
            Write-Host 'tunnel port is open but supervisor is not tracked; leaving it untouched'
        }
        return
    }
    $supervisor = Read-Pid $SupervisorPidFile
    if ($supervisor -and (Test-Process $supervisor)) {
        if (Wait-TunnelPort -TimeoutSeconds 30) { return }
        throw "supervisor $supervisor is running but port $Port never opened; see $SupervisorLog"
    }
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    Remove-Item -LiteralPath $StopFlag -ErrorAction SilentlyContinue
    Stop-PortOwner
    if (Test-TunnelPort) {
        throw "port $Port is already in use by another process"
    }
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
        '-File', $PSCommandPath, 'run',
        '-SshConfig', $SshConfig,
        '-HostAlias', $HostAlias,
        '-Port', "$Port",
        '-StateDir', $StateDir
    )
    $child = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath $SupervisorPidFile -Value $child.Id -Encoding ASCII
    if (Wait-TunnelPort -TimeoutSeconds 30) { return }
    throw "tunnel did not come up within 30s; see $SupervisorLog and $SshErrLog"
}

function Stop-Tunnel {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    Set-Content -LiteralPath $StopFlag -Value 'stop' -Encoding ASCII
    $supervisor = Read-Pid $SupervisorPidFile
    if ($supervisor -and (Test-Process $supervisor)) {
        Stop-Process -Id $supervisor -Force -ErrorAction SilentlyContinue
    }
    Stop-SshProcess
    Stop-PortOwner
    Remove-Item -LiteralPath $SupervisorPidFile -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StopFlag -ErrorAction SilentlyContinue
}

function Show-Status {
    $supervisor = Read-Pid $SupervisorPidFile
    $ssh = Read-Pid $SshPidFile
    $supervisorAlive = Test-Process $supervisor
    $sshAlive = Test-Process $ssh
    $portOpen = Test-TunnelPort
    [pscustomobject]@{
        Port           = $Port
        PortOpen       = $portOpen
        SupervisorPid  = $supervisor
        SupervisorUp   = $supervisorAlive
        SshPid         = $ssh
        SshUp          = $sshAlive
        StateDir       = $StateDir
    } | Format-List
    if (-not ($supervisorAlive -and $sshAlive -and $portOpen)) {
        Write-Host 'tunnel is not healthy' -ForegroundColor Yellow
    }
}

function Invoke-Supervisor {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $sshExe = Get-SshExe
    Write-Log "supervisor start port=$Port alias=$HostAlias"
    while ($true) {
        if (Test-Path -LiteralPath $StopFlag) { break }
        $forward = '127.0.0.1:{0}:127.0.0.1:{0}' -f $Port
        $arguments = @(
            '-F', $SshConfig,
            '-N',
            '-o', 'BatchMode=yes',
            '-o', 'ExitOnForwardFailure=yes',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-L', $forward,
            $HostAlias
        )
        Write-Log "starting ssh $sshExe $($arguments -join ' ')"
        $child = Start-Process -FilePath $sshExe -ArgumentList $arguments -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $SshOutLog -RedirectStandardError $SshErrLog
        Set-Content -LiteralPath $SshPidFile -Value $child.Id -Encoding ASCII
        Wait-Process -Id $child.Id -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $SshPidFile -ErrorAction SilentlyContinue
        Write-Log "ssh exited code=$($child.ExitCode)"
        if (Test-Path -LiteralPath $StopFlag) { break }
        Start-Sleep -Seconds 5
    }
    Remove-Item -LiteralPath $StopFlag -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $SupervisorPidFile -ErrorAction SilentlyContinue
    Write-Log 'supervisor stop'
}

function Install-Startup {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $value = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" ensure -SshConfig "{1}" -HostAlias {2} -Port {3} -StateDir "{4}"' -f `
        $PSCommandPath, $SshConfig, $HostAlias, $Port, $StateDir
    New-Item -Path $RunKey -Force | Out-Null
    New-ItemProperty -Path $RunKey -Name $RunValueName -Value $value -PropertyType String -Force | Out-Null
    Write-Host "startup entry installed: $RunValueName"
}

function Remove-Startup {
    Remove-ItemProperty -Path $RunKey -Name $RunValueName -ErrorAction SilentlyContinue
    Write-Host "startup entry removed: $RunValueName"
}

switch ($Action) {
    'start' { Start-Supervisor; Write-Host "tunnel listening on 127.0.0.1:$Port" }
    'stop' { Stop-Tunnel; Write-Host 'tunnel stopped' }
    'restart' { Stop-Tunnel; Start-Sleep -Seconds 1; Start-Supervisor; Write-Host "tunnel listening on 127.0.0.1:$Port" }
    'status' { Show-Status }
    'ensure' { Start-Supervisor }
    'run' { Invoke-Supervisor }
    'install-startup' { Install-Startup }
    'remove-startup' { Remove-Startup }
}
