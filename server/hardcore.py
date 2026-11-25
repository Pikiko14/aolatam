"""El modo hardcore por temporada (25/11/2026): "personajes aparte que, si mueren, pierden todo lo de esa temporada;
ranking propio y los que sobreviven reciben premios cosmeticos exclusivos" (plantillas/mecanicas.json "hardcore").

* La temporada es el mes. Un personaje de nivel <= 'nivel_max' se apunta desde la pestana Hardcore de Challenges: se
  guarda con que nivel y oro empieza. Mientras sigue vivo gana un 'exp_extra' % mas de EXP (app._premiar) y lleva el
  icono "Hardcore" en la barra de buffs (magic.xml 'magia').
* Solo cuentan las muertes PvE (app._quitar_buffs_al_morir con pve=True: monstruos, jefes, raid, Santa Clausula).
  PvP, duelos, El cazador cazado y el Death Notice no cuentan ("que solo cuenten las muertes de pve", 25/11/2026).
  Si muere asi pierde todo lo de la temporada: vuelve al nivel y como mucho al oro con que empezo, y
  queda fuera (caido) hasta la temporada siguiente. Cartel a todos.
* Ranking de la temporada: por nivel alcanzado (los caidos, con su nivel al caer, debajo de los vivos).
* Al cambiar de mes, los que siguen vivos reciben 'premios' (items del juego) y se anuncian.
* Quien llega a 'nivel_premio' (60) sin haber muerto ni una vez gana 'ag_premio' (50.000) de Angel Gold del item
  mall, una vez por temporada (al_subir; columna premio_nivel).
"""
import datetime as dt
import json
import logging
import pathlib
import sqlite3
import struct
import time

import sociales

log = logging.getLogger('hardcore')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'mecanicas.json'
DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'hardcore.db'


def cfg():
    return json.loads(RUTA.read_text('utf-8'))['hardcore']


def temporada(ahora=None):
    return (ahora or dt.datetime.now()).strftime('%Y-%m')


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute('create table if not exists hc (temporada text, cid int, nombre text, nivel_ini int, oro_ini int, '
                'estado text, nivel int, inicio real, premiado int default 0, primary key (temporada, cid))')
    if 'premio_nivel' not in [r[1] for r in con.execute('pragma table_info(hc)')]:
        con.execute('alter table hc add column premio_nivel int default 0')
    return con


def ficha(cid, ahora=None):
    con = _db()
    try:
        f = con.execute('select nombre, nivel_ini, oro_ini, estado, nivel from hc where temporada=? and cid=?',
                        (temporada(ahora), int(cid))).fetchone()
    finally:
        con.close()
    return dict(zip(('nombre', 'nivel_ini', 'oro_ini', 'estado', 'nivel'), f)) if f else None


def vivo(ses, ahora=None):
    """Si es un hardcore vivo de esta temporada (guardado en la sesion: se mira en cada monstruo que mata)."""
    p = getattr(ses, 'personaje', None)
    if p is None:
        return False
    t = temporada(ahora)
    c = getattr(ses, '_hc', None)
    if c is None or c[0] != t:
        f = ficha(p.char_id, ahora)
        c = ses._hc = (t, bool(f and f['estado'] == 'vivo'))
    return c[1]


def _olvidar(ses):
    try:
        ses._hc = None
    except Exception:
        pass


def mult_exp(ses):
    return 1.0 + float(cfg()['exp_extra']) / 100.0 if vivo(ses) else 1.0


def magias_propias():
    c = cfg()
    return {int(c['magia']): {'編號': str(c['magia']), '介面圖號': str(c['icono']), '名稱': 'Hardcore',
                              '對象': '自己', '高權位': str(c['magia']), '低權位': '1', '後置時間': '500',
                              '持續時間': '86400', '公式': '2',
                              '說明': 'Hardcore season: +%d%% EXP. If you die you lose everything from this season.'
                                     % int(c['exp_extra']), '死亡不消失': '是', '同類無法使用': '是'}}


def _icono(ses, activo):
    try:
        ses.enviar(struct.pack('<HIBBII', 0x001D, ses.personaje.entity_id, 1, 4, int(cfg()['magia']),
                               86400000 if activo else 0))
    except Exception:
        pass


def apuntar(ses, ahora=None):
    p = ses.personaje
    f = ficha(p.char_id, ahora)
    if f and f['estado'] == 'vivo':
        return 'You are already in this Hardcore season.'
    if f:
        return 'You fell this season. Try again next month!'
    if int(p.nivel) > int(cfg()['nivel_max']):
        return 'Only characters up to level %d can start Hardcore. Make a new character!' % int(cfg()['nivel_max'])
    con = _db()
    try:
        con.execute("insert into hc (temporada, cid, nombre, nivel_ini, oro_ini, estado, nivel, inicio) values "
                    "(?,?,?,?,?, 'vivo', ?, ?)", (temporada(ahora), int(p.char_id), p.nombre, int(p.nivel),
                                                  sociales.oro(ses), int(p.nivel), time.time()))
        con.commit()
    finally:
        con.close()
    _olvidar(ses)
    _icono(ses, True)
    sociales.cartel('[Hardcore] %s started the Hardcore season. Good luck!' % p.nombre)
    return 'Hardcore started! +%d%% EXP. Do not die...' % int(cfg()['exp_extra'])


