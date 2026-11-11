"""Un retrato por forma para el arbol de evolucion de la mascota (10/11/2026: "algunos se ven el mismo icono").

pet.xml reparte pocos retratos (頭像編號) entre muchas formas: Baby y Heady Dragon llevan el 11526, Earth, Icy y Hell
Dragon el 11528... Aqui se saca uno de cada sprite (圖號1) de las lineas que evolucionan, de su pose de espera de frente
(direccion 7 del .spr).

Deja en parches/extras shape/pet/rNNNN.shp (44 x 44, la ficha de abajo) y sNNNN.shp (26 x 26, dentro de cada cuadro
del arbol: "pudiese salir la imagen al lado de cada cuadrito"), sus <icon> en setting/peticon.xml (PRIMER_ICONO + N y
PRIMER_PEQUENO + N) y server/plantillas/retratos_arbol.json ({sprite: N}, que lee server/arbol_mascotas.py). Los
numeros no cambian de una pasada a otra: los que ya estan se quedan y los nuevos van detras.

    python tools/retratos_arbol.py
"""
import json
import pathlib
import re
import sys
import zlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'server'))
import mascota_abismo as ma  # noqa: E402
import paks_cliente  # noqa: E402
import spr_ewsp  # noqa: E402

CLIENTE = pathlib.Path(r'C:\AO\Angels Online')
EXTRAS = RAIZ / 'parches' / 'extras'
MASCOTAS = RAIZ / 'server' / 'plantillas' / 'mascotas.json'
SALIDA = RAIZ / 'server' / 'plantillas' / 'retratos_arbol.json'
PRIMER_ICONO = 70000
PRIMER_PEQUENO = 72000
ETAPAS_ARBOL = ('原型', '初階', '中階', '高階')
SEP = chr(92)
MARCA = 'aolat retratos arbol'
PLANTILLA = SEP.join(('shape', 'pet', 'p001.shp'))


def _archivos_cliente():
    """{ruta en mayusculas: bytes o (pak, inicio, largo)} ganando el pak de numero mas alto (los .bak, sin parches
    nuestros), mas lo nuestro de parches/extras."""
    out = {}
    paks = [p for p in CLIENTE.glob('*.pak') if paks_cliente.numero(p.name) >= -1]
    for pak in sorted(paks, key=lambda p: paks_cliente.numero(p.name)):
        fuente = pak.with_name(pak.name + '.bak')
        datos = (fuente if fuente.exists() else pak).read_bytes()
        for n, _c, cs, _u, off in paks_cliente._directorio(datos):
            u = n.upper()
            if u.endswith('.OBD') or u.endswith('_WAIT.SPR'):
                out[u] = (datos, off, cs)
    for f in (EXTRAS / 'shape' / 'mon').rglob('*_wait.spr'):
        out[('SHAPE' + SEP + str(f.relative_to(EXTRAS / 'shape')).replace('/', SEP)).upper()] = f.read_bytes()
    obd = EXTRAS / 'setting' / 'npc.obd'
    if obd.is_file():
        out['SETTING' + SEP + 'NPC.OBD'] = obd.read_bytes()
    return out


def _leer(v):
    if isinstance(v, bytes):
        return v
    datos, off, cs = v
    return zlib.decompress(datos[off:off + cs], -15)


def carpetas(archivos) -> dict:
    """{sprite: ruta del _Wait.spr} de todos los .obd."""
    out = {}
    for nombre, v in archivos.items():
        if not nombre.endswith('.OBD'):
            continue
        texto = _leer(v).decode('latin-1')
        for bloque in texto.split('[OBJECT]'):
            s = re.search(r'Sequence\s*=\s*(\d+)', bloque)
            d = re.search(r'Directory\s*=\s*(\S+)', bloque)
            w = re.search(r'SpriteFile\s*=\s*Wait\s*,\s*(\S+)', bloque)
            if s and d and w:
                out[int(s.group(1))] = ('SHAPE' + d.group(1).rstrip(SEP) + SEP + w.group(1)).upper()
    return out


def de_frente(spr: bytes):
    """La primera pose de espera en diagonal, frente-izquierda (direccion 6: el cuarto frame de cada pose). De frente
    (direccion 7) un submarino como el Dive Hunter parecia una botella ("se ve raro en el nuestro", 10/11/2026)."""
    frames, _k = spr_ewsp.leer(spr)
    return frames[min(3, len(frames) - 1)][0]


def main():
    tabla = json.loads(MASCOTAS.read_text(encoding='utf-8'))
    sprites = sorted({int(f['tipo']) for f in tabla.values() if f.get('tipo') and f.get('etapa') in ETAPAS_ARBOL})
    previos = json.loads(SALIDA.read_text(encoding='utf-8')) if SALIDA.is_file() else {}
    ids = {int(k): int(v) for k, v in previos.items()}          # sprite -> N
    archivos = _archivos_cliente()
    ruta_de = carpetas(archivos)
    destino = EXTRAS / 'shape' / 'pet'
    destino.mkdir(parents=True, exist_ok=True)
    hechos, faltan = 0, []
    for s in sprites:
        ruta = ruta_de.get(s)
        if not ruta or ruta not in archivos:
            faltan.append(s)
            continue
        try:
            im = de_frente(_leer(archivos[ruta]))
        except Exception as e:  # noqa: BLE001
            faltan.append(s)
            print('  %d: %s' % (s, e))
            continue
        if s not in ids:
            ids[s] = max(ids.values(), default=-1) + 1
        (destino / ('r%04d.shp' % ids[s])).write_bytes(ma._tlhs_suelto(ma._cuadrado(im, 44), PLANTILLA, 21, 43))
        (destino / ('s%04d.shp' % ids[s])).write_bytes(ma._tlhs_suelto(ma._cuadrado(im, 26), PLANTILLA, 0, 0))
        # (El pequeno con el origen en 0,0: con el del grande, 12,25, el cliente lo pintaba desplazado fuera del cuadro.)
        hechos += 1
    ids = {s: n for s, n in ids.items() if (destino / ('r%04d.shp' % n)).is_file()}
    SALIDA.write_text(json.dumps({str(k): v for k, v in sorted(ids.items())}, indent=0) + '\n', encoding='utf-8')
    # Con su propia marca: la de mascota_abismo (_xml_con) quitaria las entradas de la Abyss.
    texto, bom, nl = ma._texto_base(SEP.join(('setting', 'peticon.xml')))
    texto = ma._sin_bloque(texto, '<!-- %s -->' % MARCA, '<!-- /%s -->' % MARCA)
    carpeta = SEP + 'pet' + SEP
    lineas = []
    for n in sorted(ids.values()):
        lineas.append('\t<icon id="%d" pos="12,23" dir="%s" normal="r%04d" focus="normal" down="normal" '
                      'disable="normal"/>' % (PRIMER_ICONO + n, carpeta, n))
        lineas.append('\t<icon id="%d" dir="%s" normal="s%04d" focus="normal" down="normal" disable="normal"/>'
                      % (PRIMER_PEQUENO + n, carpeta, n))
    bloque = nl.join(['\t<!-- %s -->' % MARCA] + lineas + ['\t<!-- /%s -->' % MARCA]) + nl
    fin = texto.rindex('</')
    ma._guardar(SEP.join(('setting', 'peticon.xml')), texto[:fin] + bloque + texto[fin:], bom)
    print('retratos: %d hechos, %d sin sprite %s' % (hechos, len(faltan), faltan[:10]))


if __name__ == '__main__':
    main()
