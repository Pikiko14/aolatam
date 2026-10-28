"""Deja en parches/launcher/ los paquetes que el START.EXE de IGG baja para actualizarse:
el de informacion (u<version>.pak) y un mini-pak por archivo (<carpeta>/<nombre>.pak).

Se generan en la PC y se suben al VPS: con el zlib 1.2.11 del VPS el launcher no
llegaba a fusionarlos (con el zlib-ng de la PC si). Ver cliente_local._info_del_parche.

Uso: python -I tools/generar_paquetes_launcher.py   (despues de parche.generar())
"""
import os
import pathlib
import shutil
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
os.environ['AO_PARCHE_EN_LAUNCHER'] = '1'
import configuracion as cf  # noqa: E402
cf.PARCHE_EN_LAUNCHER = True
import cliente_local as cl  # noqa: E402
import parche  # noqa: E402

est = parche.estado()
dest = parche.DESTINO / 'launcher'
shutil.rmtree(dest, ignore_errors=True)
dest.mkdir(parents=True)
n = 0
for nombre, datos in cl.entradas_del_launcher().items():
    carpeta, _, base = nombre.rpartition(chr(92))
    if not carpeta:
        continue
    f = dest.joinpath(*carpeta.split(chr(92))) / (base + '.pak')
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(parche.armar_pak({nombre: datos}))
    n += 1
(dest / (cl._nombre_info(est) + '.pak')).write_bytes(cl._info_del_parche(est))
print('version', est['version'], '-', n, 'mini-paks + informacion en', dest)
