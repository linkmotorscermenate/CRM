@echo off
REM Il giro lanciato a mano, con doppio clic.
REM Fa lo stesso lavoro di giro-giornaliero.bat, ma alla fine mostra come e'
REM andata e apre il report, invece di chiudere la finestra all'istante.

cd /d "%~dp0..\.."
chcp 65001 >nul

echo Ricerca auto in corso. Ci vogliono alcuni minuti: non chiudere la finestra.
echo.

call "%~dp0giro-giornaliero.bat"
set ESITO=%errorlevel%

echo.
echo ----- ultime righe di output\registro.log -----
powershell -NoProfile -Command "Get-Content -LiteralPath 'output\registro.log' -Tail 25 -Encoding UTF8"
echo -----------------------------------------------
echo.

if %ESITO%==0 (
  echo Giro completato. Apro il report.
  start "" "output\ultimo.html"
) else (
  echo GIRO NON RIUSCITO ^(codice %ESITO%^). Il motivo e' scritto qui sopra.
)

echo.
pause
