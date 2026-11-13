#Requires -Version 5.1
<#
.SYNOPSIS
Deploy and operate the authenticated GitHub relay proxy on the internal server.

.DESCRIPTION
The release workstation cannot reach GitHub directly and the network path to the
relay host resets plain TCP connections to high ports, but SSH works.  This
script installs a small authenticated CONNECT proxy on the relay (under the
user's home directory, no root needed), keeps it alive through crontab, and
exposes it on the workstation as 127.0.0.1:<Port> through an SSH local forward.
The matching client configuration is written next to the GitHub token.

Actions:
  deploy         copy the proxy, create its config, start it, install cron,
                 start the SSH tunnel, write the local client config and verify
  status         show local config, tunnel state, remote service and a check
  start          start the remote proxy service
  stop           stop the remote proxy service
  restart        restart the remote proxy service
  test           tunnel checks plus token verification and optional upload test
  logs           tail the remote proxy log
  git            point global git HTTPS traffic at the proxy
  env            print environment variables for the current shell
  config         print the local client configuration with the password masked
  tunnel-start   start the workstation SSH tunnel
  tunnel-stop    stop the workstation SSH tunnel
  tunnel-status  report the workstation SSH tunnel state
#>
[CmdletBinding()]
param(
    [ValidateSet('deploy', 'status', 'start', 'stop', 'restart', 'test', 'logs', 'git', 'env', 'config',
        'tunnel-start', 'tunnel-stop', 'tunnel-status')]
    [string]$Action = 'deploy',

    [string]$RepoRoot,
    [string]$RemoteRoot = '/public/home/lihj/.operon/github-proxy',
    [string]$SshConfig = (Join-Path $env:USERPROFILE '.ssh\config'),
    [string]$HostAlias = 'srv',
    [int]$Port = 18080,
    [switch]$ConfigureGit,
    [switch]$SkipCron,
    [switch]$SkipTunnel,
    [switch]$InstallStartup,
    [int]$SelfTestMB = 0
)

$ErrorActionPreference = 'Stop'
$staging = 'C:\OperonTemp\proxy-deploy'
$tunnelScript = Join-Path $env:USERPROFILE '.operon\tunnel.ps1'
$tunnelSource = Join-Path $PSScriptRoot 'tunnel.ps1'

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-TunnelScript {
    param([Parameter(Mandatory = $true)][string]$TunnelAction)
    if (Test-Path -LiteralPath $tunnelSource) {
        $sourceItem = Get-Item -LiteralPath $tunnelSource
        $targetItem = if (Test-Path -LiteralPath $tunnelScript) { Get-Item -LiteralPath $tunnelScript } else { $null }
        if (-not $targetItem -or $sourceItem.LastWriteTimeUtc -gt $targetItem.LastWriteTimeUtc -or $sourceItem.Length -ne $targetItem.Length) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $tunnelScript) | Out-Null
            Copy-Item -LiteralPath $tunnelSource -Destination $tunnelScript -Force
        }
    }
    if (-not (Test-Path -LiteralPath $tunnelScript)) {
        throw "tunnel script not found: $tunnelScript"
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tunnelScript $TunnelAction `
        -SshConfig $SshConfig -HostAlias $HostAlias -Port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "tunnel action '$TunnelAction' failed with exit code $LASTEXITCODE"
    }
}

function Get-SshTarget {
    $lines = & ssh -F $SshConfig -G $HostAlias 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "ssh cannot resolve alias '$HostAlias' with config $SshConfig"
    }
    $values = @{}
    foreach ($line in $lines) {
        if ($line -match '^([A-Za-z]+)\s+(.*)$') {
            $values[$matches[1]] = $matches[2]
        }
    }
    if (-not $values['hostname']) {
        throw "ssh -G did not report a hostname for '$HostAlias'"
    }
    return $values
}

function Invoke-Remote {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [switch]$AllowFailure
    )
    $output = & ssh -F $SshConfig $HostAlias $Command 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "remote command failed (exit $code): $Command`n$($output -join "`n")"
    }
    return [pscustomobject]@{ Code = $code; Output = @($output) }
}

