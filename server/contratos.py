"""Contratos de cazarrecompensas (25/11/2026): "un jugador pone oro como recompensa para que otro le traiga un objeto o
le mate un jefe; un tablon de encargos entre jugadores" (plantillas/mecanicas.json "contratos").

* Publicar (pestana Contracts de la ventana Challenges, server/mecanicas_ui.py): objeto (n unidades) o jefe, buscado
  por nombre; el oro de la recompensa sale al publicar (queda en deposito). Como mucho 'max_por_jugador' abiertos.
* Objeto: cualquiera que lo tenga pulsa Deliver: se le quitan las unidades de la mochila y cobra la recompensa menos
  la 'comision' %; las unidades van al que lo pidio (si no esta conectado, al entrar: pendientes).
* Jefe: el primero que mata ese monstruo (el que lo remata, o el que mas le pego si es otro) cobra.
* El que lo publico lo puede cancelar (vuelve el oro). A las 'duracion_h' horas vence y vuelve el oro.
"""
import json
import logging
import pathlib
import sqlite3
import time

import sociales

log = logging.getLogger('contratos')

DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'contratos.db'
CONTENT = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'mecanicas.json'
_NOMBRES = {}


def cfg():
    return json.loads(RUTA.read_text('utf-8'))['contratos']


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute('create table if not exists contrato (id integer primary key autoincrement, cid int, nombre text, '
                'tipo text, objeto int, cantidad int, oro int, creado real, estado text, quien text)')
    con.execute('create table if not exists pendiente (id integer primary key autoincrement, cid int, oro int, '
                'item int, cantidad int, texto text)')
    return con


# ---------------------------------------------------------------- busqueda por nombre
def _indice(tipo):
    if tipo not in _NOMBRES:
        filas = []
        try:
            con = sqlite3.connect(str(CONTENT))
            con.text_factory = str
            if tipo == 'item':
                filas = [(int(i), str(n)) for i, n in con.execute('select id, 基本名稱 from item') if n]
            else:
                import combate
                filas = [(int(i), str(n)) for i, n, *_ in con.execute('select id, name, level from monster')
                         if n and combate.es_jefe(int(i))]
            con.close()
        except Exception:
            log.exception('contratos: indice de %s', tipo)
        vistos, unicos = set(), []
        for i, n in filas:
            k = n.strip().lower()
            if k and k not in vistos and all(ord(ch) < 128 for ch in n):
                vistos.add(k)
                unicos.append((i, n.strip()))
        _NOMBRES[tipo] = unicos
    return _NOMBRES[tipo]


def buscar(tipo, texto, tope=30):
    """[(id, nombre)] que contienen el texto (primero los que empiezan por el)."""
    t = str(texto or '').strip().lower()
    if len(t) < 2:
        return []
    filas = _indice('item' if tipo == 'item' else 'jefe')
    empieza = [f for f in filas if f[1].lower().startswith(t)]
    contiene = [f for f in filas if t in f[1].lower() and f not in empieza]
    return (sorted(empieza, key=lambda f: len(f[1])) + sorted(contiene, key=lambda f: len(f[1])))[:tope]


def nombre_de(tipo, objeto):
    for i, n in _indice('item' if tipo == 'item' else 'jefe'):
        if i == int(objeto):
            return n
    return '#%d' % int(objeto)


# ---------------------------------------------------------------- el tablon
def abiertos():
    con = _db()
    try:
        filas = con.execute("select id, cid, nombre, tipo, objeto, cantidad, oro, creado from contrato "
                            "where estado='abierto' order by id desc").fetchall()
    finally:
        con.close()
    return [dict(zip(('id', 'cid', 'nombre', 'tipo', 'objeto', 'cantidad', 'oro', 'creado'), f)) for f in filas]


def texto_contrato(c):
    if c['tipo'] == 'item':
        que = 'Bring %d x %s' % (c['cantidad'], nombre_de('item', c['objeto']))
    else:
        que = 'Defeat %s' % nombre_de('jefe', c['objeto'])
    return '%s - %s Gold (by %s)' % (que, format(int(c['oro']), ','), c['nombre'])


def publicar(ses, tipo, objeto, cantidad, oro, ahora=None):
    c = cfg()
    p = ses.personaje
    if tipo not in ('item', 'jefe'):
        return 'Choose Item or Boss.'
    oro, cantidad = int(oro), max(1, int(cantidad or 1))
    if oro < int(c['oro_min']) or oro > int(c['oro_max']):
        return 'The reward must be between %s and %s Gold.' % (format(int(c['oro_min']), ','), format(int(c['oro_max']), ','))
    if tipo == 'item' and cantidad > int(c['cantidad_max']):
        return 'At most %d units per contract.' % int(c['cantidad_max'])
    if not any(i == int(objeto) for i, _n in _indice('item' if tipo == 'item' else 'jefe')):
        return 'Find the item or boss first.'
    mios = [x for x in abiertos() if x['cid'] == int(p.char_id)]
    if len(mios) >= int(c['max_por_jugador']):
        return 'You already have %d open contracts.' % len(mios)
    if sociales.oro(ses) < oro:
        return 'You do not have %s Gold.' % format(oro, ',')
    sociales.cambiar_oro(ses, -oro)
    con = _db()
    try:
        con.execute("insert into contrato (cid, nombre, tipo, objeto, cantidad, oro, creado, estado) values "
                    "(?,?,?,?,?,?,?, 'abierto')", (int(p.char_id), p.nombre, tipo, int(objeto),
                                                   cantidad if tipo == 'item' else 1, oro, ahora or time.time()))
        con.commit()
    finally:
        con.close()
    texto = texto_contrato({'tipo': tipo, 'objeto': objeto, 'cantidad': cantidad, 'oro': oro, 'nombre': p.nombre})
    sociales.cartel('[Contracts] New contract: ' + texto)
    return 'Contract posted.'