def al_subir(ses, ahora=None):
    """Al subir de nivel: el nivel alcanzado para el ranking y, al llegar a 'nivel_premio' vivo, 'ag_premio' de Angel
    Gold del item mall (una vez). Devuelve el Angel Gold dado."""
    p = getattr(ses, 'personaje', None)
    if p is None or not vivo(ses, ahora):
        return 0
    c = cfg()
    t = temporada(ahora)
    oro = 0
    con = _db()
    try:
        con.execute('update hc set nivel=max(nivel, ?) where temporada=? and cid=?', (int(p.nivel), t, int(p.char_id)))
        if int(p.nivel) >= int(c.get('nivel_premio', 60)):
            cur = con.execute("update hc set premio_nivel=1 where temporada=? and cid=? and estado='vivo' and "
                              "coalesce(premio_nivel, 0)=0", (t, int(p.char_id)))
            if cur.rowcount:
                oro = int(c.get('ag_premio', 50000))
        con.commit()
    finally:
        con.close()
    if oro:
        try:
            import item_mall
            item_mall.sumar_ag(ses.usuario, oro)
        except Exception:
            log.exception('hardcore: Angel Gold del premio de nivel')
        sociales.cartel('[Hardcore] %s reached level %d without dying and wins %s Angel Gold!'
                        % (p.nombre, int(c.get('nivel_premio', 60)), format(oro, ',')))
        sociales.aviso(ses, '[Hardcore] Level %d without dying: +%s Angel Gold for the Item Mall!'
                       % (int(c.get('nivel_premio', 60)), format(oro, ',')))
    return oro


def al_morir(ses, ahora=None):
    """Muere un hardcore vivo: lo pierde todo de la temporada."""
    p = getattr(ses, 'personaje', None)
    if p is None:
        return False
    f = ficha(p.char_id, ahora)
    if not f or f['estado'] != 'vivo':
        return False
    nivel = int(p.nivel)
    con = _db()
    try:
        con.execute("update hc set estado='caido', nivel=max(nivel, ?) where temporada=? and cid=?",
                    (nivel, temporada(ahora), int(p.char_id)))
        con.commit()
    finally:
        con.close()
    _olvidar(ses)
    _icono(ses, False)
    try:
        if nivel > int(f['nivel_ini']):
            import gm
            gm.poner_nivel(ses, int(f['nivel_ini']))
        if sociales.oro(ses) > int(f['oro_ini']):
            sociales.cambiar_oro(ses, int(f['oro_ini']) - sociales.oro(ses))
    except Exception:
        log.exception('hardcore: quitar lo de la temporada')
    sociales.cartel('[Hardcore] %s fell at level %d and lost the whole season!' % (p.nombre, nivel))
    sociales.aviso(ses, '[Hardcore] You died. Your season is over: back to level %d.' % int(f['nivel_ini']))
    return True


def ranking(ahora=None, top=10):
    con = _db()
    try:
        filas = con.execute("select nombre, nivel, estado from hc where temporada=? "
                            "order by (estado='vivo') desc, nivel desc, inicio limit ?",
                            (temporada(ahora), int(top))).fetchall()
    finally:
        con.close()
    return filas


def al_conectar(ses):
    if vivo(ses):
        _icono(ses, True)


def cerrar_temporada(t):
    """Premios a los vivos de la temporada t (una vez)."""
    import app
    con = _db()
    try:
        filas = con.execute("select cid, nombre from hc where temporada=? and estado='vivo' and premiado=0",
                            (t,)).fetchall()
        con.execute("update hc set premiado=1 where temporada=? and estado='vivo'", (t,))
        con.commit()
    finally:
        con.close()
    if not filas:
        return []
    import contratos
    for cid, nombre in filas:
        s = sociales.por_cid(cid)
        for it in cfg()['premios']:
            if s is not None:
                try:
                    app._gm_dar_item(s, int(it), 1)
                except Exception:
                    log.exception('hardcore: premio')
            else:
                contratos._dar(cid, item=int(it), cantidad=1, texto='Hardcore survivor reward.')
        if s is not None:
            sociales.aviso(s, '[Hardcore] You survived the season! Reward: %s.' % cfg()['texto_premio'])
    sociales.cartel('[Hardcore] Season %s is over. Survivors: %s!' % (t, ', '.join(n for _c, n in filas[:10])))
    return [n for _c, n in filas]


_TEMPORADA = []


def tick(ahora=None):
    """Al arrancar y al cambiar de mes: cierra las temporadas pasadas que tengan vivos sin premiar."""
    t = temporada(ahora)
    if _TEMPORADA and _TEMPORADA[0] == t:
        return
    _TEMPORADA[:] = [t]
    con = _db()
    try:
        pasadas = [r[0] for r in con.execute("select distinct temporada from hc where temporada < ? and "
                                             "estado='vivo' and premiado=0", (t,))]
    finally:
        con.close()
    for vieja in pasadas:
        cerrar_temporada(vieja)
