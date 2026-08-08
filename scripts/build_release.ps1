param(
    [string]$Archive = (Join-Path $env:TEMP 'muxivo-discord-release.tar.gz')
)

$ErrorActionPreference = 'Stop'

if (Test-Path $Archive) {
    Remove-Item -LiteralPath $Archive
}

tar --exclude='./.git' `
    --exclude='./.agents' `
    --exclude='./.codex' `
    --exclude='./.codebase-memory' `
    --exclude='./.idea' `
    --exclude='./.vscode' `
    --exclude='./venv' `
    --exclude='./.venv' `
    --exclude='./activity/client/node_modules' `
    --exclude='./activity/client/src' `
    --exclude='./data' `
    --exclude='./docs' `
    --exclude='./logs' `
    --exclude='./tests' `
    --exclude='./.tmp' `
    --exclude='./.env' `
    --exclude='./__pycache__' `
    --exclude='./.pytest_cache' `
    --exclude='./htmlcov' `
    --exclude='./.coverage' `
    -czf $Archive .

Write-Host "Release archive created: $Archive"
