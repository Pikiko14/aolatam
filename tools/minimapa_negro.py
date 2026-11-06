"""El minimapa del Dark Cavern (stage 900) en negro (05/11/2026: "que el dark cavern el minimapa salga negro").

El stage 900 usaba el minimapa del Training Cave (雷達圖="smap\\046"), que enseña todo el mapa. Este script copia
shape\\smap\\046.shp con todos sus pixeles casi negros (no 0, que puede ser el color transparente) como
shape\\smap\\900.shp y deja la fila del stage 900 de parches/extras/setting/eng/stage.xml apuntando a ella.

    python tools/minimapa_negro.py
    python tools/publicar_setting.py stage.xml --sin-copiar
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))

STAGE = 900
ORIGEN = 'SHAPE\\SMAP\\046.SHP'
SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'smap' / ('%03d.shp' % STAGE)
STAGE_XML = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml'
CASI_NEGRO = (8, 8, 8)


def negro(datos: bytes) -> bytes:
    import oscurecer_torre as ot
    antes = ot.oscuro
    ot.oscuro = lambda r, g, b: CASI_NEGRO
    try:
        return ot.oscurecer_shp(datos)
    finally:
        ot.oscuro = antes


def main():
    import cliente_local
    raw = cliente_local._extraer_archivo_pak(pathlib.Path(cliente_local.ruta_cliente()) / 'data1.pak', ORIGEN)
    if not raw:
        raise SystemExit('no esta %s en data1.pak' % ORIGEN)
    nuevo = negro(raw)
    if nuevo == raw:
        raise SystemExit('no se pudo oscurecer %s' % ORIGEN)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(nuevo)
    txt = STAGE_XML.read_bytes().decode('utf-8')
    viejo = '編號="%d" ' % STAGE
    i = txt.index(viejo)
    fin = txt.index('/>', i)
    fila = txt[i:fin]
    fila_nueva = fila.replace('雷達圖="smap\\046"', '雷達圖="smap\\%03d"' % STAGE)
    if fila_nueva != fila:
        STAGE_XML.write_bytes((txt[:i] + fila_nueva + txt[fin:]).encode('utf-8'))
    print('minimapa negro:', SALIDA, len(nuevo), 'bytes; stage.xml:', 'cambiado' if fila_nueva != fila else 'ya estaba')


if __name__ == '__main__':
    main()
