"""Pone el icono del launcher (launcher/icono.ico) en angel.dat, el exe del juego (31/10/2026).

OJO (12/11/2026): con el angel.dat que lleva secciones propias (.aolat*) detras de .rsrc NO sirve: UpdateResource las
corre y el juego se cierra. Para ese usar tools/icono_angel_dat_en_sitio.py, que cambia los PNG sin mover nada.

angel.dat viene comprimido con UPX: cambiarle el icono asi como viene lo rompe (0xc0000005 al arrancar). Primero se
descomprime con UPX (https://github.com/upx/upx/releases, upx-4.2.4-win64.zip; no esta en el repo) y despues se
reemplaza su grupo de iconos (101). Queda de 5,8 MB en vez de 1,7 MB, y probado: el juego entra y se juega igual.

    python tools/icono_angel_dat.py <angel.dat original> <salida> --upx <ruta a upx.exe>
"""
import argparse
import pathlib
import shutil
import subprocess
import ctypes, struct, sys
from ctypes import wintypes as w
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.LoadLibraryExW.restype = w.HMODULE
k.BeginUpdateResourceW.restype = w.HANDLE
k.BeginUpdateResourceW.argtypes = [w.LPCWSTR, w.BOOL]
k.FreeLibrary.argtypes = [w.HMODULE]
k.LoadLibraryExW.argtypes = [w.LPCWSTR, w.HANDLE, w.DWORD]
k.UpdateResourceW.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p, w.WORD, ctypes.c_void_p, w.DWORD]
k.EndUpdateResourceW.argtypes = [w.HANDLE, w.BOOL]
ENUM = ctypes.WINFUNCTYPE(w.BOOL, w.HMODULE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
RT_ICON, RT_GROUP_ICON = 3, 14

def nombres(exe, tipo):
    h = k.LoadLibraryExW(exe, None, 0x2)      # LOAD_LIBRARY_AS_DATAFILE
    out = []
    def cb(hm, t, n, p):
        out.append(n if n < 0x10000 else ctypes.wstring_at(n)); return True
    k.EnumResourceNamesW.argtypes = [w.HMODULE, ctypes.c_void_p, ENUM, ctypes.c_void_p]
    k.EnumResourceNamesW(h, tipo, ENUM(cb), None)
    k.FreeLibrary(h)
    return out

def main(exe, ico, solo_ver=False):
    grupos, iconos = nombres(exe, RT_GROUP_ICON), nombres(exe, RT_ICON)
    print('grupos', grupos, 'iconos', iconos)
    if solo_ver:
        return
    d = open(ico, 'rb').read()
    _, _, n = struct.unpack_from('<HHH', d, 0)
    entradas = [struct.unpack_from('<BBBBHHII', d, 6 + 16 * i) for i in range(n)]
    base = max([i for i in iconos if isinstance(i, int)] + [0]) + 1
    h = k.BeginUpdateResourceW(exe, False)
    if not h:
        raise SystemExit('BeginUpdateResource: %d' % ctypes.get_last_error())
    grp = struct.pack('<HHH', 0, 1, n)
    for j, (an, al, col, res, planos, bits, tam, off) in enumerate(entradas):
        datos = d[off:off + tam]
        buf = ctypes.create_string_buffer(datos, len(datos))
        assert k.UpdateResourceW(h, RT_ICON, base + j, 0, buf, len(datos))
        grp += struct.pack('<BBBBHHIH', an, al, col, res, planos, bits, tam, base + j)
    gbuf = ctypes.create_string_buffer(grp, len(grp))
    for g in grupos:                           # todos los grupos apuntan al icono nuevo
        nom = g if isinstance(g, int) else ctypes.c_wchar_p(g)
        assert k.UpdateResourceW(h, RT_GROUP_ICON, nom, 0, gbuf, len(grp)) or k.UpdateResourceW(h, RT_GROUP_ICON, nom, 1033, gbuf, len(grp))
    if not k.EndUpdateResourceW(h, False):
        raise SystemExit('EndUpdateResource: %d' % ctypes.get_last_error())
    print('listo:', n, 'tamanos')



if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('original')
    ap.add_argument('salida')
    ap.add_argument('--upx', required=True)
    ap.add_argument('--ico', default=str(pathlib.Path(__file__).resolve().parent.parent / 'launcher' / 'icono.ico'))
    a = ap.parse_args()
    shutil.copyfile(a.original, a.salida)
    subprocess.run([a.upx, '-d', '-q', a.salida], check=True)
    main(a.salida, a.ico)
