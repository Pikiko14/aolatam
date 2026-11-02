"""La Torre de Babel (02/11/2026): 60 pisos, un jefe base por piso del nivel del piso, solo o en party.

Pedido del usuario: "un evento de torre de babel, en el que salgan jefes desde lvl 1 hasta lvl 60, jefes base por
supuesto"; se abre desde una accion (el boton de la barra) donde sale el ranking y la seleccion del modo; cada
intento empieza de cero; premio por piso.

* LOS PISOS: plantillas/torre_babel.json (tools/generar_torre_babel.py): el jefe de cada piso y sus stats.
* EL MAPA: el 133 (en el cliente "年獸洞窟", sin uso aqui y sin castigo al morir), renombrado "Tower of Babel" en
  stage.xml (tools/parche_subasta_ventana.py) y dinamico en plantillas/instancias.json: cada jugador solo o cada
  party tiene su propia copia (eventos_mundo._clave_corrida).
* LA CORRIDA: iniciar() lleva al piso 1. Al cargar el mapa (al_entrar) sale el jefe del piso en su casilla
  (app._poner_generado, sin reaparicion); al morir (al_morir, desde app._procesar_muerte_monstruo) se anuncia el
  piso siguiente y su jefe sale a los PAUSA segundos. Cada 10 pisos, ademas del botin del jefe, todos los de la
  copia reciben tickets. En Party los jefes salen con todo x MULT_PARTY (vida, ataque y defensas).
* PARTY: solo el lider empieza la subida; al entrar el, a los demas de su party conectados les llega la
  solicitud (la ventana de la torre con TorreInvitacion) y con el boton de entrar se unen a su copia.
* EL FINAL: cuando el ultimo de la copia sale del mapa (muerte, portal, desconexion: antes_de_viajar), la corrida
  acaba y va al ranking (pisos superados y tiempo). Superar el 60 tambien la acaba y saca a todos. Quien vuelve a
  entrar al mapa sin una corrida viva sale al Angel Lyceum: cada intento empieza de cero.
* LA VENTANA: server/lua/torre.lua (canal 0x01A0), con el ranking de cada modo y el boton de entrar.
  c2s 0x002F [u8 169][u32 a][u32 b]: a = 1 abrir la ventana, 2 ver el ranking (b = modo), 3 entrar (b = modo).
"""
import json
import logging
import pathlib
import sqlite3
import threading
import time

import canal_lua

log = logging.getLogger('torre_babel')

STAGE = 133
ENTRADA = (118, 66)
CASILLA_JEFE = (110, 66)
PISOS_JSON = pathlib.Path(__file__).parent / 'plantillas' / 'torre_babel.json'
DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'torre_babel.db'
CMD_TORRE = 169
SOLO, PARTY = 0, 1
MODOS = ('Solo', 'Party')
PAUSA = 3.0                 # segundos entre la muerte de un jefe y la salida del siguiente
MULT_PARTY = 2.0            # en Party los jefes x2: "aumenta un x2 a los jefes en el modo party" (02/11/2026)
TICKETS = (20228, 20229, 20230, 20231)      # los de instancia_oscura: se canjean en Event Overview > Exchange
TOP = 10
SALIDA = (41, (173, 91))    # el Angel Lyceum (app.REVIVIR_LYCEUM)

SALUDO_LUA = ('function OnCommandTorre(dwID, dwCmdID, dwParam, pParam) '
              'game.netcommand2(%d, 1, 0) return 1 end' % CMD_TORRE)

_LOCK = threading.RLock()
_CORRIDAS = {}              # clave de la copia -> {'modo', 'piso', 'inicio', 'nombres', 'jefe'}
_PISOS = None


# ------------------------------------------------------------------ datos

def pisos():
    global _PISOS
    if _PISOS is None:
        _PISOS = json.loads(PISOS_JSON.read_text(encoding='utf-8'))['pisos']
    return _PISOS


def total_pisos() -> int:
    return len(pisos())


