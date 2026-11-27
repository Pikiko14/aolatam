"""HONOR (26/11/2026): "honor y tienda PvP. Cada victoria en arena, guerra, duelo o caza da puntos de honor, que se
cambian en un NPC ... que salga toda la lista de fashion PD sin bonus y se compre con honor point".

* El Honor Point es un objeto apilable propio (cliente_local.ITEM_HONOR). Se gana en PvP (cantidades en
  plantillas/honor.json) y se gasta en Event Overview > Exchange > "Honor: ..." (seis tiendas: sombreros, trajes,
  guantes y botas, armas, alas y monturas; todo el fashion PD sin bonus, tools/tienda_honor.py).
* Donde se gana: duelos._cerrar (el ganador), cazador (la presa que sobrevive / el que la caza), competiciones.terminar
  (Angel Arena y Holy Battlefield), league_war.finish, moba_ranking.registrar, daily_events._finish (las PvP) y
  pvp_liga (una baja en el mundo, Totem War u Outpost).
* Contra el farmeo con otro personaje: en duelos y bajas sueltas hay tope diario y tope por rival; el duelo solo da
  honor con una apuesta minima; la baja suelta, si el muerto no es mucho mas bajo.
* Si el jugador no esta (o la mochila esta llena) queda pendiente en data/honor.db y se le da al conectar.
"""
import datetime as dt
import json
import logging
import pathlib
import sqlite3

log = logging.getLogger('honor')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'honor.json'
DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'honor.db'
_HOY = {}          # (dia, cid, clave) -> veces


def cfg():
    return json.loads(RUTA.read_text('utf-8'))


def item():
    import cliente_local
    return cliente_local.ITEM_HONOR


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute('create table if not exists pendiente (id integer primary key autoincrement, cid int, puntos int, '
                'texto text)')
    con.execute('create table if not exists total (cid int primary key, puntos int)')
    return con


def _sumar_total(cid, n):
    con = _db()
    try:
        con.execute('insert into total values (?,?) on conflict(cid) do update set puntos=puntos+excluded.puntos',
                    (int(cid), int(n)))
        con.commit()
    finally:
        con.close()


def total(cid):
    """El honor ganado en total (para un ranking futuro)."""
    con = _db()
    try:
        r = con.execute('select puntos from total where cid=?', (int(cid),)).fetchone()
        return int(r[0]) if r else 0
    finally:
        con.close()


def _entregar(ses, n, texto):
    import app
    import sociales
    r = app._gm_dar_item(ses, item(), n)
    if not str(r).startswith('dado'):
        return False
    sociales.aviso(ses, '[Honor] +%d Honor Point%s: %s. Spend them in Event Overview > Exchange.'
                   % (n, '' if n == 1 else 's', texto))
    return True


def dar(quien, n, texto):
    """quien: sesion o char_id. Da n Honor Points (o los deja pendientes)."""
    import sociales
    n = int(n or 0)
    if n <= 0:
        return 0
    ses = quien if hasattr(quien, 'personaje') else sociales.por_cid(int(quien))
    cid = int(ses.personaje.char_id) if ses is not None else int(quien)
    try:
        _sumar_total(cid, n)
        if ses is None or not _entregar(ses, n, texto):
            con = _db()
            try:
                con.execute('insert into pendiente (cid, puntos, texto) values (?,?,?)', (cid, n, texto))
                con.commit()
            finally:
                con.close()
            if ses is not None:
                sociales.aviso(ses, '[Honor] Your backpack is full: %d Honor Points will be given next login.' % n)
    except Exception:
        log.exception('honor: dar %s a %s', n, cid)
    return n


