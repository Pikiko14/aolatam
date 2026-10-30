"""Atajo: lo mismo que `python tools/subir_mapa.py 900 ...` (ver tools/subir_mapa.py)."""
import pathlib
import subprocess
import sys

sys.exit(subprocess.call([sys.executable, str(pathlib.Path(__file__).with_name('subir_mapa.py')), '900'] + sys.argv[1:]))
