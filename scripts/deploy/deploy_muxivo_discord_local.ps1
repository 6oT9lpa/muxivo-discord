param(
    [string]$HostName = '192.168.1.142',
    [int]$Port = 22,
    [string]$User = 'minecraft',
    [Parameter(Mandatory = $true)][string]$SshPassword,
    [Parameter(Mandatory = $true)][string]$RootPassword,
    [string]$Archive = (Join-Path $env:TEMP 'muxivo-discord-release.tar.gz')
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$script = Join-Path $PSScriptRoot 'muxivo-discord_deploy.sh'

Push-Location $root
try {
    # The compiled Activity `dist` is shipped; local node_modules is rebuilt
    # neither by the server nor needed at runtime.
    tar -czf $Archive --exclude=.git --exclude=venv --exclude=.venv --exclude=.env --exclude=data --exclude=logs --exclude=.tmp --exclude=__pycache__ --exclude=.pytest_cache --exclude=activity/client/node_modules .
    if ($LASTEXITCODE -ne 0) { throw "Release archive build failed with exit code $LASTEXITCODE." }
} finally { Pop-Location }

pscp.exe -batch -P $Port -pw $SshPassword $Archive "${User}@${HostName}:/tmp/muxivo-discord-release.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Release archive upload failed with exit code $LASTEXITCODE." }
pscp.exe -batch -P $Port -pw $SshPassword $script "${User}@${HostName}:/tmp/muxivo-discord_deploy.sh"
if ($LASTEXITCODE -ne 0) { throw "Deployment script upload failed with exit code $LASTEXITCODE." }
$command = "chmod +x /tmp/muxivo-discord_deploy.sh; printf '%s\n' '$RootPassword' | su root -c 'ARCHIVE=/tmp/muxivo-discord-release.tar.gz /tmp/muxivo-discord_deploy.sh'"
plink.exe -batch -ssh "${User}@${HostName}" -P $Port -pw $SshPassword $command
