@echo off
setlocal
title Ricerca auto - Link Motors
cd /d "%~dp0"

echo ============================================
echo   RICERCA AUTO - avvio del programma
echo ============================================
echo.
echo Tieni aperta questa finestra mentre usi il sito.
echo Per fermarlo: premi Ctrl+C oppure chiudi la finestra.
echo.

set "PYEXE="

rem === 1) Installazione locale di Python (il metodo piu' affidabile) ===
for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
) do (
    if not defined PYEXE if exist "%%~D" set "PYEXE=%%~D"
)

rem === 2) Launcher "py" ===
if not defined PYEXE (
    for /f "tokens=1" %%v in ('py --version 2^>nul') do if /i "%%v"=="Python" set "PYEXE=py"
)

rem === 3) "python" ma solo se e' quello vero (lo stub dello Store non stampa "Python") ===
if not defined PYEXE (
    for /f "tokens=1" %%v in ('python --version 2^>nul') do if /i "%%v"=="Python" set "PYEXE=python"
)

if not defined PYEXE goto nopython

echo Avvio con: %PYEXE%
echo.
"%PYEXE%" server.py
goto fine

:nopython
echo.
echo *** ERRORE: Python non e' installato su questo computer. ***
echo.
echo Scaricalo da:  https://www.python.org/downloads/
echo Durante l'installazione clicca "Install Now".
echo Poi rilancia questo file.
echo.
pause
exit /b 1

:fine
echo.
echo Il programma si e' chiuso.
pause