def _con():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('''CREATE TABLE IF NOT EXISTS corridas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, modo INTEGER NOT NULL, nombres TEXT NOT NULL,
        pisos INTEGER NOT NULL, segundos INTEGER NOT NULL, fecha REAL NOT NULL)''')
    return con


def guardar(modo, nombres, pisos_superados, segundos):
    with _LOCK:
        con = _con()
        try:
            con.execute('INSERT INTO corridas (modo, nombres, pisos, segundos, fecha) VALUES (?,?,?,?,?)',
                        (int(modo), ', '.join(sorted(nombres)), int(pisos_superados), int(segundos), time.time()))
            con.commit()
        finally:
            con.close()


def ranking(modo, top=TOP):
    """[[nombres, pisos, tiempo], ...]: mas pisos primero y, a igualdad, el mas rapido."""
    with _LOCK:
        con = _con()
        try:
            filas = con.execute('SELECT nombres, pisos, segundos FROM corridas WHERE modo = ? AND pisos > 0 '
                                'ORDER BY pisos DESC, segundos ASC, id ASC LIMIT ?', (int(modo), int(top))).fetchall()
        finally:
            con.close()
    return [[n, int(p), '%d:%02d' % divmod(int(s), 60)] for n, p, s in filas]


# ------------------------------------------------------------------ la corrida

def _clave(ses):
    import eventos_mundo
    return eventos_mundo._clave_corrida(ses)


def _en_la_copia(ses):
    """Las sesiones que estan en la misma copia de la torre que `ses` (ella incluida)."""
    import presencia
    vivas = list(presencia._vivas(presencia.clave_de_mapa(ses, STAGE)) or [])
    if ses not in vivas and getattr(getattr(ses, 'personaje', None), 'stage', None) == STAGE:
        vivas.append(ses)
    return vivas


def corrida(ses):
    return _CORRIDAS.get(_clave(ses))


def motivo_para_no_entrar(ses, modo):
    # Lo mismo que decide la copia (eventos_mundo._clave_corrida): un grupo que de verdad existe.
    en_party = _clave(ses)[0] == 'equipo'
    if modo == SOLO and en_party:
        return 'Solo mode: leave your party first.'
    if modo == PARTY and not en_party:
        return 'Party mode: you need to be in a party.'
    c = _CORRIDAS.get(_clave(ses))
    if c and c['modo'] != modo:
        return 'Your party is already climbing in %s mode.' % MODOS[c['modo']]
    if modo == PARTY and c is None and not _es_lider(ses):
        return 'Only the party leader can start the climb.'
    return None


def _es_lider(ses):
    import equipos
    return equipos.lider_de(ses) == int(getattr(ses.personaje, 'char_id', 0) or 0)


def invitar(ses_lider):
    """La solicitud a los de la party del lider que no estan ya en la torre: la ventana con la invitacion. Devuelve
    a cuantos se les mando."""
    import clases
    import equipos
    enviadas = 0
    for s in equipos.grupo_de(ses_lider):
        if s is ses_lider or getattr(getattr(s, 'personaje', None), 'stage', None) == STAGE:
            continue
        if getattr(s, 'canal_lua', 0):
            s.enviar(canal_lua.paquete(_lua()), canal_lua.llamar('TorreInvitacion', ses_lider.personaje.nombre,
                                                                  list(MODOS), total_pisos()), lista(PARTY))
        else:
            s.enviar(clases.aviso('%s invites you to the Tower of Babel: update your launcher to join.'
                                  % ses_lider.personaje.nombre, tipo=0))
        try:
            s.volcar()
        except Exception:
            pass
        enviadas += 1
    return enviadas