def _cerrar(cid_contrato, estado, quien=''):
    con = _db()
    try:
        n = con.execute("update contrato set estado=?, quien=? where id=? and estado='abierto'",
                        (estado, quien, int(cid_contrato))).rowcount
        con.commit()
    finally:
        con.close()
    return n == 1


def _dar(cid, oro=0, item=0, cantidad=0, texto=''):
    """Oro y/o unidades a un personaje: ya si esta conectado; si no, al entrar."""
    s = sociales.por_cid(cid)
    if s is not None:
        if oro:
            sociales.cambiar_oro(s, oro)
        if item and cantidad:
            try:
                import app
                app._gm_dar_item(s, int(item), int(cantidad))
            except Exception:
                log.exception('contratos: dar unidades')
        if texto:
            sociales.aviso(s, '[Contracts] ' + texto)
        return True
    con = _db()
    try:
        con.execute('insert into pendiente (cid, oro, item, cantidad, texto) values (?,?,?,?,?)',
                    (int(cid), int(oro), int(item), int(cantidad), texto))
        con.commit()
    finally:
        con.close()
    return False


def _pago(oro):
    return int(oro * (100 - float(cfg()['comision'])) // 100)


def _contar(ses, item):
    import app
    bolsa = getattr(ses, 'inventario', {}) or {}
    return sum(app._cant_de(ses, r) for r in app._ranuras_bolsa(bolsa) if int(bolsa.get(r, 0)) == int(item))


def entregar(ses, id_contrato):
    import app
    c = next((x for x in abiertos() if x['id'] == int(id_contrato)), None)
    if c is None or c['tipo'] != 'item':
        return 'That contract is no longer open.'
    if c['cid'] == int(ses.personaje.char_id):
        return 'You cannot deliver your own contract.'
    if _contar(ses, c['objeto']) < c['cantidad']:
        return 'You need %d x %s in your backpack.' % (c['cantidad'], nombre_de('item', c['objeto']))
    if not _cerrar(c['id'], 'hecho', ses.personaje.nombre):
        return 'Someone was faster.'
    tocadas = app._consumir_item_total(ses, c['objeto'], c['cantidad'])
    try:
        ses.enviar(*app._refrescar(ses, tocadas))
    except Exception:
        log.debug('contratos: refrescar mochila', exc_info=True)
    pago = _pago(c['oro'])
    sociales.cambiar_oro(ses, pago)
    _dar(c['cid'], item=c['objeto'], cantidad=c['cantidad'],
         texto='%s delivered your contract: %d x %s.' % (ses.personaje.nombre, c['cantidad'],
                                                       nombre_de('item', c['objeto'])))
    return 'Delivered! You get %s Gold.' % format(pago, ',')


def cancelar(ses, id_contrato):
    c = next((x for x in abiertos() if x['id'] == int(id_contrato)), None)
    if c is None or c['cid'] != int(ses.personaje.char_id):
        return 'That contract is not yours or is closed.'
    if not _cerrar(c['id'], 'cancelado'):
        return 'That contract is already closed.'
    sociales.cambiar_oro(ses, c['oro'])
    return 'Contract cancelled: your %s Gold are back.' % format(int(c['oro']), ',')


def al_matar(ses, m):
    """Un monstruo cayo: los contratos de ese jefe los cobra quien lo remato (o quien mas le pego)."""
    npc = int(getattr(m, 'npc_type', 0) or 0)
    lista = [c for c in abiertos() if c['tipo'] == 'jefe' and c['objeto'] == npc]
    if not lista:
        return
    cazador = ses
    dano = getattr(m, 'dano_por', None) or {}
    for c in lista:
        quien = cazador
        if int(quien.personaje.char_id) == c['cid'] and dano:
            otros = [(d, k) for k, d in dano.items() if int(k) != c['cid']]
            quien = sociales.por_cid(max(otros)[1]) if otros else None
        if quien is None or not _cerrar(c['id'], 'hecho', quien.personaje.nombre):
            continue
        pago = _pago(c['oro'])
        sociales.cambiar_oro(quien, pago)
        sociales.aviso(quien, '[Contracts] You completed %s\'s contract: %s Gold!' % (c['nombre'], format(pago, ',')))
        _dar(c['cid'], texto='%s defeated %s for your contract.' % (quien.personaje.nombre, nombre_de('jefe', npc)))


def al_conectar(ses):
    cid = int(ses.personaje.char_id)
    con = _db()
    try:
        filas = con.execute('select id, oro, item, cantidad, texto from pendiente where cid=?', (cid,)).fetchall()
        con.execute('delete from pendiente where cid=?', (cid,))
        con.commit()
    finally:
        con.close()
    for _i, oro, item, cantidad, texto in filas:
        _dar(cid, oro, item, cantidad, texto)


def tick(ahora=None):
    ahora = ahora or time.time()
    limite = float(cfg()['duracion_h']) * 3600
    for c in abiertos():
        if ahora - c['creado'] >= limite and _cerrar(c['id'], 'vencido'):
            _dar(c['cid'], oro=c['oro'], texto='Your contract expired: %s Gold are back.' % format(int(c['oro']), ','))
