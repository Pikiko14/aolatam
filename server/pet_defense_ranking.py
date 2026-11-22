"""Pet Defense, fase 4 (22/11/2026): las partidas guardadas, el ranking por temporadas, los rangos y los premios.

* LAS PARTIDAS: cada una que acaba (victoria, derrota o abandono habiendo pasado al menos una oleada) va a
  data/pet_defense.db con su temporada, personaje, puntos, oleadas, tiempo y resultado (pet_defense_partida.terminar).
* LAS TEMPORADAS: de 'dias' dias desde 'inicio' (plantillas/pet_defense.json, "temporada"). La 1 empieza en 'inicio'.
* EL RANKING: la MEJOR partida de cada personaje en la temporada (mas puntos; a igualdad, menos tiempo), los 'top'
  primeros.
* LOS RANGOS, por la mejor partida de la temporada: Bronze, Silver y Gold por puntos ('rangos'); Angel si ademas esta
  entre los 10 primeros y Champion el 1o (con al menos los puntos de Bronze).
* LOS PREMIOS: al empezar una temporada nueva (cron, desde el reloj de competiciones) se reparten los de la anterior
  segun el rango final de cada uno: Angel Gold y, si se configuran, objetos con su caducidad. Van a la cola de
  competicion_premios (tabla competiciones_premios del servidor de cuentas), que los entrega sola cuando el jugador
  esta conectado, aunque la temporada acabe estando el offline. Cada temporada se reparte una sola vez.
"""
import datetime as dt
import json
import logging
import pathlib
import sqlite3
import threading
import time

log = logging.getLogger('pet_defense')

DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'pet_defense.db'
STAGE_PREMIO = 917
_LOCK = threading.RLock()
RANGOS = ('Champion', 'Angel', 'Gold', 'Silver', 'Bronze')


def _cfg():
    import pet_defense
    return pet_defense.config()


def _con():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('CREATE TABLE IF NOT EXISTS partidas (id INTEGER PRIMARY KEY AUTOINCREMENT, temporada INTEGER, '
                'char_id INTEGER, usuario TEXT, nombre TEXT, nivel INTEGER, resultado TEXT, puntos INTEGER, '
                'oleadas INTEGER, segundos INTEGER, fecha REAL)')
    con.execute('CREATE INDEX IF NOT EXISTS partidas_temporada ON partidas (temporada, char_id)')
    con.execute('CREATE TABLE IF NOT EXISTS temporadas_cerradas (temporada INTEGER PRIMARY KEY, fecha REAL, '
                'premiados INTEGER)')
    con.execute('CREATE TABLE IF NOT EXISTS entradas (char_id INTEGER, dia TEXT, fecha REAL)')
    con.execute('CREATE INDEX IF NOT EXISTS entradas_dia ON entradas (char_id, dia)')
    return con


# ---------------------------------------------------------------------------------------------- partidas al dia
# "Se puede jugar maximo 3 veces el juego al dia por personaje" (22/11/2026): cuenta cada partida que EMPIEZA (al
# cargar el mapa con la partida nueva), por dia del servidor (de medianoche a medianoche, hora local).
def _dia(ahora=None):
    return dt.datetime.fromtimestamp(time.time() if ahora is None else ahora).strftime('%Y-%m-%d')


def partidas_hoy(char_id, ahora=None):
    with _LOCK:
        con = _con()
        try:
            return con.execute('SELECT COUNT(*) FROM entradas WHERE char_id=? AND dia=?',
                               (int(char_id), _dia(ahora))).fetchone()[0]
        finally:
            con.close()


def maximo_al_dia():
    return int(_cfg().get('partidas_por_dia', 3) or 0)


def quedan_hoy(char_id, ahora=None):
    """Cuantas partidas le quedan hoy a ese personaje (None si no hay limite)."""
    tope = maximo_al_dia()
    if tope <= 0:
        return None
    return max(0, tope - partidas_hoy(char_id, ahora))


def anotar_entrada(char_id, ahora=None):
    ahora = time.time() if ahora is None else ahora
    with _LOCK:
        con = _con()
        try:
            con.execute('INSERT INTO entradas VALUES (?,?,?)', (int(char_id), _dia(ahora), ahora))
            con.commit()
        finally:
            con.close()


