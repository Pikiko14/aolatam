"""Las monturas propias: la Abyss Taurus (11/11/2026) y las cuatro de las raids (12/11/2026).

"podriamos crear una nueva montura??" (el toro de la hoja del usuario) y "agregaremos estas 4 monturas como premios en
la raid lvl 50 y 60, 2 y 2, que tengan 10% de darla el jefe final".

LO QUE ES UNA MONTURA EN EL CLIENTE. El objeto (item.xml, 物品類別 座騎) lleva un 原型外觀 N: la entrada N (desde 1)
de la lista <騎乘 號碼=... 高度=...> de setting/chardef.xml, que da el objeto de char.obd (Sequence) y la altura a la que
va el jinete (高度: positivo lo sube). NO es 1200 + N: asi salio con el 714 un robot gato (el 67042 de esa lista). El
caballo blanco (White Horse, 原型外觀 1) es la primera: el 1201 de \\chr\\h001\\, altura 0, con dos animaciones (Wait 3
poses, Run 6 poses) x 5 direcciones en <sequence>_Wait.spr y _Run.spr, frames hw013.. y hr013.. (h montado, w/r,
pose, direccion 3 espalda .. 7 frente; la derecha va en espejo). El jinete NO esta en la montura: cada pieza de su
equipo tiene sus frames de montado y el cliente los pone encima, en el mismo punto de los pies.

EL ANCLA. El de la montura no va en los cascos: en el caballo el dibujo baja PIES_BAJO_EL_ANCLA px por debajo, segun
la direccion. Con el ancla en los cascos el toro flotaba ("parece que esta flotando"). Y en espera cada pose se clava
por los pies y por el centro: si no, la montura bailaba ("porque se mueve tanto cuando esta en wait").

LAS HOJAS (docs/sprites_montura/<clave>/, sin versionar):
  taurus  9 filas x 5 columnas: filas 1-6 Run y 7-9 Wait, columnas las 5 direcciones del juego (la hoja del toro).
  rey_leon  (13/11/2026) una sola pose por direccion, en una rejilla de 2 filas x 4 columnas: frente, frente-izquierda,
          izquierda, espalda-izquierda / espalda, espalda-derecha, derecha, frente-derecha. Sin fotogramas: la espera
          respira 1 px y al correr la pose da un saltito (POSE_ESPERA / POSE_CORRER).
  las otras cuatro: 4 columnas (fotogramas) y dos filas por direccion (la primera, de espera; la segunda, de correr),
          en el orden frente, frente-izquierda, izquierda, espalda-izquierda, espalda y las de la derecha. Cada
          montura dice que filas son cada direccion del juego (FILAS) y si alguna hay que voltearla (la del leon que
          mira al frente-izquierda no esta: sale de la del frente-derecha en espejo). Espera 3 poses, correr 4.

Deja, para cada una: parches/extras/shape/chr/<carpeta>/<sequence>_{Wait,Run}.spr, su icono shape/item/<archivo>.shp
y, en un solo bloque cada uno, char.obd, chardef.xml, itemicon4.xml, eng/item.xml; con --db RUTA, los objetos en esa
content.db. Los premios, en server/raid.py (MONTURA_RAID).

    python tools/montura_abismo.py [--db corpus/content.db]
"""
import argparse
import pathlib
import re
import sqlite3
import sys

import numpy as np
from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import fondos_interfaz as fi  # noqa: E402,F401
import mascota_abismo as ma  # noqa: E402
import spr_ewsp  # noqa: E402

EXTRAS = RAIZ / 'parches' / 'extras'
HOJAS = RAIZ / 'docs' / 'sprites_montura'
DESCARGAS = pathlib.Path.home() / 'Downloads'
PRIMER_ASPECTO = 1548              # la lista de chardef.xml del cliente trae 1547: las nuestras van detras, en orden
PIES_BAJO_EL_ANCLA = (13, 12, 7, 14, 16)       # h001 (1201_Wait), por direccion: espalda .. frente
MARCA_INI, MARCA_FIN = 'aolat monturas', '/aolat monturas'
ALTO_OBJETIVO = 105                # alto en px de la pose de frente de las de 8 direcciones (el toro: ~107)
LOMO_TORO = 73                     # el lomo del toro de perfil sobre su ancla (con altura 0 el jinete va sentado;
                                   # con 4 quedaba flotando, 12/11/2026)

S60 = dict(平均攻擊=55, 防禦=55, 魔攻=55, 魔防=55, 精準=8, 靈敏=16, 移動速度=70)
S50 = dict(平均攻擊=45, 防禦=45, 魔攻=45, 魔防=45, 精準=7, 靈敏=14, 移動速度=60)
# 13/11/2026, "montura especial, con stats lvl 70 pero se puede usar a lvl 60 con speed de 80 ... para fisicos y
# magos": la escala de las de 50 y 60 un paso mas, ataque y magia iguales.
S70 = dict(平均攻擊=65, 防禦=65, 魔攻=65, 魔防=65, 精準=9, 靈敏=18, 移動速度=80)

