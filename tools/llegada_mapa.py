"""Donde aparece el jugador al entrar a un mapa: la ZONA 71 que se dibuja en el editor de mapas.

En el editor: pestana Zonas, "id a crear" 71, Dibujar (Z) y marca un poligono donde quieres que salga la gente.
Al exportar y correr tools/subir_mapa.py, todos los tornados de plantillas/portales.json que llevan a ese mapa
pasan a dejar al jugador en el centro de esa zona (la casilla pisable mas cercana a su centro). Sin zona 71 no se
toca nada.

    python tools/llegada_mapa.py 900                     # dice que cambiaria
    python tools/llegada_mapa.py 900 --escribir          # lo escribe en portales.json
"""
import json
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PORTALES = RAIZ / 'server' / 'plantillas' / 'portales.json'
ZONA_LLEGADA = '71'


def _pisa(mpc: bytes):
    w, h = struct.unpack_from('<II', mpc, 4)
    return lambda x, y: 0 <= x < w and 0 <= y < h and mpc[96 + ((h - 1 - y) * w + x) * 6 + 1] & 3 == 0


def _dentro(t, poligono):
    """Punto en poligono (rayo hacia la derecha); el borde cuenta como dentro."""
    x, y = t
    dentro = False
    for (x1, y1), (x2, y2) in zip(poligono, poligono[1:] + poligono[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro or any(tuple(v) == t for v in poligono)


def casilla(n, mpc_path):
    """(x, y) donde se aparece en el mapa `n`, o None si el mapa no trae zona 71."""
    sys.path.insert(0, str(RAIZ / 'server'))
    sys.path.insert(0, str(RAIZ / 'tools'))
    import propagar_eventos as pe
    mpc_path = pathlib.Path(mpc_path)
    poligono = [tuple(v) for v in (pe._del_mapa(n, mpc_path)['tags'].get(ZONA_LLEGADA) or [])]
    if len(poligono) > 1 and poligono[0] == poligono[-1]:
        poligono = poligono[:-1]
    if not poligono:
        return None
    pisa = _pisa(mpc_path.read_bytes())
    cx = sum(v[0] for v in poligono) / len(poligono)
    cy = sum(v[1] for v in poligono) / len(poligono)
    xs, ys = [v[0] for v in poligono], [v[1] for v in poligono]
    cand = [(x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1)
            if _dentro((x, y), poligono) and pisa(x, y)]
    if not cand:
        raise ValueError('la zona 71 del mapa %d no tiene ninguna casilla pisable' % n)
    return min(cand, key=lambda t: ((t[0] - cx) ** 2 + (t[1] - cy) ** 2, t))


def aplicar(n, mpc_path, escribir=True):
    """Pone la llegada de la zona 71 en los tornados que van al mapa `n`. Devuelve [(entidad, antes, despues)]."""
    t = casilla(n, mpc_path)
    if t is None:
        return []
    j = json.loads(PORTALES.read_text(encoding='utf-8'))
    cambios = []
    for por in (p for lista in j['mapas'].values() for p in lista):
        if por.get('destino') == n and tuple(por.get('llegada') or ()) != t:
            cambios.append((por.get('entity'), por.get('llegada'), list(t)))
            por['llegada'] = list(t)
    if cambios and escribir:
        # El mismo formato que tiene el archivo: indent 1, sin escapar acentos, CRLF y salto final.
        PORTALES.write_bytes((json.dumps(j, indent=1, ensure_ascii=False) + '\n').replace('\n', '\r\n').encode('utf-8'))
    return cambios


def main():
    n = int(sys.argv[1])
    mpc = RAIZ / 'tools' / 'mapas_propios' / ('map%d.mpc' % n)
    t = casilla(n, mpc)
    if t is None:
        print('  el mapa %d no trae zona 71: la llegada de sus tornados no cambia' % n)
        return
    cambios = aplicar(n, mpc, escribir='--escribir' in sys.argv)
    print('  zona 71 -> se aparece en %s' % (t,))
    for ent, antes, despues in cambios:
        print('  tornado %s: llegada %s -> %s' % (ent, antes, despues))
    if not cambios:
        print('  los tornados ya llegan ahi')


if __name__ == '__main__':
    main()