# ---------------------------------------------------------------------------------------------- AG por oleada
def premiar_oleadas(ses, oleadas, ahora=None):
    """'ag_por_oleada' Angel Gold por cada oleada superada ("100 de AG por cada wave superado", 22/11/2026), por la
    cola de competicion_premios (lo entrega sola en segundos, aunque se desconecte). Devuelve el AG."""
    import cuentas
    ag = int(_cfg().get('ag_por_oleada', 0) or 0) * int(oleadas or 0)
    p = getattr(ses, 'personaje', None)
    usuario = getattr(ses, 'usuario', None)
    if ag <= 0 or p is None or not usuario:
        return 0
    ahora = time.time() if ahora is None else ahora
    plan = dict(exp=0, oro=0, creditos=0, skill_exp=0, skill_exp_ppm=0, items=[], angel_gold=ag, stage=STAGE_PREMIO,
                skill_rewards=[], usuario=usuario, pet_defense='oleadas')
    with cuentas._LOCK:
        cc = cuentas._get_conn()
        try:
            cc.execute('CREATE TABLE IF NOT EXISTS competiciones_premios '
                       '(ronda TEXT, char_id INTEGER, estado TEXT, plan TEXT, PRIMARY KEY(ronda,char_id))')
            cc.execute('INSERT OR IGNORE INTO competiciones_premios VALUES (?,?,?,?)',
                       ('petdefense-%d-%.3f' % (int(p.char_id), ahora), int(p.char_id), 'pendiente', json.dumps(plan)))
            cc.commit()
        finally:
            cc.close()
    log.info('Pet Defense: %s supera %d oleadas: %d AG', getattr(p, 'nombre', '?'), oleadas, ag)
    return ag