MONTURAS = [
    dict(clave='taurus', nombre='Abyss Taurus', item=83301, icono=59301, sequence=1914, carpeta='h714', nivel=60,
         stats=S60, altura=0, hoja='abyss_taurus/hoja.webp', tipo='rejilla', escala=0.68,
         descripcion='An armored bull born in the abyss beneath Flamefang. Only raiders who defeat Satrixia have '
                     'been able to tame it.'),
    dict(clave='lion', nombre='Blazemane Lion', item=83302, icono=59302, sequence=1915, carpeta='h715', nivel=60,
         altura=0, stats=S60, hoja='leon/hoja.png', descarga='leon', tipo='ocho',
         filas=((9, 9), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         escala_dir=(0.85, 1, 1, 1, 0.85),   # de frente la melena tapaba al jinete ("se ve raro en esos diagonales")
         descripcion='A lion with a mane of living fire, tamed in the depths of Flamefang.'),
    dict(clave='turtle', nombre='Coral Fortress Turtle', item=83303, icono=59303, sequence=1916, carpeta='h716',
         nivel=60, altura=4, stats=S60, hoja='tortuga/hoja.png', descarga='tortuga', tipo='ocho',
         filas=((9, 10), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         descripcion='An ancient turtle that carries a coral fortress on its shell.'),
    # Las hojas caricaturescas (12/11/2026, "cambia los sprites por estos mas caricaturescos"): 5 fotogramas por fila
    # y dos filas por direccion, en el orden frente, frente-izq., izquierda, espalda-izq., espalda y las de la derecha.
    dict(clave='ram', nombre='Frostcrown Ram', item=83304, icono=59304, sequence=1917, carpeta='h717', nivel=50,
         altura=0, stats=S50, hoja='carnero/hoja.png', descarga='carnero', tipo='ocho',
         filas=((9, 10), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         descripcion='A ram crowned with ice from the Warring Realm.'),
    # 13/11/2026, "cambialo por esta montura ... me referia al ciervo que agregamos ayer": el Aurora Stag (83305) pasa
    # a ser el Celestial Lion, con la hoja del leon celestial (6 fotogramas, como el Undead Lion King); mismo objeto,
    # mismas stats y mismo drop (Hades, 10%). La hoja del ciervo queda en ciervo/hoja.png.
    dict(clave='stag', nombre='Celestial Lion', item=83305, icono=59305, sequence=1918, carpeta='h718', nivel=50,
         altura=0, stats=S50, hoja='leon_celestial/hoja.png', descarga='leon_celestial', tipo='ocho',
         filas=((9, 10), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         escala_dir=(0.88, 1, 1, 1, 0.88), espera_fija=True, cuadricula=(6, 10), carrera=6, carrera_por_cuerpo=True,
         descripcion='A celestial lion crowned with a golden halo, said to guard the gates of heaven. Hades of the '
                     'Warring Realm keeps it chained.'),
    # 13/11/2026: no la suelta ninguna raid; se canjea por 1000 Mount Coin en Event Overview > Exchange > Ride and
    # Robots (exchange.xml, receta 19261 del grupo 538). nivel = sus stats (70); nivel_uso = el que pide (60).
    dict(clave='lionking', nombre='Undead Lion King', item=83306, icono=59306, sequence=1919, carpeta='h719', nivel=70,
         nivel_uso=60, altura=0, stats=S70, hoja='rey_leon/hoja.png', descarga='rey_leon', tipo='ocho',
         # la hoja completa (13/11/2026, "cambiemos los sprites del leon por este, aca esta todo"): 5 fotogramas,
         # espera y carrera por direccion, como el carnero. La de una sola pose quedo en rey_leon/hoja_pose.png.
         # El juego usa la vista "de frente" (7) al bajar en diagonal y la "de espaldas" (3) al subir en diagonal;
         # el jinete se pinta siempre encima, y con la cabeza grande del leon quedaba sentado en la corona ("en
         # diagonal derecha abajo se sigue viendo mal", 13/11/2026). En esas dos van sus tres cuartos: de espaldas
         # la de espalda-izquierda y de frente la de frente-izquierda en espejo (mira abajo-derecha).
         # Las vistas de tres cuartos en su lugar quedaban peor: el jinete se pinta de frente o de espaldas y no
         # casaba ("se ve horrible en diagonal"). Vuelven las de verdad, algo mas pequenas (escala_dir) para que la
         # corona no tape tanto al jinete.
         filas=((9, 10), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         escala_dir=(0.88, 1, 1, 1, 0.88),
         espera_fija=True,             # quieto: un solo fotograma que respira 1 px ("cuando esta quieto se mueve
                                       # demasiado": cada pose de espera de la hoja venia dibujada distinta)
         cuadricula=(6, 10), carrera=6,       # la hoja de 6 fotogramas por fila (13/11/2026); las de antes,
                                              # rey_leon/hoja_5.png y hoja_pose.png
         carrera_por_cuerpo=True,      # sin salto anadido y clavada por el cuerpo ("parece que brinca")
         descripcion='The fallen king of the lions, risen from the grave with his rusted crown. Fit for warriors and '
                     'mages alike.'),
]


# ---------------------------------------------------------------------------------------------- recortes
def _sin_fondo(ruta) -> np.ndarray:
    from scipy import ndimage
    im = np.array(Image.open(ruta).convert('RGBA'))
    if im[:, :, 3].min() == 255:
        # fondo blanco: fuera el blanco casi puro que toca el borde de la hoja (el de dentro del dibujo se queda)
        rgb = im[:, :, :3].astype(int)
        blanco = (rgb.min(axis=2) > 232) & (rgb.max(axis=2) - rgb.min(axis=2) < 18)
        manchas, _n = ndimage.label(blanco)
        borde = set(np.unique(np.concatenate([manchas[0], manchas[-1], manchas[:, 0], manchas[:, -1]]))) - {0}
        fondo = np.isin(manchas, list(borde))
        fondo = ndimage.binary_dilation(fondo, iterations=1) & (rgb.min(axis=2) > 205)
        im[fondo, 3] = 0
    return im


def _hoja(m):
    ruta = HOJAS / m['hoja']
    if not ruta.is_file() and m.get('descarga'):
        raise SystemExit('falta %s (copiala de Descargas)' % ruta)
    return ruta


def celdas_rejilla(m, filas=9, columnas=5):
    """La hoja del toro: [fila][columna] -> (imagen recortada, (x, y) de su esquina dentro de su casilla)."""
    from scipy import ndimage
    im = _sin_fondo(_hoja(m))
    mascara = im[:, :, 3] > 16
    etiquetas, n = ndimage.label(mascara, structure=np.ones((3, 3)))
    alto, ancho = mascara.shape
    cw, ch = ancho / columnas, alto / filas
    tam = ndimage.sum(mascara, etiquetas, range(1, n + 1))
    centros = ndimage.center_of_mass(mascara, etiquetas, range(1, n + 1))
    de = {}
    for i, (t, (cy, cx)) in enumerate(zip(tam, centros), 1):
        if t >= 30:
            de.setdefault((min(filas - 1, int(cy // ch)), min(columnas - 1, int(cx // cw))), []).append(i)
    tabla = []
    for f in range(filas):
        fila = []
        for c in range(columnas):
            mm = np.isin(etiquetas, de.get((f, c), []))
            ys, xs = np.where(mm)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            trozo = im[y0:y1, x0:x1].copy()
            trozo[~mm[y0:y1, x0:x1]] = 0
            fila.append((Image.fromarray(trozo, 'RGBA'), (x0 - c * cw, y0 - f * ch)))
        tabla.append(fila)
    return tabla


def filas_ocho(m):
    """Las hojas de 8 direcciones: [fila] -> [4 imagenes recortadas], filas por su altura y fotogramas por su x."""
    from scipy import ndimage
    im = _sin_fondo(_hoja(m))
    mascara = im[:, :, 3] > 20
    etiquetas, n = ndimage.label(ndimage.binary_closing(mascara, iterations=2), structure=np.ones((3, 3)))
    cajas = ndimage.find_objects(etiquetas)
    tam = ndimage.sum(mascara, etiquetas, range(1, n + 1))
    trozos = []
    for i, (caja, t) in enumerate(zip(cajas, tam), 1):
        if t < 800:
            continue
        trozo = im[caja].copy()
        trozo[etiquetas[caja] != i] = 0
        trozos.append(((caja[0].start + caja[0].stop) / 2, caja[1].start, Image.fromarray(trozo, 'RGBA')))
    trozos.sort(key=lambda t: t[0])
    filas = []
    for y, x, t in trozos:
        if filas and abs(filas[-1][0] - y) < 35:
            filas[-1][1].append((x, t))
        else:
            filas.append([y, [(x, t)]])
    return [[t for _x, t in sorted(f[1], key=lambda a: a[0])] for f in filas]


def _suelo(im):
    """La fila mas baja con dibujo (sin el halo casi transparente)."""
    caja = im.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
    return caja[3] if caja else im.height


def _clavar(im, c):
    """El ancla de una pose: el centro del dibujo y sus pies PIES_BAJO_EL_ANCLA[c] por debajo."""
    caja = im.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox() or (0, 0, im.width, im.height)
    return (round((caja[0] + caja[2]) / 2), _suelo(im) - PIES_BAJO_EL_ANCLA[c])


def _escalar(im, k):
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def frames_rejilla(m):
    """El toro: Run de las filas 1-6 con el ancla de su casilla; Wait de las 7-9 clavada por los pies."""
    tabla = celdas_rejilla(m)
    k = m['escala']
    salida = {}
    for anim, filas in (('run', range(0, 6)), ('wait', range(6, 9))):
        lista = []
        for f in filas:
            for c in range(5):
                im, (x, y) = tabla[f][c]
                im2 = _escalar(im, k)
                if anim == 'wait':
                    lista.append((im2, _clavar(im2, c)))
                    continue
                propias = [tabla[g][c] for g in filas]
                pie_x = sum(p[1][0] + p[0].width / 2 for p in propias) / len(propias)
                pie_y = max(p[1][1] + p[0].height for p in propias)
                lista.append((im2, (round((pie_x - x) * k), round((pie_y - y) * k))))
        if anim == 'run':
            for c in range(5):
                mios = [lista[i] for i in range(c, len(lista), 5)]
                delta = PIES_BAJO_EL_ANCLA[c] - max(_suelo(im) - oy for im, (_ox, oy) in mios)
                for i in range(c, len(lista), 5):
                    im, (ox, oy) = lista[i]
                    lista[i] = (im, (ox, oy - delta))
        salida[anim] = lista
    return salida


# El alto de la pose de espera del toro en cada direccion (espalda .. frente). Las hojas de 8 direcciones traen
# algunas direcciones mas pequenas (el leon de perfil 82 px y de frente 105: "el leon no se ve del mismo tamano en
# todas las direcciones", 12/11/2026): cada direccion se escala a la del toro.
ALTOS_TORO = (111, 114, 103, 97, 107)


def _tam(im) -> float:
    """El tamano de un dibujo: la raiz de sus pixeles opacos (igual de grande = misma area, mire a donde mire)."""
    return float(np.sqrt((np.array(im.getchannel('A')) > 40).sum()))


def _grupos(valores, k):
    """Indices de k grupos de valores 1D, partiendo por los k-1 huecos mas grandes."""
    orden = sorted(range(len(valores)), key=lambda i: valores[i])
    huecos = sorted(range(1, len(orden)), key=lambda n: valores[orden[n]] - valores[orden[n - 1]])[-(k - 1):]
    grupo, g = {}, 0
    for n, i in enumerate(orden):
        if n in huecos:
            g += 1
        grupo[i] = g
    return grupo


def filas_rejilla_exacta(m):
    """Hojas de m['cuadricula'] = (columnas, filas) sprites: [fila] -> [imagenes]. Los centros de filas y columnas salen
    de los sprites sueltos (por los huecos mas grandes entre sus centros); cada mancha va entera a la casilla de su
    centro, y las que juntan dos sprites que se tocan se parten por el borde entre casillas. Cortar por celdas iguales
    o agrupar por altura fallaba en las hojas cuyos sprites no van centrados en celdas iguales."""
    from scipy import ndimage
    im = _sin_fondo(_hoja(m))
    columnas, nfilas = m['cuadricula']
    mascara = im[:, :, 3] > 20
    etiquetas, n = ndimage.label(mascara, structure=np.ones((3, 3)))
    tam = np.array(ndimage.sum(mascara, etiquetas, range(1, n + 1)))
    centros = ndimage.center_of_mass(mascara, etiquetas, range(1, n + 1))
    grandes = [i for i in range(n) if tam[i] >= 500]
    mediana = float(np.median([tam[i] for i in grandes]))
    sueltos = [i for i in grandes if tam[i] < 1.6 * mediana]

    def centros_de(valores, k):
        g = _grupos(valores, k)
        return sorted(float(np.mean([v for i, v in enumerate(valores) if g[i] == q])) for q in range(k))
    cy = centros_de([centros[i][0] for i in sueltos], nfilas)
    cx = centros_de([centros[i][1] for i in sueltos], columnas)
    corte_y = [(a + b) / 2 for a, b in zip(cy, cy[1:])]
    corte_x = [(a + b) / 2 for a, b in zip(cx, cx[1:])]
    casilla = np.zeros(mascara.shape + (2,), int)
    casilla[:, :, 0] = np.searchsorted(corte_y, np.arange(mascara.shape[0]))[:, None]
    casilla[:, :, 1] = np.searchsorted(corte_x, np.arange(mascara.shape[1]))[None, :]
    duena = np.full(mascara.shape, -1)
    for i in range(n):
        if tam[i] < 15:
            continue
        sitio = etiquetas == i + 1
        if tam[i] >= 1.6 * mediana:                      # dos sprites pegados: cada pixel a su casilla
            duena[sitio] = casilla[sitio][:, 0] * columnas + casilla[sitio][:, 1]
        else:
            f = int(np.searchsorted(corte_y, centros[i][0]))
            c = int(np.searchsorted(corte_x, centros[i][1]))
            duena[sitio] = f * columnas + c
    tabla = []
    for f in range(nfilas):
        fila = []
        for c in range(columnas):
            mm = duena == f * columnas + c
            ys, xs = np.where(mm)
            if not len(ys):
                raise SystemExit('la casilla %d,%d de la hoja esta vacia' % (f + 1, c + 1))
            trozo = im[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
            trozo[~mm[ys.min():ys.max() + 1, xs.min():xs.max() + 1]] = 0
            fila.append(Image.fromarray(trozo, 'RGBA'))
        tabla.append(fila)
    return tabla


def frames_ocho(m):
    filas = filas_rejilla_exacta(m) if m.get('cuadricula') else filas_ocho(m)
    salida = {}
    # Una sola escala por montura (12/11/2026, "se ven mal algunos tamanos en ciertas direcciones"): las hojas
    # caricaturescas ya traen las direcciones a la misma escala (de perfil es mas baja porque se ve de lado); forzar
    # cada una al alto del toro las deformaba. El alto medio de sus 5 direcciones, el del toro.
    altos = []
    for c in range(5):
        espera = filas[m['filas'][c][0] - 1][0]
        caja = espera.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
        altos.append(caja[3] - caja[1])
    escala = sum(ALTOS_TORO) / sum(altos)
    # 13/11/2026, "el leon se ve pequeno cuando corre ... deben verse en el mismo tamano en todas las direcciones y
    # acciones": las hojas traen la carrera algo mas chica que la espera (el leon de frente-izq.: 113 px contra 128) y
    # cada direccion a su tamano. Cada fila (direccion y accion) se lleva al mismo TAMANO, medido por el area del
    # dibujo (su raiz), no por el alto: de perfil o con las patas estiradas el alto engana.
    # Pero las direcciones NO se igualan entre si (13/11/2026: de frente y de espaldas el leon salia enorme, con la
    # corona por encima del jinete): una sola escala por montura y la carrera de cada direccion, al tamano de su espera.
    espera = {c: sum(_tam(filas[m['filas'][c][0] - 1][p]) for p in (0, 1, 2)) / 3 for c in range(5)}
    salto = m.get('salto') or (0,) * 8
    for anim, cual, poses in (('wait', 0, (0, 1, 2)), ('run', 1, tuple(range(m.get('carrera', 5))))):
        lista = []
        for p in poses:
            for c in range(5):
                fila = filas[m['filas'][c][cual] - 1]
                propio = sum(_tam(fila[q % len(fila)]) for q in poses) / len(poses)
                cual_p = 0 if (anim == 'wait' and m.get('espera_fija')) else p % len(fila)
                k_dir = (m.get('escala_dir') or (1,) * 5)[c]
                im = _escalar(fila[cual_p], escala * espera[c] / propio * k_dir)
                if m['espejo'][c]:
                    im = im.transpose(Image.FLIP_LEFT_RIGHT)
                ox, oy = _clavar(im, c)
                sube = salto[p] if anim == 'run' else (POSE_ESPERA[p] if m.get('espera_fija') else 0)
                lista.append((im, (ox, oy + sube)))
        if anim == 'run' and m.get('carrera_por_cuerpo'):
            # Clavar cada fotograma por su pixel mas bajo hacia botar al cuerpo cada vez que las patas se estiran:
            # en cada direccion, el centro del cuerpo a la misma altura sobre el ancla en todos los fotogramas.
            for c in range(5):
                idx = list(range(c, len(lista), 5))
                alturas = [oy - _centro_y(im) for im, (_ox, oy) in (lista[i] for i in idx)]
                media = sum(alturas) / len(alturas)
                for i, h in zip(idx, alturas):
                    im, (ox, oy) = lista[i]
                    lista[i] = (im, (ox, round(oy + media - h)))
        salida[anim] = lista
    return salida


def _centro_y(im) -> float:
    a = np.array(im.getchannel('A')) > 40
    ys = np.nonzero(a)[0]
    return float(ys.mean()) if len(ys) else im.height / 2


POSE_ESPERA = (0, 1, 0)                 # px que sube la pose en cada fotograma de espera (respira)
POSE_CORRER = (0, 2, 3, 2, 0)           # y al correr (un saltito por zancada)


def frames_pose(m):
    """Una pose por direccion (rejilla de celdas iguales): la misma imagen en todos los fotogramas, subida un poco."""
    im = Image.fromarray(_sin_fondo(_hoja(m)), 'RGBA')
    filas, columnas = m['rejilla']
    cw, ch = im.width / columnas, im.height / filas
    poses = []
    for f, c in m['celdas']:
        celda = np.array(im.crop((round((c - 1) * cw), round((f - 1) * ch), round(c * cw), round(f * ch))))
        # fuera las motas sueltas de la hoja: solo las manchas de cierto tamano (una mota ensanchaba el recorte y
        # descentraba al leon de frente-izquierda)
        from scipy import ndimage
        manchas, n = ndimage.label(celda[:, :, 3] > 20, structure=np.ones((3, 3)))
        tam = ndimage.sum(np.ones_like(manchas), manchas, range(1, n + 1))
        celda[~np.isin(manchas, [i + 1 for i, t in enumerate(tam) if t >= 300])] = 0
        celda = Image.fromarray(celda, 'RGBA')
        poses.append(celda.crop(celda.getchannel('A').point(lambda a: 255 if a > 20 else 0).getbbox()))
    altos = [p.height for p in poses]
    k = sum(ALTOS_TORO) / sum(altos)                  # el alto medio, el del toro (como frames_ocho)
    tamano = sum(_tam(p) for p in poses) / len(poses)
    poses = [_escalar(p, k * tamano / _tam(p)) for p in poses]       # y cada direccion al mismo tamano (area)
    salida = {}
    for anim, subidas in (('wait', POSE_ESPERA), ('run', POSE_CORRER)):
        lista = []
        for d in subidas:
            for c in range(5):
                ox, oy = _clavar(poses[c], c)
                lista.append((poses[c], (ox, oy + d)))
        salida[anim] = lista
    return salida


def frames(m):
    if m['tipo'] == 'pose':
        return frames_pose(m)
    return frames_rejilla(m) if m['tipo'] == 'rejilla' else frames_ocho(m)


def lomo(fr):
    """El alto del lomo de perfil (direccion 5) sobre el ancla: lo mas alto del dibujo cerca del ancla."""
    im, (ox, oy) = fr['wait'][2]
    a = im.getchannel('A').load()
    altos = []
    for dx in (-6, -3, 0, 3, 6):
        x = ox + dx
        if 0 <= x < im.width:
            y = next((y for y in range(im.height) if a[x, y] > 100), None)
            if y is not None:
                altos.append(oy - y)
    return sorted(altos)[len(altos) // 2] if altos else LOMO_TORO


def icono(m, fr) -> bytes:
    im, _ = fr['wait'][2]                                   # de perfil
    return ma._tlhs_suelto(ma._cuadrado(im, 36), r'shape\item\i0004.shp', 0, 0)


# ---------------------------------------------------------------------------------------------- datos del cliente
def bloque_char_obd(m) -> str:
    s = m['sequence']
    if m['tipo'] == 'rejilla' or m.get('carrera') == 6:
        run = 'hr013*, #7, !CharSmokeTwo, hr023*, hr033*, hr043*, hr053*, hr063*'
    else:
        run = 'hr013*, #7, !CharSmokeTwo, hr023*, hr033*, hr043*, hr053*'
    return '\r\n'.join((
        '[OBJECT]',
        'Name = %s %s' % (m['carpeta'].upper(), m['nombre']),
        'Sequence = %d' % s,
        'Directory = \\chr\\%s\\' % m['carpeta'],
        'Sprite = Wait, hw013*, #12, hw023*, hw033*, hw023*',
        'Sprite = Run, %s' % run,
        'SpriteFile = Wait, %d_Wait.spr' % s,
        'SpriteFile = Run, %d_Run.spr' % s,
        '', ''))


def _quitar_viejos(texto, *marcas):
    for ini, fin in marcas:
        texto = ma._sin_bloque(texto, ini, fin)
    return texto


VIEJAS = ('aolat abyss taurus', '/aolat abyss taurus')       # el bloque de cuando solo estaba el toro


def char_obd():
    texto, bom, nl = ma._texto_base(r'setting\char.obd')
    texto = _quitar_viejos(texto, ('; ' + MARCA_INI, '; ' + MARCA_FIN), ('; ' + VIEJAS[0], '; ' + VIEJAS[1]))
    cuerpo = ''.join(bloque_char_obd(m).replace('\r\n', nl) for m in MONTURAS)
    bloque = '; %s%s%s; %s%s' % (MARCA_INI, nl, cuerpo, MARCA_FIN, nl)
    ma._guardar(r'setting\char.obd', texto.rstrip() + nl + nl + bloque, bom, latin=True)


def chardef_xml(alturas):
    """Sus <騎乘> justo detras del ultimo de la lista: el cliente los cuenta en orden y el 原型外觀 es esa cuenta."""
    texto, bom, nl = ma._texto_base(r'setting\chardef.xml')
    texto = _quitar_viejos(texto, ('<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN),
                           ('<!-- %s -->' % VIEJAS[0], '<!-- %s -->' % VIEJAS[1]))
    filas = list(re.finditer(r'<騎乘 [^>]*/>[^\n]*\n?', texto))
    if len(filas) + 1 != PRIMER_ASPECTO:
        raise SystemExit('chardef.xml trae %d monturas: la primera nuestra seria %d, no %d'
                         % (len(filas), len(filas) + 1, PRIMER_ASPECTO))
    fin = filas[-1].end()
    lineas = ''.join('\t<騎乘 號碼="%d" 高度="%d" 層級="DOLL_LAYER_RIDE" 種類="0"/>%s' % (m['sequence'], alturas[m['clave']], nl)
                     for m in MONTURAS)
    bloque = '\t<!-- %s -->%s%s\t<!-- %s -->%s' % (MARCA_INI, nl, lineas, MARCA_FIN, nl)
    ma._guardar(r'setting\chardef.xml', texto[:fin] + bloque + texto[fin:], bom)


def aspecto(m):
    return PRIMER_ASPECTO + MONTURAS.index(m)


def _xml_con(relativa, lineas, cierre='</'):
    texto, bom, nl = ma._texto_base(relativa)
    texto = _quitar_viejos(texto, ('<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN),
                           ('<!-- %s -->' % VIEJAS[0], '<!-- %s -->' % VIEJAS[1]))
    bloque = ('\t<!-- %s -->%s' % (MARCA_INI, nl) + ''.join('\t%s%s' % (l, nl) for l in lineas)
              + '\t<!-- %s -->%s' % (MARCA_FIN, nl))
    fin = texto.rindex(cierre)
    ma._guardar(relativa, texto[:fin] + bloque + texto[fin:], bom)


def fila_item(m) -> str:
    stats = ' '.join('%s="%d"' % kv for kv in m['stats'].items())
    return ('<道具 編號="%d" 原型介面="%d" 原型外觀="%d" 基本名稱="%s" 物品類別="座騎" 物品等級="%d" 等級限制="%d" %s '
            '重量="160" 價格="3000000" 綁定次數="3" 顏色="黃" log等級="80" 說明定義="%s" 寵物座騎裝備="是" 裝備綁定="是" '
            '抽中廣播="是" 收購價格="6000" />' % (m['item'], m['icono'], aspecto(m), m['nombre'], m['nivel'],
                                              m.get('nivel_uso', m['nivel']),
                                              stats, m['descripcion']))


REEMPLAZADAS = RAIZ / 'server' / 'plantillas' / 'monturas_reemplazadas.json'


def _atributos(m) -> dict:
    """Lo que cambia en la fila del objeto del juego que reemplaza (los mismos atributos que fila_item)."""
    d = {'原型介面': str(m['icono']), '原型外觀': str(aspecto(m)), '物品等級': str(m['nivel']),
         '等級限制': str(m.get('nivel_uso', m['nivel'])), '說明定義': m['descripcion']}
    d.update({k: str(v) for k, v in m['stats'].items()})
    d.update({k: None for k in m.get('quitar', ())})          # None: fuera ese atributo
    return d


def reemplazadas_json():
    """{item: {atributo: valor}} de las monturas que reescriben un objeto del juego (cliente_local las aplica a
    item*.xml del cliente y del parche)."""
    import json
    datos = {str(m['item']): _atributos(m) for m in MONTURAS if m.get('reemplaza')}
    REEMPLAZADAS.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def content_db(ruta):
    """Los objetos en la tabla item de content.db: copias de la Flame Eagle (5128) con lo suyo."""
    con = sqlite3.connect(ruta)
    cols = [c[1] for c in con.execute('pragma table_info(item)')]
    base = dict(zip(cols, con.execute("select * from item where id='5128'").fetchone()))
    nombres = {'平均攻擊': ('atk_avg', 'atk'), '防禦': ('def',), '魔攻': ('matk',), '魔防': ('mdef',),
               '精準': ('accuracy',), '靈敏': ('agility',)}
    for m in [x for x in MONTURAS if x.get('reemplaza')]:
        cambios = dict(_atributos(m))
        cambios['move_speed'] = str(m['stats']['移動速度'])
        cambios.update({'hp': None, 'mp': None} if m.get('quitar') else {})
        for k, v in m['stats'].items():
            for col in nombres.get(k, ()):
                cambios[col] = str(v)
        for tabla in [r[0] for r in con.execute("select name from sqlite_master where type='table' and name like 'item%'")]:
            cols_t = [c[1] for c in con.execute('pragma table_info(%s)' % tabla)]
            puestos = {k: v for k, v in cambios.items() if k in cols_t}
            if puestos:
                con.execute('update %s set %s where id=?' % (tabla, ', '.join('"%s"=?' % k for k in puestos)),
                            list(puestos.values()) + [str(m['item'])])
    for m in [x for x in MONTURAS if not x.get('reemplaza')]:
        fila = dict(base)
        fila.update({'id': str(m['item']), '原型介面': str(m['icono']), '原型外觀': str(aspecto(m)),
                     '基本名稱': m['nombre'], '原型名稱': None, 'move_speed': str(m['stats']['移動速度'])})
        if '物品等級' in fila:
            fila['物品等級'] = str(m['nivel'])
        if '等級限制' in fila:
            fila['等級限制'] = str(m.get('nivel_uso', m['nivel']))
        for k, v in m['stats'].items():
            for col in (k,) + nombres.get(k, ()):
                if col in fila:
                    fila[col] = str(v)
        if '說明定義' in fila:
            fila['說明定義'] = m['descripcion']
        con.execute('delete from item where id=?', (str(m['item']),))
        con.execute('insert into item (%s) values (%s)' % (','.join('"%s"' % c for c in cols), ','.join('?' * len(cols))),
                    [fila[c] for c in cols])
    con.commit()
    con.close()
    print('content.db: %d monturas en %s' % (len(MONTURAS), ruta))


# El canje del Undead Lion King (13/11/2026): la fila 19261 de exchange.xml (libre, grupo 0) pasa al grupo 538 (Event
# Overview > Exchange > Ride and Robots) por 1000 Mount Coin. En la copia que lee el servidor y en la del parche.
CANJES = ((19261, 538, 'Undead Lion King', 83306, 89073, 1000),)


BOM = bytes((0xEF, 0xBB, 0xBF))


def exchange_xml():
    for rel in (RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'exchange.xml',
                EXTRAS / 'setting' / 'eng' / 'exchange.xml'):
        crudo = rel.read_bytes()
        bom = crudo.startswith(BOM)
        texto = crudo.decode('utf-8-sig')
        for rid, grupo, nombre, premio, material, cantidad in CANJES:
            fila = ('<exchange 編號="%d" 群組="%d" 獎賞說明="%s" 獎賞1="%d" 獎賞1數量="1" 材料1="%d" 材料1數量="%d"/>'
                    % (rid, grupo, nombre, premio, material, cantidad))
            texto, n = re.subn(r'<exchange 編號="%d" [^>]*/>' % rid, fila, texto, count=1)
            if not n:
                raise SystemExit('no esta la fila %d en %s' % (rid, rel))
        rel.write_bytes((BOM if bom else b'') + texto.encode('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', help='solo meter los objetos en esa content.db')
    a = ap.parse_args()
    if a.db:
        content_db(pathlib.Path(a.db))
        return
    alturas = {}
    for m in MONTURAS:
        fr = frames(m)
        carpeta = EXTRAS / 'shape' / 'chr' / m['carpeta']
        carpeta.mkdir(parents=True, exist_ok=True)
        for anim, lista in fr.items():
            (carpeta / ('%d_%s.spr' % (m['sequence'], anim.capitalize()))).write_bytes(
                spr_ewsp.escribir(lista, anim, prefijo='h'))
        (EXTRAS / 'shape' / 'item').mkdir(parents=True, exist_ok=True)
        (EXTRAS / 'shape' / 'item' / ('i%d.shp' % (m['icono'] - 50000))).write_bytes(icono(m, fr))
        # la altura del jinete: la del toro (probada en el juego) corregida por lo que su lomo sube o baja
        # la altura del jinete, a ojo contra la silla del toro (altura 0): medir el lomo engania con melenas,
        # cuernos y lana (el carnero salia con 17 y el jinete flotaba, 12/11/2026)
        alturas[m['clave']] = m['altura']
        print('%-22s %s seq %d aspecto %d altura %d' % (m['nombre'], m['carpeta'], m['sequence'], aspecto(m),
                                                        alturas[m['clave']]))
    char_obd()
    chardef_xml(alturas)
    _xml_con(r'setting\itemicon4.xml', ['<icon id="%d" dir="\\item\\" normal="i%d" focus="normal" down="normal" '
                                        'disable="normal"/>' % (m['icono'], m['icono'] - 50000) for m in MONTURAS])
    _xml_con(r'setting\eng\item.xml', [fila_item(m) for m in MONTURAS if not m.get('reemplaza')])
    reemplazadas_json()
    exchange_xml()
    content_db(RAIZ / 'corpus' / 'content.db')


if __name__ == '__main__':
    main()
