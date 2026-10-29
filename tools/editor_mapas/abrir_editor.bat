@echo off
rem Editor de mapas del servidor (mapas .mpc + NPC y monstruos de AO). Necesita Python 3, Pillow y numpy:  pip install pillow numpy
rem Lee los .pak y la carpeta map\ del CLIENTE. Por defecto C:\AO\Angels Online; cambia con la variable AO_CLIENTE o pasando la carpeta como primer argumento.
rem Los NPC y monstruos se escriben en server\plantillas\<mapa>.json (hay que reiniciar el servidor para verlos).
cd /d "%~dp0"
if "%AO_CLIENTE%"=="" (set CLI=C:\AO\Angels Online) else (set CLI=%AO_CLIENTE%)
py -3 editor_mapas.py "%CLI%" 8770
pause
