"""Angel MOBA, fase 4 (23/11/2026): premios por partida, puntos de temporada, rangos y premios de temporada. Como el
de Pet Defense (pet_defense_ranking.py), con su propia base de datos (data/moba.db).

* CADA PARTIDA QUE ACABA con ganador (cae un nucleo) se guarda para los heroes que siguen en ella: clase, equipo, si
  gano, bajas y muertes. Puntos de temporada: 'puntos.victoria' o 'puntos.derrota' + 'puntos.por_baja' x bajas. Y al
  momento, por la cola de competicion_premios, 'premio_partida' Angel Gold (victoria o derrota).
* EL RANKING de la temporada: la SUMA de puntos de cada personaje (a igualdad, mas victorias). Rangos por puntos
  (Bronze, Silver, Gold), Angel en los 'angel_top' primeros y Champion el 1o (los dos con al menos los de Bronze).
* AL EMPEZAR UNA TEMPORADA (cron, desde el reloj de competiciones) se reparten los premios de la anterior por rango,
  una sola vez.
"""
import datetime as dt
import json
import logging
import pathlib
import sqlite3
import threading
import time

log = logging.getLogger('moba')

DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'moba.db'
STAGE_PREMIO = 918
_LOCK = threading.RLock()


def _cfg():
    import moba
    return moba.config().get('ranking') or {}


def _con():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('CREATE TABLE IF NOT EXISTS partidas (id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT, '
                'temporada INTEGER, char_id INTEGER, usuario TEXT, nombre TEXT, clase TEXT, equipo INTEGER, '
                'gano INTEGER, bajas INTEGER, muertes INTEGER, nivel INTEGER, puntos INTEGER, fecha REAL)')
    con.execute('CREATE INDEX IF NOT EXISTS partidas_temporada ON partidas (temporada, char_id)')
    con.execute('CREATE TABLE IF NOT EXISTS temporadas_cerradas (temporada INTEGER PRIMARY KEY, fecha REAL, '
                'premiados INTEGER)')
    return con


