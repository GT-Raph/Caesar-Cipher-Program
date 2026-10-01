param([string]$Environment = '.venv-release')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot "$Environment/Scripts/python.exe"
$fletExe = Join-Path $projectRoot "$Environment/Scripts/flet.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create the Python 3.14 release environment first.' }
$workDirectory = Join-Path $projectRoot 'build/packaging'
$outputDirectory = Join-Path $projectRoot 'dist/windows-0.3.1'
# Flet pack cleans its build directory and selected output directory.
foreach ($target in @($workDirectory, $outputDirectory)) {
    $resolvedTarget = [System.IO.Path]::GetFullPath($target)
    if (-not $resolvedTarget.StartsWith($projectRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Build output must stay inside the project.'
    }
}
Push-Location $projectRoot
try {
    & $pythonExe -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    New-Item -ItemType Directory -Path $workDirectory -Force | Out-Null
    Push-Location $workDirectory
    try {
        & $fletExe pack ../../main.py --name CipherVault --product-name 'Cipher Vault' --product-version 0.3.1 --file-version 0.3.1.0 --distpath ../../dist/windows-0.3.1 --yes
        if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
    } finally { Pop-Location }
    $candidateExe = Join-Path $outputDirectory 'CipherVault.exe'
    $candidate = Start-Process -FilePath $candidateExe -ArgumentList '--self-test','dist/windows-0.3.1/runtime-check.json' -WorkingDirectory $projectRoot -WindowStyle Hidden -Wait -PassThru
    if ($candidate.ExitCode -ne 0) { throw 'Bundled runtime check failed.' }
    $report = Get-Content -LiteralPath (Join-Path $outputDirectory 'runtime-check.json') -Raw | ConvertFrom-Json
    if ($report.status -ne 'passed') { throw 'Bundled runtime report did not pass.' }
    Get-FileHash -LiteralPath $candidateExe -Algorithm SHA256 | Format-List | Out-File (Join-Path $outputDirectory 'SHA256.txt')
} finally { Pop-Location }
