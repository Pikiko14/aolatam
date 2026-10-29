"""Editor de mapas para Free Angels Online (.mpc) y Dos Coronas.

Uso:  python editor_mapas.py [carpeta_del_cliente] [puerto]        (por defecto la carpeta padre del editor -- el cliente -- y 8770)
Abre http://127.0.0.1:8770/ . Solo necesita Python 3, Pillow y numpy.

- Abre cualquier .mpc de FAO (carpeta map\\ del cliente, los .pak, tus proyectos y tu carpeta salida\\), lo edita y lo exporta como .mpc (el formato que ya lee Dos Coronas con
  compartido/dominio/mapa_mpc.lua) y como proyecto .json.
- Los tilesets y los sprites de los objetos salen directamente de los .pak de FAO (material de un juego ajeno: prototipo).
"""
import base64, glob, io, json, mmap, os, re, struct, subprocess, sys, threading, urllib.parse, webbrowser, zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import mpcio
import packmapas

GAME = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('AO_CLIENTE', r'C:\AO\Angels Online')   # carpeta del cliente: de ahi salen .pak, mapas y sprites
RAIZ = os.path.dirname(os.path.dirname(AQUI))                       # raiz del repo del servidor
PLANTILLAS = os.path.join(RAIZ, 'server', 'plantillas')             # donde el servidor lee los NPC y monstruos de cada mapa
import ao_servidor
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8770
SALIDA = os.path.join(AQUI, 'salida')
PROYECTOS = os.path.join(AQUI, 'proyectos')
DC = os.environ.get('DOS_CORONAS', r'C:\Users\User\juegos\dos-coronas')
DCVOLCADO = os.path.join(AQUI, 'dc_mapas')         # mapas de Dos Coronas volcados con dcdump (lovec dcdump)
DCEDITADOS = os.path.join(AQUI, 'dc_editados')     # lo que sale del editor de Dos Coronas (.json y .lua)
os.makedirs(SALIDA, exist_ok=True); os.makedirs(PROYECTOS, exist_ok=True); os.makedirs(DCVOLCADO, exist_ok=True); os.makedirs(DCEDITADOS, exist_ok=True)


# ---------------------------------------------------------------- .pak
def open_pak(path):
    f = open(path, 'rb'); m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    n = len(m)
    e = bytes(a ^ ((0xb1 + 3 * i) & 255) for i, a in enumerate(m[n - 18:n]))
    cdsz, _, _, _, cdoff, _ = struct.unpack('<IHHIIH', e)
    blob = bytearray(m[cdoff + 4:cdoff + 4 + cdsz]); blob[0] ^= 0x7a
    cd = zlib.decompress(bytes(blob)); ents = []; p = 0
    while p < len(cd):
        (_, _, _, _, meth, _, _, _, cs, us, nl, xl, cl, _, _, _, lo) = struct.unpack('<IHHHHHHIIIHHHHHII', cd[p:p + 46])
        name = cd[p + 46:p + 46 + nl].decode('latin1').replace(chr(92), '/')
        ents.append((name, meth, cs, us, lo)); p += 46 + nl + xl + cl
    return m, ents


def orden(p):
    n = os.path.basename(p).lower()
    if n == 'data1.pak': return -1
    mm = re.match(r'update(\d*)\.pak', n)
    return int(mm.group(1) or 1) if mm else 500


INDEX = {}      # ruta en minusculas -> (mmap, meth, cs, lo, nombre original, pak)
INTERES = re.compile(r'^(brush/|setting/|map/|shape/(stage|house|common|npc|mon)/|shape/magic/|sound/|music/)', re.I)


def cargar():
    # El pack del editor (update28.pak) no se indexa: lo reescribe el propio editor al guardar y, con el mmap abierto, Windows no deja reemplazarlo.
    paks = sorted([p for p in glob.glob(os.path.join(GAME, '*.pak')) if os.path.getsize(p) > 1000 and 'music' not in p.lower()
                   and os.path.basename(p).lower() != packmapas.PACK], key=orden)
    for p in paks:
        m, ents = open_pak(p)
        for name, meth, cs, us, lo in ents:
            if name.endswith('/'): continue
            INDEX[name.lower()] = (m, meth, cs, lo, name, os.path.basename(p))
    print(len(INDEX), 'archivos en', len(paks), 'paquetes')


