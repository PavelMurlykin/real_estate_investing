param(
    [string[]]$TestPath = @()
)

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
$projectName = 'rei-backend-tests-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$composeArguments = @('compose', '--project-name', $projectName, '-f', $composeFile)
$previousEnvironment = @{}
foreach ($variableName in @('BROWSER_TEST_DATABASE_PASSWORD', 'BROWSER_TEST_SECRET_KEY')) {
    $previousEnvironment[$variableName] = [Environment]::GetEnvironmentVariable($variableName)
    [Environment]::SetEnvironmentVariable($variableName, (New-RandomSecret))
}

try {
    # Only db and web start: this run publishes no ports and uses no working data.
    & docker @composeArguments up -d --build --wait db web
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not start the isolated backend test stack.'
    }

    & docker @composeArguments exec -T `
        -e REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=False `
        web python -m pytest -q @TestPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Backend tests failed.'
    }
}
finally {
    & docker @composeArguments down --volumes --remove-orphans
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not clean up isolated project $projectName."
    }
    foreach ($variableName in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($variableName, $previousEnvironment[$variableName])
    }
}
