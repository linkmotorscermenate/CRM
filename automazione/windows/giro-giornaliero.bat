@echo off
REM Il giro che parte da solo ogni mattina, versione Windows.
REM Lo lancia l'Utilita di pianificazione (vedi attiva.txt qui accanto).
REM Per lanciarlo a mano conviene usare giro-adesso.bat, che a fine giro
REM mostra com'e' andata invece di chiudere subito la finestra.

setlocal enabledelayedexpansion
cd /d "%~dp0..\.."

REM Il programma scrive accenti, euro e altri segni fuori dall'alfabeto inglese.
REM Senza queste tre righe Windows non sa come metterli nel registro e il giro
REM si pianta a meta' con un errore di codifica.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if not exist "output" mkdir "output"
set "REGISTRO=output\registro.log"

REM Il registro non deve crescere all'infinito: oltre i 2 MB lo mettiamo da
REM parte come registro-vecchio.log e si riparte da un file pulito.
if exist "%REGISTRO%" for %%F in ("%REGISTRO%") do (
  if %%~zF GTR 2000000 move /y "%REGISTRO%" "output\registro-vecchio.log" >nul
)

echo. >> "%REGISTRO%"
echo ===== %date% %time% ===== >> "%REGISTRO%"

REM --------------------------------------------------------------------
REM Trovare Python. Su Windows puo' chiamarsi in tre modi diversi, e ce n'e'
REM un quarto che sembra Python ma non lo e': il finto python.exe dentro
REM WindowsApps, che apre il Microsoft Store e basta. Quello va saltato.
REM --------------------------------------------------------------------
set "PYEXE="
set "PYARG="

REM 1) il lanciatore ufficiale "py", quello che installa python.org
where py >nul 2>&1
if not errorlevel 1 (
  set "PYEXE=py"
  set "PYARG=-3"
)

REM 2) un python.exe vero nel PERCORSO, scartando quello del Microsoft Store
if not defined PYEXE (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PYEXE (
      echo(%%P| find /i "\WindowsApps\" >nul
      if errorlevel 1 set "PYEXE=%%P"
    )
  )
)

REM 3) installato solo per questo utente, senza essere finito nel PERCORSO
if not defined PYEXE (
  for /f "delims=" %%P in ('dir /b /s "%LOCALAPPDATA%\Programs\Python\python.exe" 2^>nul') do (
    if not defined PYEXE set "PYEXE=%%P"
  )
)

REM 4) installato per tutti
if not defined PYEXE (
  for /f "delims=" %%P in ('dir /b /s "%ProgramFiles%\Python*\python.exe" 2^>nul') do (
    if not defined PYEXE set "PYEXE=%%P"
  )
)

if not defined PYEXE (
  echo PYTHON NON INSTALLATO. >> "%REGISTRO%"
  echo Installarlo con: winget install -e --id Python.Python.3.13 >> "%REGISTRO%"
  echo Oppure da python.org, spuntando "Add python.exe to PATH". >> "%REGISTRO%"
  echo Il finto python.exe del Microsoft Store non va bene: non esegue niente. >> "%REGISTRO%"
  endlocal
  exit /b 2
)

echo Python: %PYEXE% %PYARG% >> "%REGISTRO%"

REM --no-apri: nessuna finestra che salta su da sola.
REM (--notifica non c'e': quelle sono le notifiche del Mac.)
REM Quello che si scrive dopo il nome del .bat viene passato al programma:
REM per una prova veloce da 20 annunci per fascia, giro-giornaliero.bat --prova
"%PYEXE%" %PYARG% cerca.py --no-apri %* >> "%REGISTRO%" 2>&1
set ESITO=%errorlevel%

if not %ESITO%==0 echo GIRO FALLITO ^(codice %ESITO%^) >> "%REGISTRO%"

endlocal & exit /b %ESITO%
