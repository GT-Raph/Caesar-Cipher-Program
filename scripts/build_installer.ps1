param([string]$Compiler = '.tools/InnoSetup/ISCC.exe')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Install Inno Setup 6 and pass its ISCC.exe path with -Compiler.' }
    $payload = 'dist/windows-0.3.1/CipherVault.exe'
    if (-not (Test-Path -LiteralPath $payload)) { throw 'Run scripts/build_windows.ps1 first.' }
    & $Compiler 'installer/CipherVault.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
    $installer = 'dist/installers/CipherVault-Setup-0.3.1-x64.exe'
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
    "$hash  CipherVault-Setup-0.3.1-x64.exe" | Set-Content 'dist/installers/SHA256.txt' -Encoding ASCII
} finally { Pop-Location }