def al_conectar(ses):
    cid = int(ses.personaje.char_id)
    con = _db()
    try:
        filas = con.execute('select puntos, texto from pendiente where cid=?', (cid,)).fetchall()
        con.execute('delete from pendiente where cid=?', (cid,))
        con.commit()
    finally:
        con.close()
    resto = []
    for n, texto in filas:
        if not _entregar(ses, int(n), texto):
            resto.append((n, texto))
    if resto:
        con = _db()
        try:
            con.executemany('insert into pendiente (cid, puntos, texto) values (?,?,?)',
                            [(cid, n, t) for n, t in resto])
            con.commit()
        finally:
            con.close()


def _cupo(cid, clave, tope, ahora=None):
    """True (y lo cuenta) si hoy aun no llego al tope."""
    dia = (ahora or dt.datetime.now()).date().isoformat()
    for k in [k for k in _HOY if k[0] != dia]:
        del _HOY[k]
    k = (dia, int(cid), clave)
    if _HOY.get(k, 0) >= int(tope):
        return False
    _HOY[k] = _HOY.get(k, 0) + 1
    return True


# ---------------------------------------------------------------------------------------------- las fuentes
def duelo(ganador_cid, perdedor_cid, oro):
    c = cfg()['duelo']
    if int(oro) < int(c['oro_min']):
        return 0
    if not _cupo(ganador_cid, 'duelo', c['tope_dia']) or not _cupo(ganador_cid, 'duelo-%d' % int(perdedor_cid),
                                                                  c['tope_rival_dia']):
        return 0
    return dar(ganador_cid, c['victoria'], 'duel won')


def caza(ses, presa_sobrevive):
    c = cfg()['caza']
    return dar(ses, c['presa_sobrevive'] if presa_sobrevive else c['cazador'],
               'survived the hunt' if presa_sobrevive else 'caught the prey')


def baja(ses, otro):
    """Una baja suelta (mundo, Totem War, Outpost)."""
    c = cfg()['baja']
    p, q = ses.personaje, otro.personaje
    if int(q.nivel) < int(p.nivel) - int(c['dif_nivel']):
        return 0
    cid = int(p.char_id)
    if not _cupo(cid, 'baja', c['tope_dia']) or not _cupo(cid, 'baja-%d' % int(q.char_id), c['tope_rival_dia']):
        return 0
    return dar(ses, c['puntos'], 'defeated %s' % q.nombre)


def competicion(r):
    """Angel Arena (campeon / resto con puesto) y Holy Battlefield (ganador / perdedor / empate)."""
    import competicion_premios
    c = cfg()
    for cid, m in r['miembros'].items():
        try:
            _plan, estado = competicion_premios.seleccionar(r, cid, m)
        except Exception:
            continue
        if estado in ('prueba', 'cancelado', 'observador', 'sin_competencia'):
            continue
        if int(r['stage']) == 112:
            if not m.get('presente_al_cierre', True):
                continue
            res = ('empate' if not r.get('ganador') else 'ganador' if m.get('equipo') == r['ganador'] else 'perdedor')
            dar(cid, c['holy'][res], 'Holy Battlefield (%s)' % {'ganador': 'victory', 'perdedor': 'defeat',
                                                                  'empate': 'draw'}[res])
        else:
            clas = r.get('clasificacion') or []
            if cid not in clas:
                continue
            res = 'campeon' if clas.index(cid) == 0 else 'participa'
            dar(cid, c['arena'][res], 'Angel Arena (%s)' % ('champion' if res == 'campeon' else 'rank %d'
                                                            % (clas.index(cid) + 1)))


def guerra(char_id, resultado):
    """League War: 'win' / 'loss' / 'draw'."""
    return dar(char_id, cfg()['league_war'].get(resultado, 0), 'League War (%s)' % resultado)


def moba(ses, gano):
    return dar(ses, cfg()['moba']['victoria' if gano else 'derrota'], 'MOBA %s' % ('victory' if gano else 'match'))


def daily(char_id, gano, nombre):
    return dar(char_id, cfg()['daily_pvp']['victoria' if gano else 'derrota'],
               '%s (%s)' % (nombre, 'victory' if gano else 'played'))
