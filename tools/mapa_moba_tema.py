"""El aspecto propio del mapa del Angel MOBA (24/11/2026: "rediseña el mapa para que no parezca el de hbf").

El 918 sale del Holy Battlefield (112, tools/mapa_moba.py): la isla tropical con arena, palmeras, muros de piedra y
cascadas. Aqui se le pone el bioma del Crystal Grounds (341): suelo oscuro, agua turquesa, hongos gigantes,
estalactitas, rocas volcanicas, cristales y raices. Solo cambia el dibujo:

* LA COLISION Y EL TRAZADO NO SE TOCAN: de cada celda solo cambia el pincel (byte 0); el atributo de terreno y el agua
  profunda siguen igual, asi que los carriles, las bases, las torres y transitable.bin del servidor valen como estaban.
* SUELO: cada pincel del 112 va al del 341 de su misma clase (hierba -> suelo oscuro, arena -> tierra de camino,
  tierra -> suelo oscuro claro, roca -> musgo, agua -> agua turquesa).
* OBJETOS: los decorados (directorio \\stage\\) se cambian por uno del 341 del mismo tipo (arbol, arbusto, hongo, roca o
  muro, hierba, cristal) y que bloquee igual; los reflejos de agua y corales del mar tropical se quitan. Lo que no es
  decorado (las estatuas y guardianes de las bases, las marcas del servidor) se queda. Con semilla fija: siempre igual.
* MINIMAPA: el render del mapa nuevo, al tamano del minimapa del 112 (shape\\smap\\918.shp).
"""
import collections
import io
import os
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ED = RAIZ / 'tools' / 'editor_mapas'
TEMA = 341                       # Crystal Grounds
SEMILLA = 918
SMAP = RAIZ / 'parches' / 'extras' / 'shape' / 'smap' / '918.shp'
SMAP_TAM = (819, 768)            # el del 112 (320x300 celdas)

# clase del pincel (editor_mapas.clase_tile) -> pinceles del 341, con su peso
SUELO = {'hierba': [(21, 5), (20, 2)], 'tierra': [(20, 1)], 'arena': [(45, 3), (46, 1)], 'roca': [(64, 1)],
         'agua': [(65, 1)], 'agua_somera': [(65, 1)]}
QUITAR = ('光點', '珊瑚', '貝殼', '水中', '海星', '浪')


def _editor():
    """editor_mapas lee sys.argv al importarse (carpeta del cliente y puerto): se le deja vacio."""
    sys.path.insert(0, str(ED))
    guardado = sys.argv
    sys.argv = [guardado[0]]
    try:
        import editor_mapas as em
    finally:
        sys.argv = guardado
    if not em.INDEX:
        em.cargar()
        em.cargar_defs()
    return em


def tipo(d):
    """El tipo de decorado de una definicion de objeto (setting/*.obd), o None si no es decorado."""
    if not d or not d['directorio'].lower().startswith('\\stage'):
        return None
    n = d['nombre']
    if any(k in n for k in QUITAR):
        return 'quitar'
    if '水晶' in n:
        return 'cristal'
    if '牆' in n or '柱' in n:
        return 'muro'
    if '蕈' in n or '菇' in n:
        return 'hongo'
    if '矮樹叢' in n or '叢' in n or '蕨' in n or '荊棘' in n:
        return 'arbusto'
    if '樹' in n or '11TREE' in d['proceso']:
        return 'arbol'
    if '石' in n or '岩' in n or '鐘乳' in n:
        return 'roca'
    if any(k in n for k in ('草', '葉', '花', '星草', '幸運草', '針葉球', '邊條')):
        return 'hierba'
    return 'otro'


# Si en el 341 no hay de ese tipo, se toma de este otro (y el muro, de las estalactitas y rocas).
RESPALDO = {'muro': 'roca', 'otro': 'roca', 'arbol': 'hongo', 'arbusto': 'hierba', 'cristal': 'roca'}


def _bolsas(em, tema):
    """{(tipo, bloquea): [(id, cuantos)]} con los decorados del mapa del tema."""
    import mpcio
    m = mpcio.leer(em.datos('map/map%03d.mpc' % tema))
    c = collections.Counter(o[0] for o in m['objetos'])
    b = collections.defaultdict(list)
    for sid, n in c.items():
        d = em.DEFS.get(sid)
        t = tipo(d)
        if t and t != 'quitar' and em.sprite_obj(sid):
            b[(t, bool(d['bloquea']))].append((sid, n))
    return b


