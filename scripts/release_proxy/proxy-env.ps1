<#
.SYNOPSIS
Exports the relay proxy settings into the current PowerShell session.

.DESCRIPTION
Dot-source this script so the variables stay in your shell:

    . .\scripts\release_proxy\proxy-env.ps1

It reads %USERPROFILE%\.operon\github_proxy.json, which proxy.ps1 writes during
deploy, and sets the variables honoured by pip, huggingface-cli/hf, conda, npm
and HTTPS git. The supervised SSH tunnel must be running; proxy.ps1 -Action
status reports that state.
#>
[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:USERPROFILE '.operon\github_proxy.json')
)

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "proxy config not found: $ConfigPath (run proxy.ps1 -Action deploy first)"
}

$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
if (-not $config.url) {
    throw "proxy config has no url: $ConfigPath"
}

$env:HTTPS_PROXY = $config.url
$env:HTTP_PROXY = $config.url
$env:ALL_PROXY = $config.url
$env:PIP_PROXY = $config.url
$env:NO_PROXY = 'localhost,127.0.0.1,::1'
$env:npm_config_proxy = $config.url
$env:npm_config_https_proxy = $config.url

# The Tsinghua mirror answers 403 to this relay's IPv4 egress path (its WAF
# flags the campus subnet), while upstream PyPI works through the same tunnel.
if (-not $env:PIP_INDEX_URL) {
    $env:PIP_INDEX_URL = 'https://pypi.org/simple'
}

Write-Host ("proxy environment loaded: {0}:{1}" -f $config.host, $config.port)
Write-Host 'pip, hf/huggingface-cli, conda, npm and HTTPS git use it automatically.'