def temporada(ahora=None):
    """(numero, inicio, fin) de la temporada de `ahora`. Antes de la primera, la 1."""
    t = _cfg().get('temporada') or {}
    dias = max(1, int(t.get('dias', 14)))
    inicio = dt.datetime.fromisoformat(str(t.get('inicio', '2026-11-23'))).timestamp()
    ahora = time.time() if ahora is None else ahora
    n = max(0, int((ahora - inicio) // (dias * 86400)))
    desde = inicio + n * dias * 86400
    return n + 1, desde, desde + dias * 86400


def puntos_de(gano, bajas):
    p = _cfg().get('puntos') or {}
    return int(p.get('victoria' if gano else 'derrota', 30 if gano else 10)) + int(p.get('por_baja', 3)) * int(bajas)


def _encolar(ronda, char_id, plan):
    import cuentas
    with cuentas._LOCK:
        cc = cuentas._get_conn()
        try:
            cc.execute('CREATE TABLE IF NOT EXISTS competiciones_premios '
                       '(ronda TEXT, char_id INTEGER, estado TEXT, plan TEXT, PRIMARY KEY(ronda,char_id))')
            cc.execute('INSERT OR IGNORE INTO competiciones_premios VALUES (?,?,?,?)',
                       (ronda, int(char_id), 'pendiente', json.dumps(plan)))
            cc.commit()
        finally:
            cc.close()


def _plan(ag, items=(), ahora=None, **extra):
    ahora = time.time() if ahora is None else ahora
    its = []
    for it in items or ():
        d = dict(id=int(it['id']), cantidad=int(it.get('cantidad', 1)))
        if it.get('dias'):
            d['caduca_en'] = ahora + float(it['dias']) * 86400
        its.append(d)
    plan = dict(exp=0, oro=0, creditos=0, skill_exp=0, skill_exp_ppm=0, items=its, angel_gold=int(ag),
                stage=STAGE_PREMIO, skill_rewards=[])
    plan.update(extra)
    return plan


def registrar(pa, ganador, ahora=None):
    """Guarda la partida de cada heroe que sigue en ella y le encola su premio. Devuelve {sesion: (puntos, AG)}.
    Lo llama moba.terminar con ganador, ANTES de que los heroes se vayan."""
    ahora = time.time() if ahora is None else ahora
    n = temporada(ahora)[0]
    premio = _cfg().get('premio_partida') or {}
    out = {}
    filas = []
    for ses, h in list(pa.heroes.items()):
        p = getattr(ses, 'personaje', None)
        if p is None or getattr(ses, 'cerrada', False):
            continue
        gano = int(h.equipo) == int(ganador)
        pts = puntos_de(gano, h.bajas)
        ag = int(premio.get('victoria' if gano else 'derrota', 0))
        cid = int(getattr(p, 'char_id', 0) or 0)
        usuario = str(getattr(ses, 'usuario', '') or '')
        filas.append((pa.id, n, cid, usuario, str(getattr(p, 'nombre', '?')), h.clave, int(h.equipo), int(gano),
                      int(h.bajas), int(h.muertes), int(h.nivel), pts, ahora))
        if ag > 0 and usuario:
            try:
                _encolar('moba-%s' % pa.id, cid, _plan(ag, ahora=ahora, usuario=usuario, moba='partida'))
            except Exception:
                log.exception('MOBA: premio de partida')
                ag = 0
        out[ses] = (pts, ag)
        try:
            import misiones_diarias
            misiones_diarias.sumar(ses, 'moba_jugar')
            if gano:
                misiones_diarias.sumar(ses, 'moba_ganar')
        except Exception:
            log.exception('MOBA: misiones diarias')
    with _LOCK:
        con = _con()
        try:
            con.executemany('INSERT INTO partidas (partida, temporada, char_id, usuario, nombre, clase, equipo, gano, '
                            'bajas, muertes, nivel, puntos, fecha) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', filas)
            con.commit()
        finally:
            con.close()
    log.info('MOBA %s: guardada (%d heroes, gana %s)', pa.id, len(filas), ganador)
    return out


def _tabla(con, n):
    """[(char_id, usuario, nombre, puntos, victorias, partidas, bajas)] de la temporada n, ordenada."""
    return [tuple(f) for f in con.execute(
        'SELECT char_id, MAX(usuario), MAX(nombre), SUM(puntos), SUM(gano), COUNT(*), SUM(bajas) FROM partidas '
        'WHERE temporada=? GROUP BY char_id ORDER BY SUM(puntos) DESC, SUM(gano) DESC, MIN(id) ASC', (int(n),))]


def ranking(n=None, top=None):
    n = temporada()[0] if n is None else n
    top = int(_cfg().get('top', 10)) if top is None else top
    with _LOCK:
        con = _con()
        try:
            return _tabla(con, n)[:top]
        finally:
            con.close()


def mi_marca(char_id, n=None):
    n = temporada()[0] if n is None else n
    with _LOCK:
        con = _con()
        try:
            for i, f in enumerate(_tabla(con, n)):
                if f[0] == int(char_id):
                    return i + 1, f
        finally:
            con.close()
    return None, None


def rango(puntos, puesto):
    r = _cfg().get('rangos') or {}
    bronce = int(r.get('Bronze', 100))
    if puesto == 1 and puntos >= bronce:
        return 'Champion'
    if puesto and puesto <= int(r.get('angel_top', 10)) and puntos >= bronce:
        return 'Angel'
    for nombre, defecto in (('Gold', 600), ('Silver', 300), ('Bronze', 100)):
        if puntos >= int(r.get(nombre, defecto)):
            return nombre
    return None


def cerrar(n, ahora=None):
    """Reparte los premios de la temporada n (una sola vez). Devuelve [(nombre, rango, plan)]."""
    premios = _cfg().get('premios') or {}
    with _LOCK:
        con = _con()
        try:
            if con.execute('SELECT 1 FROM temporadas_cerradas WHERE temporada=?', (int(n),)).fetchone():
                return []
            hechos = []
            for i, (cid, usuario, nombre, puntos, _v, _p, _b) in enumerate(_tabla(con, n)):
                r = rango(int(puntos or 0), i + 1)
                pr = premios.get(r or '') or {}
                if not usuario or not (pr.get('angel_gold') or pr.get('items')):
                    continue
                plan = _plan(pr.get('angel_gold', 0), pr.get('items'), ahora, usuario=usuario, moba=r)
                _encolar('moba-T%d' % int(n), cid, plan)
                hechos.append((nombre, r, plan))
            con.execute('INSERT INTO temporadas_cerradas VALUES (?,?,?)', (int(n), time.time(), len(hechos)))
            con.commit()
        finally:
            con.close()
    for nombre, r, plan in hechos:
        log.info('MOBA: temporada %d, %s queda %s: %s AG', n, nombre, r, plan.get('angel_gold'))
    return hechos


_ULTIMO = [0, 0.0]


def cron(ahora=None):
    """Desde el reloj de competiciones: al empezar una temporada, reparte las anteriores sin cerrar (mira la base de
    datos como mucho una vez por minuto)."""
    ahora = time.time() if ahora is None else ahora
    n = temporada(ahora)[0]
    if _ULTIMO[0] == n and ahora - _ULTIMO[1] < 60:
        return []
    _ULTIMO[0], _ULTIMO[1] = n, ahora
    with _LOCK:
        con = _con()
        try:
            jugadas = [r[0] for r in con.execute('SELECT DISTINCT temporada FROM partidas WHERE temporada < ?', (n,))]
            cerradas = {r[0] for r in con.execute('SELECT temporada FROM temporadas_cerradas')}
        finally:
            con.close()
    hechas = []
    for t in sorted(set(jugadas) - cerradas):
        hechas += cerrar(t, ahora)
    return hechas
