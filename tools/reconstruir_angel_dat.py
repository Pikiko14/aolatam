"""Reconstruye el angel.dat parcheado desde el UPX de IGG (14/11/2026).

El cliente vivo (parches/juego/angel.dat y C:/AO/Angels Online/angel.dat) no sale
solo de aplicar los scripts de tools/ sobre el UPX: antes de las secciones .aolat*
Windows reescribio .rsrc con UpdateResource (icono), y esa .rsrc es mas grande que
la del UPX virgen. Si se anaden .aolat* sobre el virgen, las VA cambian y el sha
no coincide; si se usa UpdateResource *despues* de .aolat*, Windows corre las
secciones y el juego se cierra (ver tools/icono_angel_dat_en_sitio.py).

Orden que reproduce el binario actual byte a byte:

  1. UPX -d sobre angel_igg.dat
  2. Trasplantar .rsrc (cabecera de seccion + DataDirectory RESOURCE +
     SizeOfInitializedData + bytes) desde un angel.dat de referencia que ya
     lleva el icono historico — por defecto parches/juego/angel.dat
  3. parche_canal_lua  (.aolat)
  4. parche_prop50_exe (.aolatp)
  5. parche_bolsa119_exe
  6. parche_prop50_huecos_exe (.aolatq)
  7. parche_teclas_aof (.aolatk)
  8. sin_acuerdo_angel_dat
  9. seleccion_angel_dat
 9b. parche_tooltip_verde (.aolatv)
 9c. parche_clima_exe (.aolatw): climas propios del s2c 0x0015 (niebla, brasas...)
 10. (opcional) icono_angel_dat_en_sitio — cambia el emblema; rompe el sha

Alternativa --icono-update: tras el UPX aplica UpdateResource con launcher/icono.ico
(como tools/icono_angel_dat.py). Sirve para un cliente jugable nuevo, pero el .rsrc
no coincide con el historico y el sha256 sera otro.

    python tools/reconstruir_angel_dat.py
    python tools/reconstruir_angel_dat.py -o parches/juego/angel.dat --verificar
    python tools/reconstruir_angel_dat.py --icono-update -o /tmp/angel_nuevo.dat
    python tools/reconstruir_angel_dat.py --solo-verificar
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from parche_canal_lua import _alinear, _secciones, parchear as parche_canal  # noqa: E402
from parche_prop50_exe import parchear as parche_prop50  # noqa: E402
from parche_bolsa119_exe import parchear as parche_bolsa119  # noqa: E402
from parche_prop50_huecos_exe import parchear as parche_huecos  # noqa: E402
from parche_teclas_aof import parchear as parche_teclas  # noqa: E402
import sin_acuerdo_angel_dat as sin_acuerdo  # noqa: E402
import seleccion_angel_dat as seleccion  # noqa: E402
from parche_tooltip_verde import parchear as parche_verde  # noqa: E402
from parche_clima_exe import parchear as parche_clima  # noqa: E402

IGG_DEF = pathlib.Path(r'C:\AO\Angels Online\angel_igg.dat')
REF_DEF = RAIZ / 'parches' / 'juego' / 'angel.dat'
UPX_DEF = pathlib.Path(r'C:\AO\herramientas\upx-4.2.4-win64\upx.exe')
ICO_DEF = RAIZ / 'launcher' / 'icono.ico'
EMBLEMA_DEF = RAIZ / 'launcher' / 'emblema.png'


def sha256(ruta: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for trozo in iter(lambda: f.read(1 << 20), b''):
            h.update(trozo)
    return h.hexdigest()


def _rsrc(secs):
    for s in secs:
        if s['nombre'].startswith(b'.rsrc'):
            return s
    raise SystemExit('no hay seccion .rsrc')


def transplantar_rsrc(dst: bytearray, ref: bytes) -> bytearray:
    """Copia el .rsrc historico (y los campos PE que lo describen) sobre el UPX virgen."""
    pe_d, _tab_d, secs_d = _secciones(dst)
    pe_r, _tab_r, secs_r = _secciones(ref)
    rd, rr = _rsrc(secs_d), _rsrc(secs_r)
    dst[rd['cab']:rd['cab'] + 40] = ref[rr['cab']:rr['cab'] + 40]
    # SizeOfInitializedData (OptionalHeader + 8) y DataDirectory RESOURCE (PE32: +96 + 2*8)
    dst[pe_d + 24 + 8:pe_d + 24 + 12] = ref[pe_r + 24 + 8:pe_r + 24 + 12]
    dd = 24 + 96 + 2 * 8
    dst[pe_d + dd:pe_d + dd + 8] = ref[pe_r + dd:pe_r + dd + 8]
    opt = pe_d + 24
    al_sec = struct.unpack_from('<I', dst, opt + 32)[0]
    struct.pack_into('<I', dst, opt + 56, _alinear(rr['va'] + max(rr['vsz'], rr['rsz']), al_sec))
    end = rr['rptr'] + rr['rsz']
    if len(dst) < end:
        dst.extend(b'\0' * (end - len(dst)))
    dst[rr['rptr']:end] = ref[rr['rptr']:end]
    del dst[end:]
    return dst


def descomprimir_upx(igg: pathlib.Path, upx: pathlib.Path, destino: pathlib.Path) -> None:
    shutil.copyfile(igg, destino)
    subprocess.run([str(upx), '-d', '-q', str(destino)], check=True)


def aplicar_icono_update(exe: pathlib.Path, ico: pathlib.Path) -> None:
    import icono_angel_dat
    icono_angel_dat.main(str(exe), str(ico))


def aplicar_parches_codigo(d: bytes) -> bytes:
    d = parche_canal(d)
    d = parche_prop50(d)
    d = parche_bolsa119(d)
    d = parche_huecos(d)
    d, _info = parche_teclas(d)
    return d


def aplicar_parches_en_sitio(ruta: pathlib.Path) -> None:
    d = bytearray(ruta.read_bytes())
    for o, antes, despues, _que in sin_acuerdo.PARCHES:
        est = sin_acuerdo.estado(d, o, antes, despues)
        if est.startswith('desconocido'):
            raise SystemExit('sin_acuerdo: no es el angel.dat esperado')
        if est == 'original':
            d[o:o + len(despues)] = despues
    ruta.write_bytes(bytes(d))
    seleccion.parchear(ruta, ver=False)


def aplicar_emblema(ruta: pathlib.Path, emblema: pathlib.Path) -> None:
    import icono_angel_dat_en_sitio as en_sitio
    from PIL import Image
    d = bytearray(ruta.read_bytes())
    tam_antes = len(d)
    em = Image.open(emblema).convert('RGBA')
    em = em.crop(em.getbbox())
    lado = max(em.size)
    cuadro = Image.new('RGBA', (lado, lado))
    cuadro.alpha_composite(em, ((lado - em.width) // 2, (lado - em.height) // 2))
    for o, tam in en_sitio.iconos_png(d):
        w, h = struct.unpack_from('>II', d, o + 16)
        nuevo = en_sitio.png_justo(cuadro, w, tam)
        assert len(nuevo) == tam
        d[o:o + tam] = nuevo
        print('icono %dx%d: %d bytes, en su sitio' % (w, h, tam))
    assert len(d) == tam_antes
    ruta.write_bytes(bytes(d))


def reconstruir(
    igg: pathlib.Path,
    salida: pathlib.Path,
    *,
    upx: pathlib.Path,
    referencia: pathlib.Path | None,
    icono_update: bool,
    ico: pathlib.Path,
    emblema: pathlib.Path | None,
) -> pathlib.Path:
    salida.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='reconstruir_angel_') as tmp:
        work = pathlib.Path(tmp) / 'angel.dat'
        print('1/10 UPX -d', igg)
        descomprimir_upx(igg, upx, work)
        print('   ', work.stat().st_size, 'bytes')

        if icono_update:
            print('2/10 UpdateResource', ico)
            aplicar_icono_update(work, ico)
            print('   ', work.stat().st_size, 'bytes')
        else:
            if referencia is None or not referencia.is_file():
                raise SystemExit(
                    'hace falta --referencia (angel.dat con el .rsrc historico) '
                    'o --icono-update')
            print('2/10 transplantar .rsrc desde', referencia)
            d = transplantar_rsrc(bytearray(work.read_bytes()), referencia.read_bytes())
            work.write_bytes(bytes(d))
            print('   ', work.stat().st_size, 'bytes')

        print('3-7/10 canal + prop50 + bolsa119 + huecos + teclas')
        work.write_bytes(aplicar_parches_codigo(work.read_bytes()))
        print('   ', work.stat().st_size, 'bytes')

        print('8-9/10 sin_acuerdo + seleccion')
        aplicar_parches_en_sitio(work)

        print('9b/10 tooltip verde (.aolatv)')
        work.write_bytes(parche_verde(work.read_bytes()))

        print('9c/10 climas propios (.aolatw)')
        work.write_bytes(parche_clima(work.read_bytes()))

        if emblema is not None:
            print('10/10 emblema en sitio', emblema)
            aplicar_emblema(work, emblema)
        else:
            print('10/10 emblema: omitido (el del .rsrc transplantado)')

        shutil.copyfile(work, salida)
    print('escrito', salida, salida.stat().st_size, 'bytes')
    print('sha256', sha256(salida))
    return salida


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--igg', type=pathlib.Path, default=IGG_DEF, help='angel.dat UPX de IGG')
    ap.add_argument('--upx', type=pathlib.Path, default=UPX_DEF, help='upx.exe')
    ap.add_argument('--referencia', type=pathlib.Path, default=REF_DEF,
                    help='angel.dat con el .rsrc historico (y sha esperado)')
    ap.add_argument('-o', '--salida', type=pathlib.Path, default=None,
                    help='destino (por defecto: junto a la referencia, angel.dat.reconstruido)')
    ap.add_argument('--icono-update', action='store_true',
                    help='usar UpdateResource con --ico en vez de transplantar .rsrc')
    ap.add_argument('--ico', type=pathlib.Path, default=ICO_DEF)
    ap.add_argument('--emblema', type=pathlib.Path, default=None, nargs='?', const=EMBLEMA_DEF,
                    help='despues, icono_angel_dat_en_sitio (rompe el sha historico)')
    ap.add_argument('--verificar', action='store_true',
                    help='exigir sha256 igual a --referencia')
    ap.add_argument('--solo-verificar', action='store_true',
                    help='solo compara sha de -o/--salida (o el vivo) contra la referencia')
    a = ap.parse_args()

    if a.solo_verificar:
        cand = a.salida or pathlib.Path(r'C:\AO\Angels Online\angel.dat')
        h1, h2 = sha256(cand), sha256(a.referencia)
        print(cand, h1)
        print(a.referencia, h2)
        if h1 != h2:
            raise SystemExit('no coinciden')
        print('ok: mismo sha256')
        return

    for p, nombre in ((a.igg, 'igg'), (a.upx, 'upx')):
        if not p.is_file():
            raise SystemExit('no esta %s: %s' % (nombre, p))
    if not a.icono_update and not a.referencia.is_file():
        raise SystemExit('no esta la referencia: %s' % a.referencia)

    salida = a.salida or (a.referencia.parent / 'angel.dat.reconstruido')
    reconstruir(
        a.igg, salida,
        upx=a.upx,
        referencia=None if a.icono_update else a.referencia,
        icono_update=a.icono_update,
        ico=a.ico,
        emblema=a.emblema,
    )
    if a.verificar:
        if a.icono_update or a.emblema is not None:
            raise SystemExit('--verificar no aplica con --icono-update ni --emblema')
        h1, h2 = sha256(salida), sha256(a.referencia)
        print('referencia', h2)
        if h1 != h2:
            raise SystemExit('sha256 distinto de la referencia')
        print('ok: mismo sha256 que la referencia')


if __name__ == '__main__':
    main()