def iniciar(ses, addr, modo):
    """Entra a la torre: una corrida nueva en el piso 1, o se une a la de su party si ya esta en marcha."""
    import app
    motivo = motivo_para_no_entrar(ses, modo)
    if motivo:
        return motivo
    clave = _clave(ses)
    nueva = False
    with _LOCK:
        c = _CORRIDAS.get(clave)
        if c is None:
            c = _CORRIDAS[clave] = {'modo': modo, 'piso': 1, 'inicio': time.time(), 'nombres': set(), 'jefe': None}
            nueva = True
        c['nombres'].add(ses.personaje.nombre)
    log.info('%s entra a la Torre de Babel (%s, piso %d)', ses.personaje.nombre, MODOS[modo], c['piso'])
    app._viajar_por_portal(ses, addr, {'destino': STAGE, 'llegada': ENTRADA}, motivo='a la Torre de Babel')
    if nueva and modo == PARTY:
        log.info('Torre de Babel: %s invita a %d de su party', ses.personaje.nombre, invitar(ses))
    return None


def _jefe_vivo(ses, c):
    m = (getattr(ses, 'monstruos', None) or {}).get(c.get('jefe'))
    return m is not None and getattr(m, 'hp', 0) > 0


def _sacar(ses, addr='?'):
    import app
    import clases
    app._sincronizar_cambio_mapa(ses, SALIDA[0], *SALIDA[1])
    return clases


def al_entrar(ses, addr='?'):
    """El jugador termino de cargar un mapa. En la torre: sin corrida, fuera; con ella, el jefe del piso si no esta."""
    p = getattr(ses, 'personaje', None)
    if not p or getattr(p, 'stage', None) != STAGE:
        return
    c = corrida(ses)
    if c is None:
        import clases
        ses.enviar(clases.aviso('The Tower of Babel climb is over. Start again from the tower button.', tipo=0))
        _sacar(ses, addr)
        return
    c['nombres'].add(p.nombre)
    if not _jefe_vivo(ses, c):
        poner_jefe(ses, c)
    _cartel(ses, 'Tower of Babel - Floor %d / %d: %s' % (c['piso'], total_pisos(), pisos()[c['piso'] - 1]['nombre']))


def poner_jefe(ses, c):
    """Saca el jefe del piso de la corrida en la copia de `ses`."""
    import app
    datos = pisos()[c['piso'] - 1]
    eid = app._SIG_GENERADO[0]
    app._SIG_GENERADO[0] += 1
    m = app._poner_generado(ses, eid, int(datos['npc_type']), CASILLA_JEFE, 0)
    if m is None:
        log.warning('Torre de Babel: no se pudo sacar el jefe del piso %d (%s)', c['piso'], datos['npc_type'])
        return None
    k = MULT_PARTY if c['modo'] == PARTY else 1.0
    m.hp_max = m.hp = int(datos['hp'] * k)
    m.atk, m.defensa = int(datos['atk'] * k), int(datos['def'] * k)
    m.matk, m.mdef = int(datos['matk'] * k), int(datos['mdef'] * k)
    m.nivel = int(datos['nivel'])
    m.piso_torre = c['piso']
    c['jefe'] = eid
    ses.volcar()
    return m


def _cartel(ses, texto):
    import totem_war
    pk = totem_war.cartel_deslizante(texto)
    for s in _en_la_copia(ses):
        try:
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(pk)
            s.volcar()
        except Exception:
            pass


