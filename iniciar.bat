@echo off
title Boletines IRVE - Comunidad de Madrid
cd /d "%~dp0"

set PY=
where python >nul 2>&1 && set PY=python
if "%PY%"=="" if exist "C:\Python314\python.exe" set PY=C:\Python314\python.exe
if "%PY%"=="" if exist "C:\Python313\python.exe" set PY=C:\Python313\python.exe
if "%PY%"=="" if exist "C:\Python312\python.exe" set PY=C:\Python312\python.exe

if "%PY%"=="" (
  echo.
  echo  No encuentro Python en este ordenador.
  echo  Instalalo desde https://www.python.org/downloads/ y marca
  echo  la casilla "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

%PY% -c "import pymupdf" >nul 2>&1
if errorlevel 1 (
  echo  Instalando la libreria que lee los PDF, un momento...
  %PY% -m pip install --user --quiet -r requisitos.txt
)

%PY% servidor.py
pause