def _elegir(bolsas, t, bloquea, rng):
    for clave in ((t, bloquea), (RESPALDO.get(t), bloquea), (t, not bloquea), (RESPALDO.get(t), not bloquea),
                  ('roca', bloquea)):
        op = bolsas.get(clave)
        if op:
            ids, pesos = zip(*op)
            return rng.choices(ids, weights=pesos)[0]
    return None


def tematizar(m, em=None, tema=TEMA, semilla=SEMILLA):
    """Cambia el suelo y los decorados de m (dict de mpcio) al bioma del mapa `tema`. Devuelve un resumen."""
    em = em or _editor()
    rng = random.Random(semilla)
    w, h = m['w'], m['h']
    cel = bytearray(m['celdas'])
    clase = {}
    for i in range(w * h):
        p = cel[i * 6]
        if p not in clase:
            t = em.tileset(p)
            clase[p] = t[2] if t else 'tierra'
        ops = SUELO.get(clase[p], SUELO['tierra'])
        # el mismo pincel elegido por manchas de 8x8 celdas, para que no salga a cuadros
        x, y = i % w, i // w
        r = random.Random(hash((semilla, p, x // 8, y // 8)) & 0xFFFFFFFF)
        cel[i * 6] = r.choices([a for a, _ in ops], weights=[b for _, b in ops])[0]
    m['celdas'] = bytes(cel)
    usados = sorted(set(cel[i * 6] for i in range(w * h)))
    m['tilesets'] = usados
    bolsas = _bolsas(em, tema)
    nuevos, cuenta = [], collections.Counter()
    for o in m['objetos']:
        d = em.DEFS.get(o[0])
        t = tipo(d)
        if t is None:
            nuevos.append(o)
            cuenta['igual'] += 1
            continue
        if t == 'quitar':
            cuenta['quitado'] += 1
            continue
        if t == 'otro' and not d['bloquea']:
            t = 'hierba'              # baldosas y bordes planos del 112: una roca encima pareceria un muro y se pisa
        sid = _elegir(bolsas, t, bool(d['bloquea']), rng)
        if sid is None:
            cuenta['quitado'] += 1
            continue
        nuevos.append([sid] + list(o[1:]))
        cuenta[t] += 1
    m['objetos'] = nuevos
    return dict(cuenta, pinceles=usados)


def render(m, em=None, escala=8):
    """El mapa dibujado (suelo y objetos) a 1/escala."""
    from PIL import Image
    em = em or _editor()
    w, h = m['w'], m['h']
    cel = m['celdas']
    lado = max(1, 32 // escala)
    im = Image.new('RGB', (w * lado, h * lado))
    texs = {}
    for p in set(cel[k * 6] for k in range(w * h)):
        t = em.tileset(p)
        if t:
            texs[p] = t[0].resize((512 // escala, 512 // escala))
    for y in range(h):
        for x in range(w):
            t = texs.get(cel[(y * w + x) * 6])
            if t is not None:
                sx, sy = (x % 16) * lado, (y % 16) * lado
                im.paste(t.crop((sx, sy, sx + lado, sy + lado)), (x * lado, y * lado))
    cache = {}
    for o in sorted(m['objetos'], key=lambda o: o[2]):
        if o[0] not in cache:
            r = em.sprite_obj(o[0])
            if r:
                s = Image.open(io.BytesIO(r[0])).convert('RGBA')
                cache[o[0]] = (s.resize((max(1, s.width // escala), max(1, s.height // escala))), r[1])
            else:
                cache[o[0]] = None
        c = cache[o[0]]
        if c:
            s, meta = c
            im.paste(s, (int((o[1] - meta['ox']) / escala), int((o[2] - meta['oy']) / escala)), s)
    return im


def minimapa(m, em=None, salida=SMAP):
    sys.path.insert(0, str(RAIZ / 'tools'))
    from icono_subasta import a_shp
    im = render(m, em, escala=8).resize(SMAP_TAM).convert('RGBA')
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(a_shp(im))
    return im