function Send-RemoteFile {
    param(
        [Parameter(Mandatory = $true)][string]$LocalPath,
        [Parameter(Mandatory = $true)][string]$RemoteName
    )
    & scp -F $SshConfig -q $LocalPath "${HostAlias}:$RemoteRoot/$RemoteName"
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed for $LocalPath"
    }
}

function Get-LocalConfig {
    $path = Join-Path $env:USERPROFILE '.operon\github_proxy.json'
    if (-not (Test-Path -LiteralPath $path)) {
        throw "local proxy config not found: $path (run -Action deploy)"
    }
    return Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
}

function Get-Python {
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    throw 'python.exe not found; install Python or add it to PATH'
}

function Test-ProxyChallenge {
    param(
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Target
    )
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect($HostName, $Port)
        $stream = $client.GetStream()
        $request = "CONNECT $Target HTTP/1.1`r`nHost: $Target`r`n`r`n"
        $bytes = [Text.Encoding]::ASCII.GetBytes($request)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
        $stream.ReadTimeout = 15000
        $buffer = New-Object byte[] 256
        $count = $stream.Read($buffer, 0, $buffer.Length)
        if ($count -le 0) { return '' }
        $line = [Text.Encoding]::ASCII.GetString($buffer, 0, $count)
        return ($line -split "`r`n")[0]
    } finally {
        $client.Close()
    }
}

function Test-Tunnel {
    param([Parameter(Mandatory = $true)]$Config)
    $authorized = & curl.exe -sS -o NUL -w '%{http_code} %{time_total}' --max-time 60 --proxy $Config.url https://api.github.com/rate_limit
    $challenge = Test-ProxyChallenge -HostName $Config.host -Port ([int]$Config.port) -Target 'api.github.com:443'
    $anonymous = if ($challenge -match '\s407\s') { '407' } else { $challenge }
    return [pscustomobject]@{
        Authorized = ($authorized -split ' ')[0]
        AuthorizedSeconds = ($authorized -split ' ')[1]
        Anonymous = $anonymous
        AnonymousSeconds = '0'
    }
}

function Invoke-Deploy {
    if (-not $RepoRoot) {
        $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    }
    $source = Join-Path $RepoRoot 'scripts\release_proxy'
    foreach ($name in @('github_proxy_server.py', 'service.sh', 'install_cron.sh', 'config.example.json', 'tunnel.ps1')) {
        $candidate = Join-Path $source $name
        if (-not (Test-Path -LiteralPath $candidate)) {
            throw "missing deployment source: $candidate"
        }
    }

    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    foreach ($name in @('github_proxy_server.py', 'service.sh', 'install_cron.sh', 'config.example.json', 'publish_release.py')) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $staging $name) -Force
    }

    Write-Step "preparing $RemoteRoot on $HostAlias"
    [void](Invoke-Remote "mkdir -p $RemoteRoot")
    foreach ($name in @('github_proxy_server.py', 'service.sh', 'install_cron.sh')) {
        Send-RemoteFile (Join-Path $staging $name) $name
    }
    [void](Invoke-Remote "chmod 700 $RemoteRoot/service.sh $RemoteRoot/install_cron.sh")

    $presence = Invoke-Remote "test -f $RemoteRoot/config.json && echo present || echo absent"
    if (($presence.Output -join "`n") -match 'absent') {
        Write-Step 'creating proxy credentials on the relay'
        [void](Invoke-Remote "cd $RemoteRoot && python3 github_proxy_server.py --init-config --config config.json --port $Port")
    } else {
        Write-Step 'keeping existing proxy credentials'
    }

    Write-Step 'binding the relay proxy to loopback only'
    $bootstrap = @'