def datos(key):
    m, meth, cs, lo, _, _ = INDEX[key]
    raw = bytes(m[lo:lo + cs])
    return zlib.decompress(raw, -15) if meth == 8 else raw


# ---------------------------------------------------------------- imagenes de FAO
def c565(v, bgr=False):
    r, g, b = (v >> 11 & 31) * 255 // 31, (v >> 5 & 63) * 255 // 63, (v & 31) * 255 // 31
    return (b, g, r) if bgr else (r, g, b)


def decode_shp(b, pal=None):
    if b[:4] != b'TLHS' or len(b) < 96: return None
    h = struct.unpack('<20I', b[:80]); typ, fl, w, hh = h[2], h[3], h[5], h[6]
    ox, oy = struct.unpack('<ii', b[28:36])
    if not (0 < w <= 4096 and 0 < hh <= 4096) or len(b) < 80 + 4 * hh: return None
    rows = struct.unpack('<%dI' % hh, b[80:80 + 4 * hh])
    im = Image.new('RGBA', (w, hh), (0, 0, 0, 0)); px = im.load(); L = len(b)
    paletted = fl == 768 and typ == 2
    if paletted and h[16] and h[16] + 512 <= L:
        pal = [c565(b[h[16] + 2 * i] | b[h[16] + 2 * i + 1] << 8) for i in range(256)]
    bgr = typ == 4
    for y, o in enumerate(rows):
        while o + 8 <= L:
            cnt, x, off = struct.unpack('<HHI', b[o:o + 8]); o += 8
            if x == 0xffff or (cnt == 0 and off == 0): break
            for i in range(cnt):
                if x + i >= w: break
                if paletted:
                    if off + i < L and pal and b[off + i] < len(pal): px[x + i, y] = pal[b[off + i]] + (255,)
                else:
                    p = off + 2 * i
                    if p + 2 <= L: px[x + i, y] = c565(b[p] | b[p + 1] << 8, bgr) + (255,)
    return im, (ox, oy)


