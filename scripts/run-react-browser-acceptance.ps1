$ErrorActionPreference = 'Stop'

function New-RandomSecret {
    $secretBytes = New-Object byte[] 36
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($secretBytes)
        return [Convert]::ToBase64String($secretBytes)
    }
    finally {
        $generator.Dispose()
    }
}

$composeFile = Join-Path $PSScriptRoot '..\compose.browser-tests.yaml'
$workspaceDirectory = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:BROWSER_TEST_DATABASE_PASSWORD = New-RandomSecret
$env:BROWSER_TEST_SECRET_KEY = New-RandomSecret
$env:BROWSER_TEST_ACCOUNT_PASSWORD = New-RandomSecret

docker compose -f $composeFile up -d --build --wait
docker compose -f $composeFile exec -T web python manage.py shell -c `
    "from django.conf import settings; assert settings.REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED is True"
if ($LASTEXITCODE -ne 0) {
    throw 'The isolated acceptance stack did not enable React cutover.'
}
$env:BROWSER_TEST_FIXTURES = docker compose -f $composeFile exec -T `
    -e BROWSER_TEST_ACCOUNT_PASSWORD=$env:BROWSER_TEST_ACCOUNT_PASSWORD `
    web python -m browser_acceptance.fixtures
if ($LASTEXITCODE -ne 0) {
    throw 'Could not seed the isolated acceptance database.'
}
$env:BROWSER_TEST_ALLOW_WRITES = 'isolated'
$env:BROWSER_TEST_BASE_URL = 'http://127.0.0.1:18081'

if (-not $env:CHROMIUM_EXECUTABLE_PATH) {
    $env:CHROMIUM_EXECUTABLE_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
}
if (-not (Test-Path -LiteralPath $env:CHROMIUM_EXECUTABLE_PATH)) {
    throw 'Set CHROMIUM_EXECUTABLE_PATH to an installed Chromium-based browser.'
}

Push-Location (Join-Path $workspaceDirectory 'frontend')
try {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCommand) {
        $nodeExecutable = $nodeCommand.Source
    }
    else {
        $nodeExecutable = Join-Path $env:USERPROFILE `
            '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    }
    if (-not (Test-Path -LiteralPath $nodeExecutable)) {
        throw 'Install Node.js or add its executable to PATH.'
    }

    $nodeArguments = @()
    if (-not (Test-Path -LiteralPath (Join-Path $PWD 'node_modules\playwright-core'))) {
        $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
        if ($npmCommand) {
            & $npmCommand.Source ci
            if ($LASTEXITCODE -ne 0) {
                throw 'Could not install locked frontend dependencies.'
            }
        }
        else {
            $codexRegister = Join-Path $workspaceDirectory `
                'outputs\react-browser-runtime\register.mjs'
            if (-not (Test-Path -LiteralPath $codexRegister)) {
                throw 'Run npm ci in frontend or add npm to PATH.'
            }
            $codexRegisterUrl = [System.Uri]::new($codexRegister).AbsoluteUri
            $nodeArguments += @('--import', $codexRegisterUrl)
        }
    }
    $nodeArguments += @('--test', 'browser-tests/*.test.mjs')
    & $nodeExecutable @nodeArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'React browser acceptance tests failed.'
    }
}
finally {
    Pop-Location
}