def _premio_cada_diez(ses, piso, addr):
    """Cada 10 pisos: piso // 10 tickets al azar para cada uno de la copia."""
    import random
    import app
    for s in _en_la_copia(ses):
        salen = {}
        for _ in range(piso // 10):
            t = random.choice(TICKETS)
            salen[t] = salen.get(t, 0) + 1
        try:
            app._aplicar_efectos(s, getattr(s, 'addr', addr), [('dar', sorted(salen.items()))],
                                 ' por el piso %d de la Torre de Babel' % piso)
        except Exception:
            log.exception('premio de la Torre de Babel')


def al_morir(ses, m, addr='?'):
    """Un monstruo cayo. Si era el jefe del piso de la corrida: premio, piso siguiente o final."""
    p = getattr(ses, 'personaje', None)
    if not p or getattr(p, 'stage', None) != STAGE:
        return
    c = corrida(ses)
    if c is None or int(getattr(m, 'entity_id', 0)) != c.get('jefe'):
        return
    piso = c['piso']
    c['jefe'] = None
    if piso % 10 == 0:
        _premio_cada_diez(ses, piso, addr)
    if piso >= total_pisos():
        segundos = time.time() - c['inicio']
        _cartel(ses, 'The Tower of Babel is conquered! %d floors in %d:%02d' % ((piso,) + divmod(int(segundos), 60)))
        terminar(ses, piso)
        return
    c['piso'] = piso + 1
    _cartel(ses, 'Floor %d cleared! Next: floor %d - %s' % (piso, piso + 1, pisos()[piso]['nombre']))
    try:
        import asyncio
        asyncio.get_event_loop().call_later(PAUSA, _siguiente, ses, c)
    except RuntimeError:
        _siguiente(ses, c)


def _siguiente(ses, c):
    if corrida(ses) is not c or getattr(getattr(ses, 'personaje', None), 'stage', None) != STAGE:
        return
    vivos = [s for s in _en_la_copia(ses) if not getattr(s, 'muerto', False)] or [ses]
    if not _jefe_vivo(vivos[0], c):
        poner_jefe(vivos[0], c)


def terminar(ses, pisos_superados=None):
    """Acaba la corrida de la copia de `ses`, la guarda en el ranking y saca a los que sigan dentro."""
    clave = _clave(ses)
    with _LOCK:
        c = _CORRIDAS.pop(clave, None)
    if c is None:
        return
    superados = c['piso'] - 1 if pisos_superados is None else pisos_superados
    segundos = time.time() - c['inicio']
    guardar(c['modo'], c['nombres'] or {ses.personaje.nombre}, superados, segundos)
    log.info('Torre de Babel %s: %s, %d pisos en %ds', MODOS[c['modo']], ', '.join(sorted(c['nombres'])),
             superados, segundos)
    if pisos_superados is not None:          # la conquistaron: fuera todos
        for s in _en_la_copia(ses):
            try:
                _sacar(s)
                s.volcar()
            except Exception:
                pass


def antes_de_viajar(ses, stage_destino):
    """Alguien sale de la torre: si era el ultimo de su copia, la corrida acaba."""
    p = getattr(ses, 'personaje', None)
    if not p or getattr(p, 'stage', None) != STAGE or int(stage_destino) == STAGE:
        return
    if corrida(ses) is None:
        return
    quedan = [s for s in _en_la_copia(ses) if s is not ses]
    if not quedan:
        terminar(ses)


def al_desconectar(ses):
    antes_de_viajar(ses, 0)


# ------------------------------------------------------------------ la ventana

def _lua():
    return (canal_lua.CARPETA / 'torre.lua').read_text(encoding='utf-8')


def abrir(ses, modo=SOLO):
    return [canal_lua.paquete(_lua()), canal_lua.llamar('TorreAbrir', list(MODOS), total_pisos()),
            lista(modo)]


def lista(modo):
    return canal_lua.llamar('TorreRanking', int(modo), ranking(modo))


def procesar(ses, cuerpo, addr='?') -> bool:
    """El 0x002F de la ventana de la torre. True si era suyo."""
    import struct
    if len(cuerpo) < 9 or cuerpo[0] != CMD_TORRE:
        return False
    a, b = struct.unpack_from('<II', cuerpo, 1)
    modo = PARTY if b == PARTY else SOLO
    if a == 1:
        ses.enviar(*abrir(ses))
    elif a == 2:
        ses.enviar(lista(modo))
    elif a == 3:
        motivo = iniciar(ses, addr, modo)
        if motivo:
            ses.enviar(canal_lua.llamar('TorreAviso', motivo))
        else:
            ses.enviar(canal_lua.llamar('TorreCerrar'))
    return True
