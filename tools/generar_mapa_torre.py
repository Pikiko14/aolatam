"""El mapa de la Torre de Babel (02/11/2026): 60 plataformas en el cielo estrellado, unidas por puentes, subiendo.

"Cambia el mapa que sea una torre que se vaya caminando y subiendo x piso. Crea el mapa tu". Reemplaza el mapa 133
(el de la torre, server/torre_babel.py) por uno hecho aqui, con tools/editor_mapas/mpcio.py:

* Cada piso es una ARENA de ANCHO_ARENA x ALTO_ARENA casillas de piedra (las de cada 10 pisos, de marmol), con su
  jefe en el centro. Alrededor, cielo nocturno: no se pisa.
* Los pisos van en zigzag y hacia ARRIBA del mapa: 1-6 de izquierda a derecha en la fila de abajo, se sube, 7-12 de
  derecha a izquierda, y asi hasta el 60. Un PUENTE de piedra une cada piso con el siguiente.
* La salida de cada puente la cierra una cortina de luz (el objeto 60402, como las puertas de Dark Cavern) hasta
  matar al jefe del piso: torre_babel.py la pone y la quita, y no deja cruzar su zona mientras esta.

Escribe parches/extras/map/map133.mpc (va al parche de los jugadores) y server/plantillas/torre_babel_mapa.json, donde
el servidor lee la entrada, el centro de cada arena y las casillas de cada cortina.

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

PISOS, POR_FILA = 60, 6
ANCHO_ARENA, ALTO_ARENA = 18, 14
PUENTE, ANCHO_PUENTE = 6, 3
MARGEN = 6

# Pinceles (brush/brush.bNN) y atributos de casilla: 0 se pisa, 1 obstaculo.
CIELO = 0xE8            # cielo nocturno con estrellas
PIEDRA = 0x48           # piedra dorada de templo: las arenas
MARMOL = 0x7E           # marmol con emblema: las arenas de cada 10 pisos
PUENTE_PIEDRA = 0x16    # adoquin gris: los puentes y el borde de las arenas
LIBRE, OBSTACULO = 0, 1

FILAS = (PISOS + POR_FILA - 1) // POR_FILA
ANCHO = 2 * MARGEN + POR_FILA * ANCHO_ARENA + (POR_FILA - 1) * PUENTE
ALTO = 2 * MARGEN + FILAS * ALTO_ARENA + (FILAS - 1) * PUENTE


def _arena(piso):
    """(x0, y0) de la esquina de arriba a la izquierda de la arena de ese piso (1..PISOS)."""
    i = piso - 1
    fila, col = divmod(i, POR_FILA)
    if fila % 2:
        col = POR_FILA - 1 - col               # las filas impares van de derecha a izquierda
    x0 = MARGEN + col * (ANCHO_ARENA + PUENTE)
    y0 = ALTO - MARGEN - (fila + 1) * ALTO_ARENA - fila * PUENTE          # la fila 0 abajo: se sube
    return x0, y0


def _centro(piso):
    x0, y0 = _arena(piso)
    return x0 + ANCHO_ARENA // 2, y0 + ALTO_ARENA // 2


def _puente(piso):
    """Las casillas del puente del piso `piso` al siguiente, y las de su cortina (la fila o columna de su mitad)."""
    ax, ay = _arena(piso)
    bx, by = _arena(piso + 1)
    casillas, cortina = [], []
    if ay == by:                                # en la misma fila: puente horizontal
        x_ini = min(ax, bx) + ANCHO_ARENA
        y_ini = ay + (ALTO_ARENA - ANCHO_PUENTE) // 2
        for x in range(x_ini, x_ini + PUENTE):
            for y in range(y_ini, y_ini + ANCHO_PUENTE):
                casillas.append((x, y))
        medio = x_ini + PUENTE // 2
        cortina = [(medio, y) for y in range(y_ini, y_ini + ANCHO_PUENTE)]
    else:                                       # cambio de fila: puente vertical, hacia arriba
        y_ini = by + ALTO_ARENA
        x_ini = ax + (ANCHO_ARENA - ANCHO_PUENTE) // 2
        for y in range(y_ini, y_ini + PUENTE):
            for x in range(x_ini, x_ini + ANCHO_PUENTE):
                casillas.append((x, y))
        medio = y_ini + PUENTE // 2
        cortina = [(x, medio) for x in range(x_ini, x_ini + ANCHO_PUENTE)]
    return casillas, cortina


def celdas():
    """La cuadricula (6 bytes por casilla: pincel, atributo, 0, 0, 0, 0) y el {casilla: pincel} de lo que se pisa."""
    pisable = {}
    for piso in range(1, PISOS + 1):
        x0, y0 = _arena(piso)
        suelo = MARMOL if piso % 10 == 0 else PIEDRA
        for x in range(x0, x0 + ANCHO_ARENA):
            for y in range(y0, y0 + ALTO_ARENA):
                borde = x in (x0, x0 + ANCHO_ARENA - 1) or y in (y0, y0 + ALTO_ARENA - 1)
                pisable[(x, y)] = PUENTE_PIEDRA if borde else suelo
        if piso < PISOS:
            for c in _puente(piso)[0]:
                pisable[c] = PUENTE_PIEDRA
    grid = bytearray()
    for y in range(ALTO):
        for x in range(ANCHO):
            pincel = pisable.get((x, y))
            grid += bytes((pincel, LIBRE, 0, 0, 0, 0)) if pincel is not None else bytes((CIELO, OBSTACULO, 0, 0, 0, 0))
    return bytes(grid), pisable


def mapa():
    base = mpcio.leer(BASE.read_bytes())
    grid, pisable = celdas()
    m = dict(base)
    m.update(w=ANCHO, h=ALTO, celdas=grid, extra=b'', hueco=b'', objetos=[], rutas=[], puntos=[], resto='',
             tilesets=sorted({CIELO, PIEDRA, MARMOL, PUENTE_PIEDRA}))
    return mpcio.escribir(m), pisable


def disposicion():
    """Lo que necesita el servidor: entrada, centro de cada arena y, por puente, su zona y su cortina."""
    x0, y0 = _arena(1)
    pisos = []
    for piso in range(1, PISOS + 1):
        d = {'piso': piso, 'centro': list(_centro(piso))}
        if piso < PISOS:
            casillas, cortina = _puente(piso)
            d['puente'] = [list(c) for c in casillas]
            d['cortina'] = [list(c) for c in cortina]
        pisos.append(d)
    return {'_nota': 'Generado por tools/generar_mapa_torre.py (mapa 133, %dx%d).' % (ANCHO, ALTO),
            'ancho': ANCHO, 'alto': ALTO, 'entrada': [x0 + 2, y0 + ALTO_ARENA // 2], 'pisos': pisos}


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