# ---------------------------------------------------------------------------------------------- temporadas
def temporada(ahora=None):
    """(numero, inicio, fin) de la temporada de `ahora` (timestamps). Antes de la primera, la 1."""
    t = _cfg().get('temporada') or {}
    dias = max(1, int(t.get('dias', 14)))
    inicio = dt.datetime.fromisoformat(str(t.get('inicio', '2026-11-22'))).timestamp()
    ahora = time.time() if ahora is None else ahora
    n = max(0, int((ahora - inicio) // (dias * 86400)))
    desde = inicio + n * dias * 86400
    return n + 1, desde, desde + dias * 86400


# ---------------------------------------------------------------------------------------------- partidas
def guardar(ses, datos, ahora=None):
    """Guarda una partida acabada. datos: el resultado_datos de la partida. Devuelve True si se guardo."""
    if datos.get('resultado') == 'abandono' and not datos.get('oleadas'):
        return False
    p = getattr(ses, 'personaje', None)
    if p is None:
        return False
    ahora = time.time() if ahora is None else ahora
    n = temporada(ahora)[0]
    with _LOCK:
        con = _con()
        try:
            con.execute('INSERT INTO partidas (temporada, char_id, usuario, nombre, nivel, resultado, puntos, oleadas, '
                        'segundos, fecha) VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (n, int(getattr(p, 'char_id', 0) or 0), str(getattr(ses, 'usuario', '') or ''),
                         str(getattr(p, 'nombre', '?')), int(getattr(p, 'nivel', 0) or 0), datos.get('resultado'),
                         int(datos.get('puntos', 0)), int(datos.get('oleadas', 0)), int(datos.get('segundos', 0)), ahora))
            con.commit()
        finally:
            con.close()
    return True


def _mejores(con, n):
    """La mejor partida de cada personaje en la temporada n, ordenadas: [(char_id, usuario, nombre, nivel, puntos,
    oleadas, segundos, resultado)]."""
    filas = con.execute('SELECT char_id, usuario, nombre, nivel, puntos, oleadas, segundos, resultado, id FROM partidas '
                        'WHERE temporada=? ORDER BY puntos DESC, segundos ASC, id ASC', (int(n),)).fetchall()
    vistos, out = set(), []
    for f in filas:
        if f[0] in vistos:
            continue
        vistos.add(f[0])
        out.append(tuple(f[:8]))
    return out


def ranking(n=None, top=None):
    """Los `top` mejores de la temporada n (la actual por defecto)."""
    n = temporada()[0] if n is None else n
    top = int(_cfg().get('ranking_top', 10)) if top is None else top
    with _LOCK:
        con = _con()
        try:
            return _mejores(con, n)[:top]
        finally:
            con.close()


def mi_marca(char_id, n=None):
    """(puesto 1.., fila) de ese personaje en la temporada n, o (None, None) si no jugo."""
    n = temporada()[0] if n is None else n
    with _LOCK:
        con = _con()
        try:
            for i, f in enumerate(_mejores(con, n)):
                if f[0] == int(char_id):
                    return i + 1, f
        finally:
            con.close()
    return None, None


def rango(puntos, puesto):
    """El rango de esa marca: Champion (1o), Angel (top 10), Gold, Silver, Bronze o None. Champion y Angel necesitan al
    menos los puntos de Bronze."""
    r = _cfg().get('rangos') or {}
    bronce = int(r.get('Bronze', 5000))
    if puesto == 1 and puntos >= bronce:
        return 'Champion'
    if puesto and puesto <= int(r.get('angel_top', 10)) and puntos >= bronce:
        return 'Angel'
    for nombre in ('Gold', 'Silver', 'Bronze'):
        if puntos >= int(r.get(nombre, {'Gold': 20000, 'Silver': 12000, 'Bronze': 5000}[nombre])):
            return nombre
    return None


# ---------------------------------------------------------------------------------------------- premios
def plan_de(rango_final, ahora=None):
    """El plan de premio (el formato de competicion_premios) de ese rango, o None si no tiene."""
    premio = (_cfg().get('premios') or {}).get(rango_final or '') or {}
    ag = int(premio.get('angel_gold', 0))
    items = []
    ahora = time.time() if ahora is None else ahora
    for it in premio.get('items') or ():
        d = dict(id=int(it['id']), cantidad=int(it.get('cantidad', 1)))
        if it.get('dias'):
            d['caduca_en'] = ahora + float(it['dias']) * 86400
        items.append(d)
    if not ag and not items:
        return None
    return dict(exp=0, oro=0, creditos=0, skill_exp=0, skill_exp_ppm=0, items=items, angel_gold=ag,
                stage=STAGE_PREMIO, skill_rewards=[], pet_defense=rango_final)


def cerrar(n, ahora=None):
    """Reparte los premios de la temporada n (una sola vez). Devuelve [(nombre, rango, plan)] de los premiados."""
    import cuentas
    with _LOCK:
        con = _con()
        try:
            if con.execute('SELECT 1 FROM temporadas_cerradas WHERE temporada=?', (int(n),)).fetchone():
                return []
            mejores = _mejores(con, n)
            premiados = []
            for i, (cid, usuario, nombre, _nv, puntos, _ol, _sg, _rs) in enumerate(mejores):
                r = rango(puntos, i + 1)
                plan = plan_de(r, ahora)
                if plan and usuario:
                    plan['usuario'] = usuario
                    premiados.append((cid, nombre, r, plan))
            with cuentas._LOCK:
                cc = cuentas._get_conn()
                try:
                    cc.execute('CREATE TABLE IF NOT EXISTS competiciones_premios '
                               '(ronda TEXT, char_id INTEGER, estado TEXT, plan TEXT, PRIMARY KEY(ronda,char_id))')
                    for cid, _nombre, _r, plan in premiados:
                        cc.execute('INSERT OR IGNORE INTO competiciones_premios VALUES (?,?,?,?)',
                                   ('petdefense-T%d' % int(n), int(cid), 'pendiente', json.dumps(plan)))
                    cc.commit()
                finally:
                    cc.close()
            con.execute('INSERT INTO temporadas_cerradas VALUES (?,?,?)', (int(n), time.time(), len(premiados)))
            con.commit()
        finally:
            con.close()
    for _cid, nombre, r, plan in premiados:
        log.info('Pet Defense: temporada %d, %s queda %s: %s AG, %d objetos', n, nombre, r, plan.get('angel_gold'),
                 len(plan.get('items') or ()))
    return [(nombre, r, plan) for _cid, nombre, r, plan in premiados]


_ULTIMO = [0, 0.0]          # (temporada ya revisada, cuando)


def cron(ahora=None):
    """Desde el reloj de competiciones (cada segundo): al empezar una temporada, reparte las anteriores que no se
    hayan cerrado. Mira la base de datos como mucho una vez por minuto."""
    ahora = time.time() if ahora is None else ahora
    n = temporada(ahora)[0]
    if _ULTIMO[0] == n and ahora - _ULTIMO[1] < 60:
        return []
    _ULTIMO[0], _ULTIMO[1] = n, ahora
    hechas = []
    with _LOCK:
        con = _con()
        try:
            jugadas = [r[0] for r in con.execute('SELECT DISTINCT temporada FROM partidas WHERE temporada < ?', (n,))]
            cerradas = {r[0] for r in con.execute('SELECT temporada FROM temporadas_cerradas')}
        finally:
            con.close()
    for t in sorted(set(jugadas) - cerradas):
        hechas += cerrar(t, ahora)
    return hechas