import json
path = "config.json"
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
data["listen_host"] = "127.0.0.1"
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
'@
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bootstrap))
    [void](Invoke-Remote "cd $RemoteRoot && echo $b64 | base64 -d > _bind.py && python3 _bind.py && rm -f _bind.py")

    Write-Step 'restarting the proxy service'
    $restarted = Invoke-Remote "cd $RemoteRoot && bash service.sh restart"
    $restarted.Output | ForEach-Object { Write-Host "    $_" }

    if (-not $SkipCron) {
        Write-Step 'installing crontab keepalive'
        $cron = Invoke-Remote "cd $RemoteRoot && bash install_cron.sh"
        $cron.Output | ForEach-Object { Write-Host "    $_" }
    }

    Write-Step 'writing the local client configuration'
    & scp -F $SshConfig -q "${HostAlias}:$RemoteRoot/config.json" (Join-Path $staging 'config.json')
    if ($LASTEXITCODE -ne 0) {
        throw 'could not download the relay configuration'
    }
    $relay = Get-Content -LiteralPath (Join-Path $staging 'config.json') -Raw | ConvertFrom-Json
    if ([string]$relay.listen_host -ne '127.0.0.1') {
        throw "relay config still listens on '$($relay.listen_host)'; expected 127.0.0.1"
    }
    $target = Get-SshTarget
    $user = [uri]::EscapeDataString([string]$relay.username)
    $password = [uri]::EscapeDataString([string]$relay.password)
    $client = [ordered]@{
        host        = '127.0.0.1'
        port        = [int]$relay.listen_port
        username    = [string]$relay.username
        password    = [string]$relay.password
        remote_host = [string]$target['hostname']
        remote_root = $RemoteRoot
        updated     = (Get-Date).ToString('o')
    }
    $client['url'] = "http://{0}:{1}@{2}:{3}" -f $user, $password, $client['host'], $client['port']

    $configDirectory = Join-Path $env:USERPROFILE '.operon'
    New-Item -ItemType Directory -Force -Path $configDirectory | Out-Null
    $configPath = Join-Path $configDirectory 'github_proxy.json'
    $json = ($client | ConvertTo-Json) + "`n"
    [System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))

    Write-Step 'restricting permissions on the client configuration'
    $identity = "$env:USERDOMAIN\$env:USERNAME"
    & icacls.exe $configPath /inheritance:r /grant:r "${identity}:(F)" /grant:r 'SYSTEM:(F)' /grant:r 'Administrators:(F)' | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "could not restrict ACL on ${configPath}"
    }

    if (-not $SkipTunnel) {
        Write-Step 'starting the workstation SSH tunnel'
        Invoke-TunnelScript -TunnelAction 'ensure'
        if ($InstallStartup) {
            Write-Step 'installing the logon startup entry'
            Invoke-TunnelScript -TunnelAction 'install-startup'
        }
    }

    if ($ConfigureGit) {
        Set-GitProxy
    }

    Write-Step 'verifying the tunnel from this workstation'
    $config = Get-LocalConfig
    $result = Test-Tunnel -Config $config
    if ($result.Authorized -ne '200') {
        throw "tunnel check failed: authorized request returned HTTP $($result.Authorized); run -Action tunnel-status"
    }
    if ($result.Anonymous -ne '407') {
        throw "authentication check failed: anonymous request returned HTTP $($result.Anonymous), expected 407"
    }
    Write-Host ("    authenticated: HTTP {0} in {1}s" -f $result.Authorized, $result.AuthorizedSeconds) -ForegroundColor Green
    Write-Host ("    anonymous:     HTTP {0} (rejected as expected)" -f $result.Anonymous) -ForegroundColor Green
    Write-Host ''
    Write-Host "client config: $configPath" -ForegroundColor Green
    Write-Host "proxy URL:     $($config.url)" -ForegroundColor Green
    Write-Host "remote:        $($config.remote_host):$RemoteRoot" -ForegroundColor Green
}

function Set-GitProxy {
    $config = Get-LocalConfig
    & git config --global 'http.https://github.com/.proxy' $config.url
    if ($LASTEXITCODE -ne 0) {
        throw 'git config failed'
    }
    Write-Host "git now uses $($config.url) for https://github.com/" -ForegroundColor Green
}

