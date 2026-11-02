"""El mapa de la Torre de Babel (02/11/2026): las salas de la Limitless Tower del juego, un piso por sala.

"Que parezca una torre... el mapa se ve horrible, se empieza del piso 1 y se va subiendo; si te es dificil, que cada
piso sea 1 tp al piso nuevo". El mapa hecho a mano (salas de piedra y escaleras) no parecia una torre, asi que el 133
(el de la torre, server/torre_babel.py) pasa a ser una copia del 110, la Limitless Tower: doce salas de torre con sus
muros de marmol, sus escaleras y sus nubes. Cada piso es una sala: al matar al jefe, todos los de la copia suben a la
sala siguiente (torre_babel.subir, un salto dentro del mismo mapa) y alli sale el jefe nuevo. Las salas van de abajo
arriba del mapa y, como son doce y los pisos 60, se repiten cinco veces.

Escribe parches/extras/map/map133.mpc (va al parche de los jugadores) y server/plantillas/torre_babel_mapa.json, donde
el servidor lee por piso su sala: donde se llega y donde sale el jefe.

    python tools/generar_mapa_torre.py
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
import mpcio

SALIDA_MPC = RAIZ / 'parches' / 'extras' / 'map' / 'map133.mpc'
SALIDA_JSON = RAIZ / 'server' / 'plantillas' / 'torre_babel_mapa.json'
ORIGEN = RAIZ / 'tools' / 'originales' / 'map110.mpc'     # la Limitless Tower, sacada de los .pak del cliente

PISOS = 60
SALA_MINIMA = 500          # casillas: lo que es menos no es una sala (rincones sueltos)
LLEGADA = 6                # casillas al sur del centro donde se aparece, para no caer encima del jefe
SEPARACION = 4             # y nunca a menos de esto del jefe


def _salas(m):
    """Las zonas pisables separadas del mapa (cada una una sala), de abajo arriba."""
    w, h, cel = m['w'], m['h'], m['celdas']

    def libre(x, y):
        return 0 <= x < w and 0 <= y < h and cel[(y * w + x) * 6 + 1] == 0
    visto, salas = set(), []
    for y in range(h):
        for x in range(w):
            if not libre(x, y) or (x, y) in visto:
                continue
            pila, sala = [(x, y)], []
            visto.add((x, y))
            while pila:
                a, b = pila.pop()
                sala.append((a, b))
                for n in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if libre(*n) and n not in visto:
                        visto.add(n)
                        pila.append(n)
            if len(sala) >= SALA_MINIMA:
                salas.append(sala)
    salas.sort(key=lambda s: (-sum(y for _, y in s) / len(s), sum(x for x, _ in s) / len(s)))
    return salas


def _cerca(sala, x, y):
    return min(sala, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)


def disposicion(m):
    salas = []
    for sala in _salas(m):
        cx = sum(x for x, _ in sala) / len(sala)
        cy = sum(y for _, y in sala) / len(sala)
        centro = _cerca(sala, cx, cy)
        lejos = [c for c in sala if (c[0] - centro[0]) ** 2 + (c[1] - centro[1]) ** 2 >= SEPARACION ** 2]
        salas.append({'centro': list(centro), 'llegada': list(_cerca(lejos, centro[0], centro[1] + LLEGADA))})
    pisos = [dict(piso=p, sala=(p - 1) % len(salas), **salas[(p - 1) % len(salas)]) for p in range(1, PISOS + 1)]
    return {'_nota': 'Generado por tools/generar_mapa_torre.py: el mapa 133 es la Limitless Tower (110), %d salas; '
                     'cada piso es una sala, "llegada" donde se aparece y "centro" donde sale el jefe.' % len(salas),
            'ancho': m['w'], 'alto': m['h'], 'salas': len(salas), 'entrada': pisos[0]['llegada'], 'pisos': pisos}


def main():
    datos = ORIGEN.read_bytes()
    m = mpcio.leer(datos)
    lay = disposicion(m)
    SALIDA_MPC.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_MPC.write_bytes(datos)
    SALIDA_JSON.write_text(json.dumps(lay, ensure_ascii=False) + '\n', encoding='utf-8')
    print('escrito', SALIDA_MPC.relative_to(RAIZ), '(%dx%d, %d salas)' % (m['w'], m['h'], lay['salas']))
    print('escrito', SALIDA_JSON.relative_to(RAIZ))


if __name__ == '__main__':
    main()
