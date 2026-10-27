"""Genera parches/update27.pak y parches/version.json a mano (el servidor
tambien lo hace al arrancar). Ver server/parche.py."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import parche

if __name__ == '__main__':
    print(json.dumps(parche.generar(), indent=1, ensure_ascii=False))
