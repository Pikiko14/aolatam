"""El mapa de la Torre de Babel (02/11/2026): una torre de 60 pisos, uno encima de otro, con escaleras entre ellos.

"Cambia el mapa que sea una torre que se vaya caminando y subiendo x piso. Crea el mapa tu" y despues "que el mapa
parezca una torre, que salgan escaleras y se tengan que subir al otro piso". Reemplaza el mapa 133 (el de la torre,
server/torre_babel.py) por uno hecho aqui, con tools/editor_mapas/mpcio.py:

* Una sola COLUMNA alta y estrecha sobre el cielo estrellado: la torre. Sus muros (los lados y el suelo grueso entre
  un piso y otro) no se pisan.
* Cada piso es una SALA de ANCHO_SALA x ALTO_SALA casillas, con su jefe en el centro. Toda la torre es de la misma
  piedra dorada (SUELO): salas, escaleras y muros, que no se pisan. El piso 1 abajo del todo y el 60 arriba.
* Del centro del borde de arriba de cada sala sale una ESCALERA que atraviesa el suelo y llega a la sala de encima:
  la unica forma de subir. Se pisan sus casillas (el pincel de escalones) y encima va el objeto de la escalera de
  marmol con barandas doradas de la Torre Dorada (12583), que baja hasta la sala de abajo y sube hasta la de arriba.
* El pie de cada escalera lo cierra una cortina de luz (el objeto 60402, como las puertas de Dark Cavern) hasta
  matar al jefe del piso: torre_babel.py la pone y la quita, y no deja subir mientras esta.

Escribe parches/extras/map/map133.mpc (va al parche de los jugadores) y server/plantillas/torre_babel_mapa.json, donde
el servidor lee la entrada, el centro de cada sala y, por escalera, sus casillas ("puente") y las de su cortina.

    python tools/generar_mapa_torre.py
    python tools/instalar_mapa.py parches/extras/map/map133.mpc --stage 133      # cliente local + transitable.bin
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
import mpcio

SALIDA_MPC = RAIZ / 'parches' / 'extras' / 'map' / 'map133.mpc'
SALIDA_JSON = RAIZ / 'server' / 'plantillas' / 'torre_babel_mapa.json'
BASE = RAIZ / 'tools' / 'editor_mapas' / 'salida' / 'MAP900.mpc'      # de aqui salen cabecera, eventos y dialogos

PISOS = 60
ANCHO_SALA, ALTO_SALA = 24, 11          # lo que se pisa de cada piso
ESCALERA, ANCHO_ESCALERA = 5, 3         # el suelo entre dos pisos, que la escalera atraviesa
MURO = 2                                # el grosor de los muros de los lados
MARGEN = 6                              # cielo alrededor de la torre

# Pinceles (brush/brush.bNN) y atributos de casilla: 0 se pisa, 1 obstaculo.
CIELO = 0xE8            # cielo nocturno con estrellas
PIEDRA = 0x48           # piedra dorada de templo: el suelo de las salas
MARMOL = 0x7E           # marmol con emblema: las salas de cada 10 pisos
MURO_PIEDRA = 0x16      # adoquin gris: los muros de la torre y el borde de las salas
ESCALONES = 0x3A        # escalones de piedra: las escaleras
LIBRE, OBSTACULO = 0, 1
# "La de la torre debe verse homogeneo" (02/11/2026): toda la torre, salas, escaleras y muros, del mismo pincel; los
# muros siguen sin pisarse y lo que separa un piso de otro es la escalera dorada.
SUELO = PIEDRA
CELDA = 32                              # px por casilla
OBJETO_ESCALERA = 12583                 # 黃金塔_樓梯01: sus escalones suben recto, de abajo arriba de la imagen
AJUSTE_ESCALERA = 38                    # px: el centro de los escalones queda 38 px por encima del ancla del sprite

ANCHO = 2 * MARGEN + 2 * MURO + ANCHO_SALA
ALTO = 2 * MARGEN + PISOS * ALTO_SALA + (PISOS - 1) * ESCALERA
# El cliente guarda la posicion en pixeles como un entero de 16 bits con signo: con 1086 filas (34752 px) el piso 1
# quedaba en y negativa ("no me veo", 02/11/2026). Todo el mapa tiene que caber en 32767 px.
assert ALTO * 32 <= 32767, ALTO
X_SALA = MARGEN + MURO                  # la primera columna que se pisa de las salas


def _sala(piso):
    """(x0, y0) de la esquina de arriba a la izquierda de la sala de ese piso (1 abajo, PISOS arriba)."""
    y0 = ALTO - MARGEN - piso * ALTO_SALA - (piso - 1) * ESCALERA
    return X_SALA, y0


def _centro(piso):
    x0, y0 = _sala(piso)
    return x0 + ANCHO_SALA // 2, y0 + ALTO_SALA // 2


def _escalera(piso):
    """Las casillas de la escalera del piso `piso` al de encima, y las de su cortina (la fila de abajo del todo)."""
    x0, y0 = _sala(piso)
    xi = x0 + (ANCHO_SALA - ANCHO_ESCALERA) // 2
    casillas = [(x, y) for y in range(y0 - ESCALERA, y0) for x in range(xi, xi + ANCHO_ESCALERA)]
    cortina = [(x, y0 - 1) for x in range(xi, xi + ANCHO_ESCALERA)]
    return casillas, cortina


def objetos():
    """Una escalera por paso entre pisos, centrada en sus casillas: [id, x, y, 0, 0, 192, extra] como los de MAP900."""
    out = []
    for piso in range(1, PISOS):
        casillas = _escalera(piso)[0]
        xs = [x for x, _ in casillas]; ys = [y for _, y in casillas]
        cx = (min(xs) + max(xs) + 1) * CELDA // 2
        cy = (min(ys) + max(ys) + 1) * CELDA // 2
        out.append([OBJETO_ESCALERA, cx, cy + AJUSTE_ESCALERA, 0, 0, 192, '00' * 50])
    return out


def celdas():
    """La cuadricula (6 bytes por casilla: pincel, atributo, 0, 0, 0, 0) y el {casilla: pincel} de lo que se pisa."""
    pisable, muro = {}, set()
    for x in range(MARGEN, ANCHO - MARGEN):                 # la torre entera es muro...
        for y in range(MARGEN, ALTO - MARGEN):
            muro.add((x, y))
    for piso in range(1, PISOS + 1):                        # ...menos sus salas
        x0, y0 = _sala(piso)
        for x in range(x0, x0 + ANCHO_SALA):
            for y in range(y0, y0 + ALTO_SALA):
                pisable[(x, y)] = SUELO
        if piso < PISOS:                                    # ...y sus escaleras
            for c in _escalera(piso)[0]:
                pisable[c] = SUELO
    grid = bytearray()
    for y in range(ALTO):
        for x in range(ANCHO):
            if (x, y) in pisable:
                grid += bytes((pisable[(x, y)], LIBRE, 0, 0, 0, 0))
            elif (x, y) in muro:
                grid += bytes((SUELO, OBSTACULO, 0, 0, 0, 0))
            else:
                grid += bytes((CIELO, OBSTACULO, 0, 0, 0, 0))
    return bytes(grid), pisable


def mapa():
    base = mpcio.leer(BASE.read_bytes())
    grid, pisable = celdas()
    m = dict(base)
    m.update(w=ANCHO, h=ALTO, celdas=grid, extra=b'', hueco=b'', objetos=objetos(), rutas=[], puntos=[], resto='',
             tilesets=sorted({CIELO, SUELO}))
    return mpcio.escribir(m), pisable


def disposicion():
    """Lo que necesita el servidor: entrada, centro de cada sala y, por escalera, sus casillas y su cortina."""
    x0, y0 = _sala(1)
    pisos = []
    for piso in range(1, PISOS + 1):
        d = {'piso': piso, 'centro': list(_centro(piso))}
        if piso < PISOS:
            casillas, cortina = _escalera(piso)
            d['puente'] = [list(c) for c in casillas]
            d['cortina'] = [list(c) for c in cortina]
        pisos.append(d)
    return {'_nota': 'Generado por tools/generar_mapa_torre.py (mapa 133, %dx%d): "puente" son las casillas de la '
                     'escalera de cada piso al de encima.' % (ANCHO, ALTO),
            'ancho': ANCHO, 'alto': ALTO, 'entrada': [x0 + ANCHO_SALA // 2, y0 + ALTO_SALA - 3], 'pisos': pisos}


def main():
    datos, pisable = mapa()
    SALIDA_MPC.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_MPC.write_bytes(datos)
    SALIDA_JSON.write_text(json.dumps(disposicion(), ensure_ascii=False) + '\n', encoding='utf-8')
    print('escrito', SALIDA_MPC.relative_to(RAIZ), '(%dx%d, %d bytes, %d casillas pisables)' % (
        ANCHO, ALTO, len(datos), len(pisable)))
    print('escrito', SALIDA_JSON.relative_to(RAIZ))


if __name__ == '__main__':
    main()
