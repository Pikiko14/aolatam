"""El brillo del campeon de Angel Arena: un AURA SUPER SAIYAN dibujada por codigo (17-18/11/2026).

"en ganador del primer lugar debe brillar", "crea el efecto tu que sea vistoso", "que el efecto sea algo como los
super sayan". El primer intento (el Angel Halo recoloreado en oro) no valia: "ese efecto no debe ser un efecto creado
por ti". Ahora los frames se dibujan desde cero y van en los huecos del efecto de magia 25 (W06 天使光環), que ningun
skill usa. Sus tres objetos de setting/M02.OBD (\\magic\\025\\) se ven uno tras otro, asi que los tres llevan FUEGO
("que solo sea el fuego", "debe verse siempre"): los 6 frames del aura repartidos entre

    279  s082011..031  (era el angel; se le pone SP_ATTRIB_WHITELIGHT para que sume luz como los otros)
    280  s083011..061  (era el halo)
    328  s188011..031  (era el destello)

y en M02.OBD (parches/extras/setting/m02.obd, copia del oficial con solo esas lineas cambiadas) los tres acaban con
@SP_EVENT_ACT_REMOVE: sin el, cada relanzamiento dejaba otra copia y se iba poniendo cada vez mas amarillo.

EL .SHP DE ESTA CARPETA ES DE COLOR DIRECTO: cabecera '<4s19I', cab[5] ancho, cab[6] alto, cab[7] y cab[8] el
desplazamiento de la esquina de arriba a la izquierda respecto al ancla (esquina = ancla - (cab[7], cab[8]); los pies
van en el ancla), cab[16] = 0 (sin paleta) y 2 bytes RGB565 por pixel desde cab[11]. Lo que no brilla no se dibuja
(los tramos solo cubren lo que tiene luz). Con luz sumada, menos intensidad es mas transparente (TRANSPARENCIA).

Deja parches/extras/shape/magic/025/<frame>.shp y setting/m02.obd (entran en el parche) y, con --vista RUTA.png, una
hoja con los 12 frames y el aura sobre un muneco. El servidor lo lanza con el cierre (fase 0x80) del 0x0011 del
efecto 25 una vez por jugador y mapa (competicion_premios.brillo_campeon; gm /fxm 25 [modo], /brillo).

    python tools/brillo_campeon.py [--vista RUTA.png]
"""
import argparse
import pathlib
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import fondos_interfaz as fi  # noqa: E402

EFECTO = 25
NUCLEO = ('s082011', 's082021', 's082031')
AURA = ('s083011', 's083021', 's083031', 's083041', 's083051', 's083061')
CHISPAS = ('s188011', 's188021', 's188031')
FRAMES = NUCLEO + AURA + CHISPAS
SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'magic' / ('%03d' % EFECTO)

# El cuerpo, en px sobre el ancla (los pies): un personaje mide ~90 px montado o no.
ANCHO, ALTO = 110, 170          # el lienzo del aura
PIES = 150                      # fila del lienzo donde caen los pies (el ancla)
ALTO_CUERPO = 92
UMBRAL = 10                     # intensidad minima que se dibuja (0..255)
TRANSPARENCIA = 0.85            # intensidad del aura (era 1.7: tapaba al personaje en blanco)

# Rampa de la paleta: intensidad 0..255 -> color. Ambar oscuro, oro, amarillo y blanco en el centro.
# Sin blanco puro arriba: con luz sumada (WHITELIGHT) sobre el personaje lo quemaba en blanco ("que no brille tanto se
# pierde el personaje", 18/11/2026).
RAMPA = ((0, (70, 35, 0)), (60, (200, 110, 0)), (120, (245, 175, 15)), (180, (255, 210, 50)),
         (225, (255, 228, 100)), (255, (255, 240, 150)))