def read_spr(b):
    if b[:4] != b'EWSP': return None
    cnt = struct.unpack('<I', b[8:12])[0]
    pal_off = 80 + 12 * cnt
    name_off0 = struct.unpack('<I', b[80:84])[0]
    pal = [c565(b[pal_off + 2 * i] | b[pal_off + 2 * i + 1] << 8) for i in range(max(0, (name_off0 - pal_off) // 2))]
    frames = []
    for i in range(cnt):
        off, size, noff = struct.unpack('<III', b[84 + 12 * i:96 + 12 * i])
        frames.append((b[noff:noff + 16].split(b'\0')[0].decode('latin1'), b[off:off + size]))
    return pal, frames


def png(im):
    bio = io.BytesIO(); im.save(bio, 'PNG'); return bio.getvalue()


# ---------------------------------------------------------------- tilesets de pincel (brush/brush.bNN)
_ts = {}


def tileset(n):
    """(textura 512x512 RGB como imagen, color medio, clase, nTiles) del tileset de pincel n."""
    if n in _ts: return _ts[n]
    k = 'brush/brush.b%02x' % n
    if k not in INDEX:
        _ts[n] = None; return None
    b = datos(k)
    pal = np.frombuffer(b[52:52 + 512], dtype='<u2').astype(np.int32)
    r, g, bl = ((pal >> 11) & 31) * 255 // 31, ((pal >> 5) & 63) * 255 // 63, (pal & 31) * 255 // 31
    pal = np.stack([r, g, bl], 1).astype(np.uint8)
    nt = (len(b) - 564) // 1024
    px = np.frombuffer(b[564:564 + nt * 1024], dtype=np.uint8).reshape(nt, 32, 32)
    lado = int(round(nt ** 0.5)) or 1
    tex = pal[px[:lado * lado].reshape(lado, lado, 32, 32).transpose(0, 2, 1, 3).reshape(lado * 32, lado * 32)]
    reps = max(1, 512 // tex.shape[0])
    tex = np.tile(tex, (reps, reps, 1))[:512, :512]
    medio = tex.reshape(-1, 3).mean(0)
    clase = clase_tile(medio)
    _ts[n] = (Image.fromarray(tex, 'RGB'), [int(v) for v in medio], clase, nt)
    return _ts[n]


UMBRAL_AGUA = 90


def clase_tile(rgb):
    r, g, b = [float(v) for v in rgb]
    if b - r >= UMBRAL_AGUA: return 'agua'
    if b - r >= 30 and g >= r: return 'agua_somera'
    if g > r + 15 and g > b + 25: return 'hierba'
    if abs(r - g) < 16 and abs(g - b) < 24 and r < 200: return 'roca'
    if r > 225 and g > 200 and b > 120: return 'arena'
    return 'tierra'


def tslist():
    out = []
    for k in sorted(INDEX):
        mm = re.fullmatch(r'brush/brush\.b([0-9a-f]{2})', k)
        if mm:
            n = int(mm.group(1), 16); t = tileset(n)
            if t: out.append(dict(n=n, color=t[1], clase=t[2], tiles=t[3]))
    return out


# ---------------------------------------------------------------- definiciones de objetos (setting/*.obd)
REGLAS_NO = ('花', '草', '葉', '蒲公英', '針葉球', '幸運草', '貝殼', '邊條', '邊', '橋', '光', '蝴蝶', '小鳥', '水中', '植物', '蘆葦', '星草', '草皮')
REGLAS_SI = ('樹', '石頭', '石', '岩', '礁', '山洞', '木箱', '木桶', '寶箱', '攤販', '櫃子', '骷髏', '木桌', '桶', '箱')
DEFS = {}


def objeto_bloquea(d):
    nombre, proceso = d['nombre'], d['proceso']
    if 'ZBUFFER' not in d['flags'] and 'HITTEST' not in d['flags'] and '11TREE' not in proceso: return False
    if '矮樹叢' in nombre: return False
    if '11TREE' in proceso and '(X)' not in nombre: return True
    if any(k in nombre for k in REGLAS_NO): return False
    return any(k in nombre for k in REGLAS_SI)


def cargar_defs():
    for arch in ('setting/mapobj.obd', 'setting/server.obd', 'setting/npc.obd', 'setting/common.obd', 'setting/house.obd'):
        if arch not in INDEX: continue
        t = datos(arch).decode('cp950', errors='replace')
        for bloque in re.split(r'\r?\n\[OBJECT\]\r?\n', t)[1:]:
            d = {}
            for l in bloque.split('\n'):
                l = l.strip()
                if '=' in l and not l.startswith('//') and not l.startswith('['):
                    k, v = l.split('=', 1)
                    d.setdefault(k.strip(), []).append(v.split('//')[0].strip())
            if 'Sequence' in d:
                try: sid = int(d['Sequence'][0], 0)
                except ValueError: continue
                if sid in DEFS: continue
                x = dict(nombre=d.get('Name', [''])[0], proceso=d.get('Process', [''])[0], flags=d.get('Flags', [''])[0],
                         directorio=d.get('Directory', [''])[0], sprite=d.get('Sprite', [''])[0], fuente=arch.split('/')[-1][:-4])
                x['bloquea'] = objeto_bloquea(x)
                DEFS[sid] = x
    print(len(DEFS), 'definiciones de objetos')


def frames_obj(d):
    t = d['sprite']
    if not t.lower().startswith('wait'): return []
    out = []
    for tok in [x.strip() for x in t.split(',')][1:]:
        if re.fullmatch(r'[0-9A-Za-z]+-[0-9A-Za-z]+-[0-9A-Za-z]+', tok): out.append(tok)
    return out


_obj = {}


def sprite_obj(sid):
    """(PNG, meta) del primer cuadro del objeto, o None."""
    if sid in _obj: return _obj[sid]
    d = DEFS.get(sid); res = None
    if d:
        carpeta = d['directorio'].replace(chr(92), '/').strip('/')
        for nombre in frames_obj(d)[:1]:
            for ext in ('shp', 'spr'):
                k = 'shape/%s/%s.%s' % (carpeta, nombre.lower(), ext)
                if k not in INDEX: continue
                b = datos(k)
                r = None
                if ext == 'shp': r = decode_shp(b)
                else:
                    s = read_spr(b)
                    if s and s[1]: r = decode_shp(s[1][0][1], s[0])
                if r:
                    im, (ox, oy) = r
                    meta = dict(id=sid, w=im.width, h=im.height, ox=ox, oy=oy, n=d['nombre'], c=d['proceso'], b=d['bloquea'],
                                huella=max(1, int(round(im.width * 0.30 / 64))) if d['bloquea'] else 0, frames=len(frames_obj(d)))
                    res = (png(im), meta); break
            if res: break
    _obj[sid] = res
    return res


# ---------------------------------------------------------------- mapas
def mapas_disponibles():
    out = []
    for f in sorted(glob.glob(os.path.join(GAME, 'map', '*.mpc'))):
        out.append(dict(origen='carpeta', nombre=os.path.basename(f)[:-4], ruta=f))
    for f in sorted(glob.glob(os.path.join(SALIDA, '*.mpc'))):
        out.append(dict(origen='salida', nombre=os.path.basename(f)[:-4], ruta=f))
    for k in sorted(INDEX):
        if k.startswith('map/') and k.endswith('.mpc'):
            out.append(dict(origen='pak', nombre=INDEX[k][4].split('/')[-1][:-4], ruta=INDEX[k][4], pak=INDEX[k][5]))
    return out


_stage = {}


def stage_nombres():
    if _stage: return _stage
    k = 'setting/eng/stage.xml'
    if k in INDEX:
        t = datos(k).decode('utf-8', errors='replace')
        for mm in re.finditer(r'編號="(\d+)" 名稱="([^"]*)"', t):
            _stage[int(mm.group(1))] = mm.group(2)
    return _stage


def mapa_json(m, nombre, origen):
    b64 = lambda b: base64.b64encode(bytes(b)).decode('ascii')
    return dict(nombre=nombre, origen=origen, w=m['w'], h=m['h'], cabecera=m['cabecera'], celdas=b64(m['celdas']), extra=b64(m.get('extra', b'')),
                hueco=b64(m.get('hueco', b'')), tilesets=m['tilesets'], objetos=m['objetos'], eventos=m['eventos'], dialogos=m['dialogos'], rutas=m['rutas'],
                puntos=m['puntos'], resto=m.get('resto', ''))


def json_a_mapa(j):
    b = lambda s: base64.b64decode(s) if s else b''
    return dict(w=j['w'], h=j['h'], cabecera=j['cabecera'], celdas=b(j['celdas']), extra=b(j.get('extra', '')), hueco=b(j.get('hueco', '')), tilesets=j['tilesets'],
                objetos=j['objetos'], eventos=j['eventos'], dialogos=j['dialogos'], rutas=j['rutas'], puntos=j['puntos'], resto=j.get('resto', ''))


def nuevo_mapa(w, h, ts, nombre):
    cel = bytearray(w * h * 6)
    for i in range(0, len(cel), 6): cel[i] = ts
    cab = [0x0050414d, w, h, 0x10005, 32, 32, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    cab[0] = struct.unpack('<I', b'MAP\x00')[0]
    ev = '<?xml version="1.0" encoding="UTF-8" ?>\n<root>\n\t<head version="1.0"/>\n</root>\n'
    return dict(w=w, h=h, cabecera=cab, celdas=bytes(cel), extra=b'', hueco=b'', tilesets=[ts], objetos=[], eventos=ev, dialogos=ev, rutas=[], puntos=[], resto='')


def abrir(origen, nombre):
    if origen == 'nuevo':
        raise ValueError('use /api/nuevo')
    for mp in mapas_disponibles():
        if mp['origen'] == origen and mp['nombre'] == nombre:
            if origen == 'pak':
                d = datos('map/' + nombre.lower() + '.mpc') if ('map/' + nombre.lower() + '.mpc') in INDEX else None
            else:
                d = open(mp['ruta'], 'rb').read()
            r = mapa_json(mpcio.leer(d), nombre, origen)
            r['campamentos'] = camps_de(nombre)
            return r
    raise FileNotFoundError(nombre)


PACK_RUTA = os.path.join(GAME, packmapas.PACK)


def al_pack(nombre, data):
    """Guarda el mapa en el pack nuevo del cliente (update28.pak). Nunca tumba el guardado: si falla (p. ej. el juego tiene el pack abierto) lo cuenta."""
    try:
        return dict(ok=True, **packmapas.guardar_mapa(PACK_RUTA, nombre, data))
    except Exception as ex:
        return dict(ok=False, pack=packmapas.PACK, error=('cierra el cliente y el servidor (tienen el pack abierto) y vuelve a guardar' if isinstance(ex, PermissionError) else repr(ex)))


def camps_de(nombre):
    """Campamentos de criaturas de un mapa: el .mpc no los trae, van en salida/NOMBRE_campamentos.json (al lado del .mpc exportado)."""
    f = os.path.join(SALIDA, re.sub(r'[^0-9A-Za-z_\-]', '', nombre) + '_campamentos.json')
    try: return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else []
    except Exception: return []


def guardar_camps(camps, nombre, carpeta):
    """Escribe NOMBRE_campamentos.json y .lua (lista de { monstruo, cantidad, radio, x, y, jefe? }, x e y en casillas con .5). Sin campamentos borra los archivos."""
    import dcexport
    nombre = re.sub(r'[^0-9A-Za-z_\-]', '', nombre) or 'mapa'
    rj, rl = os.path.join(carpeta, nombre + '_campamentos.json'), os.path.join(carpeta, nombre + '_campamentos.lua')
    if not camps:
        for f in (rj, rl):
            if os.path.exists(f): os.remove(f)
        return None
    limpio = [{k: c[k] for k in ('monstruo', 'cantidad', 'radio', 'x', 'y', 'jefe', 'nivel') if k in c} for c in camps]
    open(rj, 'w', encoding='utf-8').write(json.dumps(limpio, ensure_ascii=False))
    cab = ('-- GENERADO por el editor de mapas (fao-editor-mapas): campamentos de criaturas del mapa "%s".\n'
           '-- Lista de { monstruo (id de monstruos.xml), cantidad, radio (casillas), x, y (casillas, centro de la casilla = .5), jefe? }.\n' % nombre)
    open(rl, 'w', encoding='utf-8', newline='\n').write(cab + 'return ' + dcexport.a_lua(limpio) + '\n')
    return rl


# ---------------------------------------------------------------- servidor
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def out(self, code, body, ctype='application/json', extra=None):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str): body = body.encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def cuerpo(self):
        n = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(n) if n else b''

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        g = lambda k, d='': q.get(k, [d])[0]
        try:
            if u.path == '/':
                return self.out(200, open(os.path.join(AQUI, 'editor.html'), 'rb').read(), 'text/html; charset=utf-8')
            if u.path.startswith('/static/'):
                f = os.path.join(AQUI, 'static', os.path.basename(u.path))
                return self.out(200, open(f, 'rb').read(), 'text/javascript; charset=utf-8' if f.endswith('.js') else 'text/css')
            if u.path == '/api/mapas': return self.out(200, dict(mapas=mapas_disponibles(), stage={str(k): v for k, v in stage_nombres().items()}, dc=os.path.isdir(DC)))
            if u.path == '/api/abrir': return self.out(200, abrir(g('o'), g('n')))
            if u.path == '/api/nuevo':
                m = nuevo_mapa(int(g('w', '100')), int(g('h', '80')), int(g('ts', '0')), g('n', 'nuevo'))
                return self.out(200, mapa_json(m, g('n', 'nuevo'), 'nuevo'))
            if u.path == '/api/tslist': return self.out(200, tslist())
            if u.path == '/api/ts':
                t = tileset(int(g('n')))
                return self.out(200, png(t[0]), 'image/png') if t else self.out(404, b'')
            if u.path == '/api/ao/catalogo':
                return self.out(200, ao_servidor.catalogo())
            if u.path == '/api/ao/foto':
                r = ao_servidor.foto(int(g('id', '0') or 0))
                return self.out(200, r, 'image/png') if r else self.out(404, b'')
            if u.path == '/api/ao/spawns':
                return self.out(200, ao_servidor.spawns(g('mapa')))
            if u.path == '/api/objdefs':
                return self.out(200, {str(k): [v['nombre'], v['proceso'].replace('SP_CLASS_', ''), v['fuente'], 1 if v['bloquea'] else 0, 1 if frames_obj(v) else 0, v['flags']] for k, v in DEFS.items()})
            if u.path == '/api/obj':
                r = sprite_obj(int(g('id')))
                return self.out(200, r[0], 'image/png', {'X-Obj': json.dumps(r[1], ensure_ascii=False).encode('utf-8').decode('latin1')}) if r else self.out(404, b'')
            if u.path == '/api/objmeta':
                out = {}
                for s in g('ids').split(','):
                    if s.isdigit():
                        r = sprite_obj(int(s)); out[s] = r[1] if r else None
                return self.out(200, out)
            if u.path == '/dc':
                return self.out(200, open(os.path.join(AQUI, 'editor_dc.html'), 'rb').read(), 'text/html; charset=utf-8')
            if u.path == '/api/dc/lista':
                return self.out(200, dict(volcados=sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(DCVOLCADO, '*.json'))),
                                          editados=sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(DCEDITADOS, '*.json'))), dc=os.path.isdir(DC)))
            if u.path == '/api/dc/abrir':
                carpeta = DCEDITADOS if g('o') == 'editado' else DCVOLCADO
                return self.out(200, open(os.path.join(carpeta, os.path.basename(g('n')) + '.json'), 'rb').read())
            if u.path == '/api/dc/volcar':
                return self.out(200, volcar_dc())
            if u.path == '/api/dc/monstruos':
                return self.out(200, monstruos_dc())
            if u.path == '/api/dc/mob':
                r = foto_mob(g('id'))
                return self.out(200, r, 'image/png', {'Cache-Control': 'max-age=3600'}) if r else self.out(404, b'')
            if u.path == '/api/proyectos':
                return self.out(200, sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(PROYECTOS, '*.json'))))
            if u.path == '/api/abrir_proyecto':
                return self.out(200, open(os.path.join(PROYECTOS, os.path.basename(g('n')) + '.json'), 'rb').read())
            if u.path == '/api/descargar':
                f = os.path.join(SALIDA, os.path.basename(g('n')))
                return self.out(200, open(f, 'rb').read(), 'application/octet-stream', {'Content-Disposition': 'attachment; filename="%s"' % os.path.basename(f)})
            self.out(404, {'error': 'no'})
        except Exception as ex:
            import traceback; traceback.print_exc()
            self.out(500, {'error': repr(ex)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        g = lambda k, d='': q.get(k, [d])[0]
        try:
            j = json.loads(self.cuerpo().decode('utf-8'))
            if u.path == '/api/exportar':
                nombre = re.sub(r'[^0-9A-Za-z_\-]', '', g('n', 'mapa')) or 'mapa'
                data = mpcio.escribir(json_a_mapa(j))
                chk = mpcio.leer(data)               # comprobacion: se puede volver a leer
                ruta = os.path.join(SALIDA, nombre + '.mpc')
                open(ruta, 'wb').write(data)
                rc = guardar_camps(j.get('campamentos') or [], nombre, SALIDA)
                pk = al_pack(nombre, data)           # tambien al pack nuevo del cliente
                return self.out(200, dict(ok=True, ruta=ruta, bytes=len(data), w=chk['w'], h=chk['h'], objetos=len(chk['objetos']), archivo=nombre + '.mpc',
                                          campamentos=len(j.get('campamentos') or []), campamentos_lua=rc, pack=pk))
            if u.path == '/api/ao/exportar':
                return self.out(200, ao_servidor.exportar(j.get('mapa'), j.get('spawns') or []))
            if u.path == '/api/guardar_proyecto':
                nombre = re.sub(r'[^0-9A-Za-z_\-]', '', g('n', 'proyecto')) or 'proyecto'
                open(os.path.join(PROYECTOS, nombre + '.json'), 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False))
                pk = None
                if not nombre.startswith('_auto_'):  # el autoguardado cada 90 s solo guarda el proyecto; guardar de verdad tambien manda el mapa al pack
                    try:
                        pk = al_pack(nombre, mpcio.escribir(json_a_mapa(j)))
                    except Exception as ex:
                        pk = dict(ok=False, pack=packmapas.PACK, error=repr(ex))
                return self.out(200, dict(ok=True, nombre=nombre, pack=pk))
            if u.path == '/api/dc/guardar':
                return self.out(200, guardar_dc(j, g('n', 'mapa')))
            if u.path == '/api/a_dos_coronas':
                return self.out(200, a_dos_coronas(j, g('num', '900'), g('n', 'mapa')))
            self.out(404, {'error': 'no'})
        except Exception as ex:
            import traceback; traceback.print_exc()
            self.out(500, {'error': repr(ex)})


def volcar_dc():
    """Vuelca los mapas actuales de Dos Coronas (los que genera su codigo) con LOVE: lovec dcdump."""
    for ruta in (os.environ.get('LOVEC', ''), os.path.join(os.path.dirname(DC), 'love', 'lovec.exe'), os.path.join(DC, '..', 'love', 'lovec.exe')):
        if ruta and os.path.exists(ruta): lovec = ruta; break
    else:
        return dict(ok=False, error='no encuentro lovec.exe (define LOVEC)')
    r = subprocess.run([lovec, os.path.join(AQUI, 'dcdump'), DC, DCVOLCADO], capture_output=True, text=True, timeout=300)
    return dict(ok=r.returncode == 0, salida=(r.stdout + r.stderr)[-1500:])


def monstruos_dc():
    """Criaturas de compartido/datos/monstruos.xml (id, nombre, nivel, bioma, etiquetas) para el selector de campamentos."""
    t = ''
    for arch in ('monstruos.xml', 'monstruos_altos.xml'):          # (las criaturas de los niveles 35 a 50 viven en monstruos_altos.xml)
        ruta = os.path.join(DC, 'compartido', 'datos', arch)
        if os.path.exists(ruta): t += open(ruta, encoding='utf-8').read() + ' '
    if not t: return []
    out = []
    for m in re.finditer(r'<monstruo\s+([^>]*?)/?>', t):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if 'id' not in a: continue
        out.append(dict(id=a['id'], nombre=a.get('nombre', a['id']), nivel=int(a['nivel']) if a.get('nivel', '').isdigit() else 0, bioma=a.get('bioma', ''),
                        jefe=a.get('jefeMundo', '') not in ('', 'false') or a.get('elite', '') == 'true', categoria=a.get('categoria', '')))
    return out


def foto_mob(idm):
    """Miniatura (primer cuadro de la espera, recortado) de una criatura de Dos Coronas: juego/arte/monstruos/<id>/wait.png (6 cuadros: 3 pasos x 2 direcciones)."""
    if not idm or not re.fullmatch(r'[a-z0-9_]+', idm): return None
    ruta = os.path.join(DC, 'juego', 'arte', 'monstruos', idm, 'wait.png')
    if not os.path.exists(ruta): return None
    im = Image.open(ruta).convert('RGBA')
    im = im.crop((0, 0, im.width // 6, im.height))
    bb = im.getchannel('A').point(lambda v: 255 if v > 10 else 0).getbbox()
    if bb: im = im.crop(bb)
    im.thumbnail((56, 56), Image.LANCZOS)
    o = io.BytesIO(); im.save(o, 'PNG')
    return o.getvalue()


def guardar_dc(j, nombre):
    import dcexport
    return dcexport.guardar(j, nombre, DCEDITADOS)



def registrar_mapa(destino, comando, num):
    """Anade `comando = num` a compartido/datos/mapas_fao/indice.lua (return { nombre = numero, ... }), conservando lo que ya tenia."""
    ruta = os.path.join(destino, 'indice.lua')
    mapas = {}
    if os.path.exists(ruta):
        for k, v in re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)', open(ruta, encoding='utf-8').read()):
            mapas[k] = int(v)
    mapas = {k: v for k, v in mapas.items() if v != num}      # un numero de mapa solo tiene un nombre
    mapas[comando] = num
    cab = ('-- GENERADO por el editor de mapas (fao-editor-mapas, "Enviar a Dos Coronas"): mapas de FAO instalados.\n'
           '-- nombre del comando (/admin mapa nombre) = numero del .mpc (mapNNN.mpc en esta carpeta). Se puede editar a mano.\n')
    open(ruta, 'w', encoding='utf-8', newline='\n').write(cab + 'return {\n' + ''.join('  %s = %d,\n' % (k, v) for k, v in sorted(mapas.items(), key=lambda kv: kv[1])) + '}\n')
    return ruta


def a_dos_coronas(j, num, nombre):
    """Exporta el mapa y lo hornea en el proyecto Dos Coronas con su herramienta (hornear_mpc.py): copia el .mpc, genera mapNNN_datos.lua y los atlas."""
    if not os.path.isdir(DC): return dict(ok=False, error='no encuentro Dos Coronas en ' + DC + ' (define DOS_CORONAS)')
    num = int(num)
    data = mpcio.escribir(json_a_mapa(j))
    carpeta = os.path.join(SALIDA, 'dc_mapas')
    os.makedirs(carpeta, exist_ok=True)
    open(os.path.join(carpeta, 'map%03d.mpc' % num), 'wb').write(data)
    env = dict(os.environ, FAO_MAPAS=carpeta, FAO_DESCARGAS=GAME)
    r = subprocess.run([sys.executable, '-X', 'utf8', os.path.join(DC, 'herramientas', 'generar_mapa', 'hornear_mpc.py'), str(num)], capture_output=True, text=True, env=env, cwd=DC)
    extra = ''
    destino = os.path.join(DC, 'compartido', 'datos', 'mapas_fao')
    if r.returncode == 0:      # los campamentos viajan en un archivo aparte junto al .mpc (mapNNN_campamentos.lua)
        rc = guardar_camps(j.get('campamentos') or [], 'map%03d' % num, destino)
        extra = ('\nCampamentos: %d -> %s' % (len(j.get('campamentos') or []), rc)) if rc else '\nSin campamentos de criaturas.'
        cmd = re.sub(r'[^a-z0-9_]', '', nombre.lower()) or 'mapa'
        ri = registrar_mapa(destino, cmd, num)
        extra += '\nRegistrado en %s: %s = %d' % (ri, cmd, num)
    cmd = re.sub(r'[^a-z0-9_]', '', nombre.lower()) or 'mapa'
    return dict(ok=r.returncode == 0, salida=(r.stdout + r.stderr)[-2000:] + extra,
                siguiente="Queda registrado en compartido/datos/mapas_fao/indice.lua (%s = %d): si el juego ya lee ese indice (ver PROMPT_CRIATURAS_FAO.md, paso 0) basta reiniciar el servidor; en el juego: /admin mapa %s" % (cmd, num, cmd))


def main():
    print('Leyendo .pak en', GAME)
    cargar(); cargar_defs()
    ao_servidor.init(sys.modules[__name__])
    print('Editor en http://127.0.0.1:%d/' % PORT)
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    threading.Timer(.8, lambda: webbrowser.open('http://127.0.0.1:%d/' % PORT)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