function Show-Status {
    Write-Step 'local configuration'
    try {
        $config = Get-LocalConfig
        Write-Host ("    proxy:  {0}:{1}" -f $config.host, $config.port)
        Write-Host ("    relay:  {0}:{1}" -f $config.remote_host, $config.port)
        Write-Host ("    user:   {0}" -f $config.username)
        Write-Host ("    config: {0}" -f (Join-Path $env:USERPROFILE '.operon\github_proxy.json'))
    } catch {
        Write-Warning $_.Exception.Message
        return
    }

    Write-Step 'workstation tunnel'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tunnelScript status `
        -SshConfig $SshConfig -HostAlias $HostAlias -Port $Port

    Write-Step 'remote service'
    $status = Invoke-Remote "cd $RemoteRoot && bash service.sh status" -AllowFailure
    $status.Output | ForEach-Object { Write-Host "    $_" }

    Write-Step 'tunnel check'
    $result = Test-Tunnel -Config $config
    Write-Host ("    authenticated: HTTP {0} in {1}s" -f $result.Authorized, $result.AuthorizedSeconds)
    Write-Host ("    anonymous:     HTTP {0}" -f $result.Anonymous)
}

function Show-Config {
    $config = Get-LocalConfig
    [pscustomobject]@{
        host        = $config.host
        port        = $config.port
        username    = $config.username
        password    = ('*' * ([string]$config.password).Length)
        url         = ('http://{0}:****@{1}:{2}' -f $config.username, $config.host, $config.port)
        remote_host = $config.remote_host
    } | Format-List
}

function Show-Environment {
    $config = Get-LocalConfig
    Write-Host 'Run these lines in the shell that uploads to GitHub:' -ForegroundColor Cyan
    Write-Host ('$env:HTTPS_PROXY = "{0}"' -f $config.url)
    Write-Host ('$env:HTTP_PROXY  = "{0}"' -f $config.url)
    Write-Host '$env:NO_PROXY    = "localhost,127.0.0.1"'
    Write-Host ''
    Write-Host 'The release publisher already uses this proxy directly and needs no environment.'
}

function Invoke-Tests {
    Write-Step 'tunnel checks'
    $config = Get-LocalConfig
    $result = Test-Tunnel -Config $config
    Write-Host ("    authenticated: HTTP {0} in {1}s" -f $result.Authorized, $result.AuthorizedSeconds)
    Write-Host ("    anonymous:     HTTP {0}" -f $result.Anonymous)
    if ($result.Authorized -ne '200' -or $result.Anonymous -ne '407') {
        throw 'tunnel checks failed'
    }

    $python = Get-Python
    $publisher = Join-Path $PSScriptRoot 'publish_release.py'
    Write-Step 'token verification through the proxy'
    & $python $publisher verify
    if ($LASTEXITCODE -ne 0) {
        throw 'token verification failed'
    }

    if ($SelfTestMB -gt 0) {
        Write-Step "upload self test ($SelfTestMB MiB)"
        & $python $publisher selftest --size-mb $SelfTestMB
        if ($LASTEXITCODE -ne 0) {
            throw 'upload self test failed'
        }
    }
}

switch ($Action) {
    'deploy' { Invoke-Deploy }
    'status' { Show-Status }
    'start' {
        $result = Invoke-Remote "cd $RemoteRoot && bash service.sh start"
        $result.Output | ForEach-Object { Write-Host $_ }
    }
    'stop' {
        $result = Invoke-Remote "cd $RemoteRoot && bash service.sh stop"
        $result.Output | ForEach-Object { Write-Host $_ }
    }
    'restart' {
        $result = Invoke-Remote "cd $RemoteRoot && bash service.sh restart"
        $result.Output | ForEach-Object { Write-Host $_ }
    }
    'test' { Invoke-Tests }
    'logs' {
        $result = Invoke-Remote "tail -n 80 $RemoteRoot/proxy.log"
        $result.Output | ForEach-Object { Write-Host $_ }
    }
    'git' { Set-GitProxy }
    'env' { Show-Environment }
    'config' { Show-Config }
    'tunnel-start' { Invoke-TunnelScript -TunnelAction 'start' }
    'tunnel-stop' { Invoke-TunnelScript -TunnelAction 'stop' }
    'tunnel-status' { Invoke-TunnelScript -TunnelAction 'status' }
}