def _paleta():
    xs = [p for p, _ in RAMPA]
    i = np.arange(256)
    rgb = np.stack([np.interp(i, xs, [c[k] for _, c in RAMPA]) for k in range(3)], -1)
    rgb = np.clip(np.rint(rgb), 0, 255).astype(np.uint32)
    v = ((rgb[:, 0] * 31 // 255) << 11) | ((rgb[:, 1] * 63 // 255) << 5) | (rgb[:, 2] * 31 // 255)
    return v.astype('<u2'), rgb.astype(np.uint8)


def _ruido(h, w, semilla, escala):
    """Ruido suave (bilineal de una rejilla aleatoria), 0..1, PERIODICO en vertical: al desplazarlo hacia arriba con
    np.roll no deja el corte horizontal que salia en la primera vista."""
    rng = np.random.default_rng(semilla)
    gh, gw = h // escala + 2, w // escala + 2
    g = rng.random((gh, gw))
    g[-2:] = g[:2]
    ys = np.linspace(0, gh - 1.001, h)
    xs = np.linspace(0, gw - 1.001, w)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return a * (1 - fy) * (1 - fx) + b * (1 - fy) * fx + c * fy * (1 - fx) + d * fy * fx


def _llamas(t, ancho_max, alto_max, semilla, fuerza=1.0):
    """Intensidad 0..1 de un aura de llamas en punta en el instante t (0..1, ciclico)."""
    h, w = ALTO, ANCHO
    y = np.arange(h)[:, None].astype(float)
    x = (np.arange(w)[None, :] - w / 2).astype(float)
    alto = (PIES - y) / alto_max                       # 0 en los pies, 1 arriba del todo
    # La silueta: ancha a la altura del pecho, se cierra en los pies y se afila hacia arriba.
    perfil = np.clip(np.sin(np.clip(alto, 0, 1) * np.pi * 0.95) ** 0.6, 0, 1) * ancho_max / 2
    perfil = perfil + 6 * (alto > 0)
    # Lenguas de fuego: columnas que suben (el ruido se desplaza hacia arriba con t) y puntas.
    sube = int(t * ALTO)
    n1 = np.roll(_ruido(h, w, semilla, 9), -sube, axis=0)
    n2 = np.roll(_ruido(h, w, semilla + 1, 4), -2 * sube, axis=0)
    lenguas = 0.6 * n1 + 0.4 * n2
    borde = perfil * (0.75 + 0.55 * lenguas)
    dist = np.abs(x) / np.maximum(borde, 1)
    llama = np.clip(1 - dist, 0, 1) ** 0.7
    # Puntas por arriba: el techo de la llama tambien sube y baja con el ruido.
    techo = 1 + 0.35 * (n1 - 0.5) + 0.25 * np.sin(x / 5 + t * 2 * np.pi)
    llama *= np.clip((techo - alto) * 6, 0, 1)
    llama *= np.clip(alto * 8 + 0.4, 0, 1)             # se apaga bajo los pies
    # HUECA, como las de Super Saiyan: brilla en el borde y por dentro apenas un velo, para que se vea el personaje
    # (la primera vista era un bloque de fuego que lo tapaba).
    borde_luz = np.clip(dist, 0, 1) ** 1.6
    # El cuerpo mide ~24 px de ancho: ahi casi no hay luz, para que el personaje se siga viendo.
    # La forma de la captura del 18/11/2026 que gusto (fuego redondo envolviendo el cuerpo), pero a media intensidad:
    # con luz sumada, menos intensidad es mas transparente ("debe verse como antes pero con transparencia"). La
    # version hueca partia el aura en dos mitades ("se ve mal").
    hueco = np.clip(np.abs(x) / (perfil * 0.45 + 1), 0, 1)       # 0 en el eje del cuerpo
    v = llama * (0.12 + 0.88 * borde_luz) * (0.35 + 0.65 * hueco)
    # Sin el parpadeo de conjunto (0.9 + 0.1 * sin) que llevaba: "no debe titilar, debe encenderse siempre" (18/11/2026).
    v = v * TRANSPARENCIA * fuerza
    return np.clip(v, 0, 1)


def _chispas(t, semilla):
    """Chispas que suben y un par de rayos en zigzag (estilo SSJ2)."""
    img = Image.new('L', (ANCHO, ALTO), 0)
    dib = ImageDraw.Draw(img)
    rng = np.random.default_rng(semilla)
    for _ in range(26):
        x0 = rng.normal(0, 22) + ANCHO / 2
        y0 = PIES - rng.random() * (ALTO_CUERPO + 30)
        y = (y0 - t * 60) % (ALTO - 10)
        r = rng.choice((1, 1, 2))
        brillo = int(150 + 105 * rng.random())
        largo = 3 + 5 * rng.random()
        for k in range(int(largo)):                      # estela que se apaga hacia abajo
            dib.point((x0, y + r + 1 + k), fill=int(brillo * 0.45 * (1 - k / largo)))
        dib.ellipse((x0 - r, y - r, x0 + r, y + r), fill=brillo)
    for k in range(2):
        rr = np.random.default_rng(semilla * 31 + k)
        x = ANCHO / 2 + rr.choice((-1, 1)) * (14 + 10 * rr.random())
        y = PIES - 15 - rr.random() * 40
        pts = [(x, y)]
        for _ in range(6):
            x += rr.normal(0, 6)
            y -= 6 + 6 * rr.random()
            pts.append((x, y))
        dib.line(pts, fill=255, width=1)
        dib.line([(px + 1, py) for px, py in pts], fill=140, width=1)
    return np.asarray(img, dtype=np.float64) / 255.0


def _a_shp(intensidad, plantilla) -> bytes:
    """La intensidad (0..1) del lienzo como .shp de COLOR DIRECTO, con el ancla en los pies.

    LOS SPRITES DE \\magic\\025\\ NO LLEVAN PALETA (18/11/2026, el aura salia como ruido de arcoiris): cab[16] = 0 y
    cada pixel son 2 bytes RGB565, que empiezan en cab[11] = cab[12]. Los de paleta se marcan con cab[3] = 768 y
    cab[16] apuntando a ella (los del efecto 171). fondos_interfaz.leer solo sabe de la marca 4 para los 2 bytes, asi
    que aqui se escribe a mano, con la misma forma que los originales: cabecera, una tabla con el inicio de los tramos
    de cada fila, los tramos (n, x, origen) y el cierre de fila (0, 0xFFFF, puntero tras sus pixeles), y los pixeles."""
    cab = list(struct.unpack_from('<4s19I', plantilla))
    pal565, _ = _paleta()
    idx = np.clip(np.rint(intensidad * 255), 0, 255).astype(np.uint8)
    filas = []
    for fila in idx:
        tramos, x = [], 0
        while x < len(fila):
            if fila[x] < UMBRAL:
                x += 1
                continue
            ini = x
            while x < len(fila) and fila[x] >= UMBRAL:
                x += 1
            tramos.append((ini, pal565[fila[ini:x]].astype('<u2').tobytes()))
        filas.append(tramos)
    alto = len(filas)
    n_tramos = sum(len(t) + 1 for t in filas)
    ini_tramos = 80 + 4 * alto
    ini_pix = ini_tramos + 8 * n_tramos
    tabla, tramos_b, pix = bytearray(), bytearray(), bytearray()
    for tramos in filas:
        tabla += struct.pack('<I', ini_tramos + len(tramos_b))
        for x, px in tramos:
            tramos_b += struct.pack('<HHI', len(px) // 2, x, ini_pix + len(pix))
            pix += px
        tramos_b += struct.pack('<HHI', 0, 0xFFFF, ini_pix + len(pix))
    cab[3] = 512                               # color directo, como los originales de esta carpeta
    cab[5], cab[6] = ANCHO, alto
    cab[7] = (ANCHO // 2) & 0xFFFFFFFF         # esquina = ancla - (ANCHO/2, PIES)
    cab[8] = PIES
    cab[9], cab[10], cab[11], cab[12] = n_tramos, len(pix) // 2, ini_pix, ini_pix
    cab[16] = 0                                # sin paleta
    return struct.pack('<4s19I', *cab) + bytes(tabla) + bytes(tramos_b) + bytes(pix)


def _fuego(i):
    """El frame i (0..5) del aura de fuego."""
    return np.clip(_llamas(i / 6, 78, ALTO_CUERPO * 1.35, 200 + i)
                   + 0.5 * _llamas(i / 6 + 0.5, 60, ALTO_CUERPO * 1.15, 300 + i), 0, 1)


def dibujar():
    """{frame: intensidad} de los 12 frames."""
    out = {}
    # El nucleo se dibuja SIN sumar luz (tapa lo que hay debajo): solo unos destellos sueltos alrededor, nada encima
    # del cuerpo.
    # "que solo sea el fuego" y "se prende y apaga, debe verse siempre" (18/11/2026): las tres capas se ven una tras
    # otra, asi que las tres llevan FUEGO (los 6 del aura repartidos) y la del nucleo suma luz como las otras
    # (FLAGS_M02). Vacias, dejaban huecos sin nada.
    for i, f in enumerate(NUCLEO):
        out[f] = _fuego(2 * i)
    for i, f in enumerate(AURA):
        out[f] = _fuego(i)
    for i, f in enumerate(CHISPAS):
        out[f] = _fuego(2 * i + 1)
    return out


def vista(capas, ruta):
    """Hoja: los 12 frames y debajo 6 instantes del aura completa sobre un muneco gris."""
    _, rgb = _paleta()

    def color(v):
        im = rgb[np.clip(np.rint(v * 255), 0, 255).astype(np.uint8)].astype(np.float64)
        return im * (v >= UMBRAL / 255.0)[..., None]

    frames = [color(capas[f]) for f in FRAMES]
    ancho = (ANCHO + 6) * len(frames)
    hoja = np.zeros((ALTO * 2 + 10, ancho, 3))
    for i, fr in enumerate(frames):
        hoja[:ALTO, i * (ANCHO + 6):i * (ANCHO + 6) + ANCHO] = fr
    muneco = Image.new('L', (ANCHO, ALTO), 0)
    d = ImageDraw.Draw(muneco)
    cx = ANCHO // 2
    d.ellipse((cx - 10, PIES - ALTO_CUERPO, cx + 10, PIES - ALTO_CUERPO + 20), fill=110)
    d.rectangle((cx - 12, PIES - ALTO_CUERPO + 20, cx + 12, PIES - 30), fill=90)
    d.rectangle((cx - 10, PIES - 30, cx - 2, PIES), fill=80)
    d.rectangle((cx + 2, PIES - 30, cx + 10, PIES), fill=80)
    base = np.repeat((np.asarray(muneco, dtype=np.float64))[..., None], 3, -1)
    for k in range(6):
        aura = color(capas[AURA[k]])
        nucleo = color(capas[NUCLEO[k % 3]])
        chis = color(capas[CHISPAS[k % 3]])
        mezcla = np.clip(base + aura + chis, 0, 255)                       # luz sumada (WHITELIGHT)
        tapa = (capas[NUCLEO[k % 3]] >= UMBRAL / 255.0)[..., None]
        mezcla = np.where(tapa, np.clip(0.5 * mezcla + nucleo, 0, 255), mezcla)
        x = k * (ANCHO + 6)
        hoja[ALTO + 10:, x:x + ANCHO] = mezcla
    Image.fromarray(hoja.astype(np.uint8)).resize((ancho * 2, (ALTO * 2 + 10) * 2), Image.NEAREST).save(ruta)


def original(frame) -> bytes:
    """El .shp ORIGINAL de data1.pak (fi.del_cliente ya devuelve el nuestro, que va en el parche)."""
    import zlib
    sys.path.insert(0, str(RAIZ / 'server'))
    import paks_cliente
    datos = (fi.CLIENTE / 'data1.pak').read_bytes()
    nombre = ('shape\\magic\\%03d\\%s.shp' % (EFECTO, frame)).upper()
    for n, _crc, cs, _us, off in paks_cliente._directorio(datos):
        if n.upper() == nombre:
            return zlib.decompress(datos[off:off + cs], -15)
    raise SystemExit('no esta %s en data1.pak' % nombre)


# "que siempre brille el fuego" (18/11/2026): las tres capas duran lo mismo (48 unidades de DelayUnit) y sin el
# frame congelado ni el fundido que traia el halo (s083061 x6 y @SP_EVENT_ACT_FADEOUT), asi el servidor la relanza
# al terminar y no hay bajon (luego: el fuego sin cierre, ver abajo). Solo cambian esas lineas de M02.OBD.
# Con @SP_EVENT_ACT_REMOVE al final (como otros 53 efectos de M02): sin el, la capa no se retiraba nunca y cada
# relanzamiento sumaba otra copia ("se va poniendo cada vez amarillo", 18/11/2026).
# El fuego sale despues de las chispas ("si se ve el fuego pero luego de las chispas", 18/11/2026): por eso las capas
# de chispas y rayos van vacias (dibujar()), y queda solo el fuego.
# "que dure la animacion por siempre" (18/11/2026): el fuego (280) va SIN evento de cierre, asi no se retira nunca y
# queda en bucle; el servidor lo manda una sola vez por jugador y mapa (competicion_premios.brillo_campeon), en vez
# de relanzarlo, que es lo que lo hacia titilar.
# Y LAS TRES SIN CIERRE (20/11/2026, "el vps me desconecta del juego a cada rato"): con el fuego en bucle y las otras
# dos capas con @SP_EVENT_ACT_REMOVE, el cliente se cerraba sin volcado a los 6-17 s de entrar (sospecha: al retirar
# esas capas libera el efecto entero mientras el fuego sigue). Con las tres en bucle (0.0.0.196) no habia cierres.
SPRITES_M02 = {
    279: 'Sprite = Wait, #16, s082011, s082021, s082031, SCROVER',
    280: 'Sprite = Wait, #8, s083011, s083021, s083031, s083041, s083051, s083061, SCROVER',
    328: 'Sprite = Wait, #16, s188011, s188021, s188031, SCROVER',
}
# La capa 279 (el angel original) se dibujaba sin sumar luz: con fuego, opaco. Se le pone la de las otras dos.
FLAGS_M02 = {279: 'Flags = SP_ATTRIB_WHITELIGHT'}
M02 = RAIZ / 'parches' / 'extras' / 'setting' / 'm02.obd'


def m02_original() -> bytes:
    """El setting\\M02.OBD oficial mas nuevo de los paks del cliente (sin contar el nuestro, update27)."""
    import re
    import zlib
    sys.path.insert(0, str(RAIZ / 'server'))
    import paks_cliente
    mejor = None
    for pak in fi.CLIENTE.glob('*.pak'):
        m = re.search(r'(\d+)', pak.stem)
        num = -1 if pak.stem.lower().startswith('data') else int(m.group(1)) if m else 0
        if num == 27:
            continue
        datos = pak.read_bytes()
        for n, _crc, cs, _us, off in paks_cliente._directorio(datos):
            if n.upper() == 'SETTING\\M02.OBD' and (mejor is None or num > mejor[0]):
                mejor = (num, zlib.decompress(datos[off:off + cs], -15))
    if not mejor:
        raise SystemExit('no esta SETTING\\M02.OBD en el cliente')
    return mejor[1]


def m02_parcheado(datos: bytes) -> bytes:
    import re
    hechos = set()
    partes = datos.split(b'[OBJECT]')
    for i, bloque in enumerate(partes[1:], 1):
        m = re.search(rb'Sequence = (\d+)', bloque)
        seq = int(m.group(1)) if m else None
        if seq in SPRITES_M02 and b'\\magic\\025\\' in bloque:
            nuevo, n = re.subn(rb'Sprite = [^\r\n]*', SPRITES_M02[seq].encode('ascii'), bloque, count=1)
            assert n == 1, seq
            if seq in FLAGS_M02 and b'Flags = ' not in nuevo:
                nuevo, n = re.subn(rb'(Process = )', FLAGS_M02[seq].encode('ascii') + b'\r\n' + rb'\1', nuevo, count=1)
                assert n == 1, seq
            partes[i] = nuevo
            hechos.add(seq)
    if hechos != set(SPRITES_M02):
        raise SystemExit('M02.OBD: no se encontraron los objetos %s' % sorted(set(SPRITES_M02) - hechos))
    return b'[OBJECT]'.join(partes)


def leer_directo(datos):
    """(ancho, alto, ox, oy, [[(x, valores RGB565)]]) de un .shp de color directo, para comprobar lo escrito."""
    cab = struct.unpack_from('<4s19I', datos)
    alto = cab[6]
    offs = struct.unpack_from('<%dI' % alto, datos, 80)
    filas = []
    for y in range(alto):
        p, tramos = offs[y], []
        while True:
            n, x, src = struct.unpack_from('<HHI', datos, p)
            p += 8
            if x == 0xFFFF:
                break
            tramos.append((x, np.frombuffer(datos[src:src + 2 * n], '<u2')))
        filas.append(tramos)
    return cab[5], alto, struct.unpack('<i', struct.pack('<I', cab[7]))[0], cab[8], filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vista')
    a = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    capas = dibujar()
    for f in FRAMES:
        plantilla = original(f)
        datos = _a_shp(capas[f], plantilla)
        (SALIDA / ('%s.shp' % f)).write_bytes(datos)
        print(f, len(datos))
    M02.parent.mkdir(parents=True, exist_ok=True)
    orig = m02_original()
    nuevo = m02_parcheado(orig)
    M02.write_bytes(nuevo)
    print('m02.obd', len(orig), '->', len(nuevo))
    if a.vista:
        vista(capas, a.vista)
        print('vista en', a.vista)


if __name__ == '__main__':
    main()
