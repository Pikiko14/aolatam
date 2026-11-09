"""Mapas del tesoro (treasuremap.xml).

101 mapas en el pak vigente (UPDATE8). Cada uno dice que cofre dibuja, de
que tabla de drop saca el premio, y en que escenas y puntos de disparo
puede aparecer.

    <藏寶圖 編號="1" 名稱="Dusty Wooden Box" 寶箱圖形="60153"
            掉寶資料="473" 場景01="41" 觸發點01="100" .../>

Lo que NO esta en el cliente es la REGLA DE SELECCION: cual de los puntos
sale cada vez. Eso lo decidia el servidor.
"""
import json
import pathlib
import random

_TABLA = None


def tabla() -> list:
    global _TABLA
    if _TABLA is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'mapas_tesoro.json'
        try:
            _TABLA = json.loads(f.read_text(encoding='utf-8'))['filas']
        except Exception:
            _TABLA = []
    return _TABLA


def de_id(mid: int):
    for m in tabla():
        if m.get('id') == int(mid):
            return m
    return None


def en_escena(stage: int) -> list:
    """Los mapas que pueden aparecer en ese escenario."""
    return [m for m in tabla() if int(stage) in (m.get('escenas') or [])]


def punto_al_azar(mid: int):
    """Un punto de disparo del mapa. SUPOSICION: el cliente no dice cual."""
    m = de_id(mid)
    pts = (m or {}).get('puntos') or []
    return random.choice(pts) if pts else None


# Los mapas van de mas facil a mas dificil (Dusty Wooden Box en la escena 41 ... Robber Lord's Warehouse en las de nivel
# alto). Solo se usan del 1 al 70: del 71 al 91 no tienen escena, el 101 no tiene premio y el 100 (Qiduo's Magic Box) es
# de evento. Son 7 franjas de 10, y el nivel medio de los Map Piece del album (1..10) elige la franja.
# SUPOSICION nuestra: el cliente no dice que regla usaba el servidor (09/11/2026).
MAPA_MAXIMO = 70
MAPAS_POR_FRANJA = 10
FRANJAS = MAPA_MAXIMO // MAPAS_POR_FRANJA


def franja_de_nivel(nivel: int) -> int:
    nivel = max(1, min(10, int(nivel or 1)))
    return -(-nivel * FRANJAS // 10)


def _franja(franja: int) -> list:
    return [m for m in tabla() if m.get('drop') and m.get('escenas')
            and MAPAS_POR_FRANJA * (franja - 1) < int(m.get('id') or 0) <= min(MAPA_MAXIMO, MAPAS_POR_FRANJA * franja)]


def casilla(escena: int, punto: int):
    """La casilla (x, y) del punto de disparo `punto` en la escena: es un tag del mapa (触发点 100 -> tag 100)."""
    import eventos
    cas = eventos.casillas_de_tag(int(escena), int(punto))
    return tuple(cas[0]) if cas else None


def elegir(nivel: int, azar=random):
    """(mapa, escena, punto) para un album completo, o None. Solo combinaciones cuyo punto existe en la escena, para que
    el cliente pueda marcarlo y el servidor sepa donde esta."""
    for n in range(franja_de_nivel(nivel), 0, -1):
        opciones = [(int(m['id']), int(e), int(p)) for m in _franja(n)
                    for e in (m.get('escenas') or []) for p in (m.get('puntos') or []) if casilla(e, p)]
        if opciones:
            return azar.choice(opciones)
    return None
