@echo off
rem Cliente propio AOF (LÖVE), no el angel.dat de IGG.
setlocal
set "ROOT=%~dp0.."
set "LOVE=%ROOT%\tools\love\love-11.5-win64\lovec.exe"
if not exist "%LOVE%" (
  echo Falta LÖVE. Baja tools\love\love-11.5-win64 o ejecuta:
  echo   powershell -File tools\instalar_love.ps1
  exit /b 1
)
cd /d "%ROOT%"
rem HUD y ventanas con los scripts originales y el canal Lua del servidor (Item Mall, subasta, raid...).
rem Para volver al HUD simple: set AO_NATIVO= antes de lanzar.
if not defined AO_NATIVO set "AO_NATIVO=1"
"%LOVE%" cliente %*
