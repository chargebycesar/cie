# Construye el instalador de Boletines IRVE.
#
#   .\empaquetar\construir.ps1                     -> carpeta lista y instalador
#   .\empaquetar\construir.ps1 -Firmar             -> ademas firma los .exe
#
# Deja todo en  empaquetar\salida\
#
# Hace falta, solo en el ordenador de quien construye:
#   - Conexion a internet la primera vez (se baja el Python empotrado)
#   - Inno Setup 6   https://jrsoftware.org/isdl.php
#   - Para firmar: signtool (viene con el SDK de Windows) y tu certificado .pfx

[CmdletBinding()]
param(
    [switch]$Firmar,
    [string]$Certificado = $env:BOLETINES_PFX,
    [string]$ClaveCertificado = $env:BOLETINES_PFX_PASS,
    [string]$VersionPython = "3.12.8",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$trabajo = Join-Path $PSScriptRoot "trabajo"
$salida = Join-Path $PSScriptRoot "salida"
$app = Join-Path $trabajo "app"
$python = Join-Path $app "python"

Write-Host "== Boletines IRVE $Version ==" -ForegroundColor Cyan

# ---------------------------------------------------------------- limpieza
Remove-Item $trabajo -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $app, $salida | Out-Null

# ------------------------------------------------- 1. Python empotrado
# Asi el cliente no tiene que instalar Python: va dentro del programa.
$zip = Join-Path $PSScriptRoot "python-embed-$VersionPython.zip"
if (-not (Test-Path $zip)) {
    $url = "https://www.python.org/ftp/python/$VersionPython/python-$VersionPython-embed-amd64.zip"
    Write-Host "Descargando Python empotrado..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $url -OutFile $zip
}
Expand-Archive -Path $zip -DestinationPath $python -Force

# El Python empotrado no mira site-packages hasta que se le dice
$pth = Get-ChildItem $python -Filter "python*._pth" | Select-Object -First 1
if ($pth) {
    $texto = Get-Content $pth.FullName
    if ($texto -notcontains "import site") { Add-Content $pth.FullName "import site" }
    if ($texto -notcontains "Lib\site-packages") { Add-Content $pth.FullName "Lib\site-packages" }
}

# ------------------------------------------------- 2. las librerias
Write-Host "Instalando PyMuPDF..." -ForegroundColor Yellow
$getpip = Join-Path $PSScriptRoot "get-pip.py"
if (-not (Test-Path $getpip)) {
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
}
& "$python\python.exe" $getpip --no-warn-script-location | Out-Null
& "$python\python.exe" -m pip install --no-warn-script-location `
    -r (Join-Path $raiz "requisitos.txt") | Out-Null

# ------------------------------------------------- 3. la aplicacion
Write-Host "Copiando la aplicacion..." -ForegroundColor Yellow
foreach ($f in @("nucleo.py", "cie_pdf.py", "cie_libreoffice.py", "servidor.py",
                 "config.json", "LEEME.md", "requisitos.txt")) {
    Copy-Item (Join-Path $raiz $f) $app
}
Copy-Item (Join-Path $raiz "web") $app -Recurse
Copy-Item (Join-Path $raiz "plantillas") $app -Recurse
New-Item -ItemType Directory -Force -Path (Join-Path $app "salida") | Out-Null

# Arrancador que no necesita Python instalado en el sistema
@'
@echo off
title Boletines IRVE
cd /d "%~dp0"
start "" /B python\python.exe servidor.py
'@ | Set-Content (Join-Path $app "Boletines IRVE.bat") -Encoding ASCII

# ------------------------------------------------- 4. el instalador
$iss = Join-Path $PSScriptRoot "boletines.iss"
$inno = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($inno) {
    Write-Host "Construyendo el instalador..." -ForegroundColor Yellow
    & $inno "/DVersionApp=$Version" "/DCarpetaApp=$app" "/DCarpetaSalida=$salida" $iss
} else {
    Write-Host "Inno Setup no esta instalado: te dejo la carpeta lista en $app" -ForegroundColor Yellow
    Write-Host "  Descargalo de https://jrsoftware.org/isdl.php y vuelve a ejecutar." -ForegroundColor Yellow
}

# ------------------------------------------------- 5. la firma
if ($Firmar) {
    if (-not $Certificado -or -not (Test-Path $Certificado)) {
        throw "No encuentro el certificado. Pasa -Certificado ruta\tu.pfx o pon BOLETINES_PFX."
    }
    $signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse `
        -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "x64" } | Select-Object -First 1
    if (-not $signtool) { throw "No encuentro signtool.exe. Instala el SDK de Windows." }

    Get-ChildItem $salida -Filter *.exe | ForEach-Object {
        Write-Host "Firmando $($_.Name)..." -ForegroundColor Yellow
        & $signtool.FullName sign /fd SHA256 /f $Certificado /p $ClaveCertificado `
            /tr http://timestamp.digicert.com /td SHA256 $_.FullName
        & $signtool.FullName verify /pa $_.FullName
    }
}

Write-Host "Listo. Todo en $salida" -ForegroundColor Green
