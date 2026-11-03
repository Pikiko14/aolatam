"""La Torre de Babel (02/11/2026): 60 pisos, un jefe base por piso del nivel del piso, solo o en party.

Pedido del usuario: "un evento de torre de babel, en el que salgan jefes desde lvl 1 hasta lvl 60, jefes base por
supuesto"; se abre desde una accion (el boton de la barra) donde sale el ranking y la seleccion del modo; cada
intento empieza de cero; premio por piso.

* LOS PISOS: plantillas/torre_babel.json (tools/generar_torre_babel.py): el jefe de cada piso y sus stats.
* EL MAPA: el 133, que tools/generar_mapa_torre.py hace copia de la Limitless Tower (110): cada piso es una de sus
  salas, y al matar al jefe todos los de la copia suben (subir: un salto dentro del mapa) a la sala del piso
  siguiente. Se llama "Tower of Babel" en stage.xml (tools/parche_subasta_ventana.py) y es dinamico en
  plantillas/instancias.json: cada jugador solo o cada party tiene su propia copia (eventos_mundo._clave_corrida).
* LA CORRIDA: iniciar() lleva al piso 1. Al cargar el mapa (al_entrar) sale el jefe del piso en su casilla
  (app._poner_generado, sin reaparicion); al morir (al_morir, desde app._procesar_muerte_monstruo) se anuncia el
  piso siguiente y a los PAUSA segundos todos suben a su sala, donde sale su jefe. Cada 10 pisos, ademas del botin del jefe, todos los de la
  copia reciben tickets. Los jefes salen con todo x MULT_SOLO o x MULT_PARTY (vida, ataque y defensas).
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
# El mapa lo hace tools/generar_mapa_torre.py: el 133 es una copia de la Limitless Tower (110) y cada piso una de sus
# salas. De alli salen, por piso, donde se llega y donde sale su jefe.
MAPA_JSON = pathlib.Path(__file__).parent / 'plantillas' / 'torre_babel_mapa.json'
EFECTO_SUBIR, MAGIA_SUBIR = 45, 1640   # el destello de Swiftness (holy_battlefield.salto) al pasar de sala
_MAPA = None


def mapa():
    global _MAPA
    if _MAPA is None:
        _MAPA = json.loads(MAPA_JSON.read_text(encoding='utf-8'))
    return _MAPA


def entrada():
    return tuple(mapa()['entrada'])


def casilla_jefe(piso):
    return tuple(mapa()['pisos'][piso - 1]['centro'])


def llegada(piso):
    return tuple(mapa()['pisos'][piso - 1]['llegada'])


def subir(ses, c):
    """Lleva a todos los de la copia a la sala del piso de la corrida y saca alli su jefe: "que cada piso sea 1 tp al
    piso nuevo" (02/11/2026). Es un salto dentro del mismo mapa (desplazamientos.reubicar), sin recargarlo."""
    import combate
    import desplazamientos
    import presencia
    destino = llegada(c['piso'])
    gente = _en_la_copia(ses) or [ses]
    for s in gente:
        try:
            p = s.personaje
            s.enviar(combate.efecto_magia_self_inicio(p.entity_id, EFECTO_SUBIR, MAGIA_SUBIR, cast_time=0))
            desplazamientos.reubicar(s, destino, 'torre')
            s.enviar(combate.efecto_magia_self_fin(p.entity_id, EFECTO_SUBIR, MAGIA_SUBIR))
            presencia.notificar_companero_accion(
                s, combate.efecto_magia_self_fin(presencia.entidad_de(s), EFECTO_SUBIR, MAGIA_SUBIR))
        except Exception:
            log.exception('Torre de Babel: no se pudo subir a %s', getattr(getattr(s, 'personaje', None), 'nombre', '?'))
    vivos = [s for s in gente if not getattr(s, 'muerto', False)] or [ses]
    if not _jefe_vivo(vivos[0], c):
        poner_jefe(vivos[0], c)
    _cartel(ses, 'Tower of Babel - Floor %d / %d: %s' % (c['piso'], total_pisos(), pisos()[c['piso'] - 1]['nombre']))


PISOS_JSON = pathlib.Path(__file__).parent / 'plantillas' / 'torre_babel.json'
DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'torre_babel.db'
CMD_TORRE = 169
SOLO, PARTY = 0, 1
MODOS = ('Solo', 'Party')
PAUSA = 5.0                 # segundos entre la muerte de un jefe y el siguiente: "ponle tiempo de 5 seg" (03/11/2026)
# "Sube la dificultad: solo x2 y parties x3" (03/11/2026). Antes Solo x1 y Party x2. Vida, ataque y defensas.
MULT_SOLO = 2.0
MULT_PARTY = 3.0
# EL PREMIO CADA 10 PISOS: 5 de los vales que pide el canje de Event Overview > Exchange > Enhanced Pestle and Ride
# Feed (Lucky Enhanced Pestle / Ride Feed / Piercing Hammer / Hammer Voucher, al azar entre los cuatro) y 5 Mount
# Coins: "cada 10 pisos 5 materiales aleatorios para sacar de aca, y tambien mount coin 5" (02/11/2026).
TICKETS = (20228, 20229, 20230, 20231)
VALES_POR_PREMIO = 5
MOUNT_COIN = 89073          # cliente_local.ITEM_MONEDA_MONTURA
MONEDAS_POR_PREMIO = 5
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
                                                                  list(MODOS), total_pisos()), lista(PARTY),
                     clases.aviso('%s invites you to the Tower of Babel: press Join in the tower window.'
                                  % ses_lider.personaje.nombre, tipo=0))
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
    with _LOCK:
        c = _CORRIDAS.get(clave)
        if c is None:
            c = _CORRIDAS[clave] = {'modo': modo, 'piso': 1, 'inicio': time.time(), 'nombres': set(), 'jefe': None}
        c['nombres'].add(ses.personaje.nombre)
    log.info('%s entra a la Torre de Babel (%s, piso %d)', ses.personaje.nombre, MODOS[modo], c['piso'])
    app._viajar_por_portal(ses, addr, {'destino': STAGE, 'llegada': llegada(c['piso'])}, motivo='a la Torre de Babel')
    if modo == PARTY and _es_lider(ses):
        # Cada vez que entra el lider, no solo al empezar: "la torre de babel party no le solicita aceptar el summon a
        # los demas" (02/11/2026) cuando la party ya tenia una subida a medias.
        import clases
        n = invitar(ses)
        log.info('Torre de Babel: %s invita a %d de su party', ses.personaje.nombre, n)
        ses.enviar(clases.aviso('Tower of Babel: invitation sent to %d party member(s).' % n if n else
                                'Tower of Babel: your whole party is already inside.', tipo=0))
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
    if (p.tile_x, p.tile_y) != llegada(c['piso']) and c['piso'] > 1:
        import desplazamientos                  # quien se une a medias, a la sala del piso en curso
        desplazamientos.reubicar(ses, llegada(c['piso']), 'torre')
    if not _jefe_vivo(ses, c):
        poner_jefe(ses, c)
    _cartel(ses, 'Tower of Babel - Floor %d / %d: %s' % (c['piso'], total_pisos(), pisos()[c['piso'] - 1]['nombre']))


def poner_jefe(ses, c):
    """Saca el jefe del piso de la corrida en la copia de `ses`."""
    import app
    datos = pisos()[c['piso'] - 1]
    eid = app._SIG_GENERADO[0]
    app._SIG_GENERADO[0] += 1
    m = app._poner_generado(ses, eid, int(datos['npc_type']), casilla_jefe(c['piso']), 0)
    if m is None:
        log.warning('Torre de Babel: no se pudo sacar el jefe del piso %d (%s)', c['piso'], datos['npc_type'])
        return None
    k = MULT_PARTY if c['modo'] == PARTY else MULT_SOLO
    m.hp_max = m.hp = int(datos['hp'] * k)
    m.atk, m.defensa = int(datos['atk'] * k), int(datos['def'] * k)
    m.matk, m.mdef = int(datos['matk'] * k), int(datos['mdef'] * k)
    m.nivel = int(datos['nivel'])
    m.piso_torre = c['piso']
    c['jefe'] = eid
    ses.volcar()
    # "Si estoy en pt no veo el mob jefe de la torre" (03/11/2026): la aparicion solo iba al que lo saca y al resto
    # por el espejo de la sala, que no siempre llegaba. Se le manda tambien a cada uno de la copia, con su vida, y el
    # jefe entra en sus bichos (si no comparten ya la sala) para que puedan pegarle.
    try:
        import combate
        import login
        aparece = login._npc_spawn(eid, int(datos['npc_type']), m.nombre, tuple(casilla_jefe(c['piso'])),
                                   sprite=getattr(m, 'sprite', 0), klass=1)
        for s in _en_la_copia(ses):
            if s is ses or getattr(s, 'cerrada', False):
                continue
            if getattr(s, 'monstruos', None) is None:
                s.monstruos = {}
            s.monstruos.setdefault(eid, m)
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(aparece, combate.atributo(eid, m.porcentaje))
            if hasattr(s, 'volcar'):
                s.volcar()
    except Exception:
        log.exception('Torre de Babel: no se pudo mostrar el jefe a la party')
    return m


def _cartel(ses, texto):
    """El aviso a todos los de la copia, en el chat. No en el cartel que cruza la parte de arriba
    (totem_war.cartel_deslizante): "que no salgan los mensajes aca" (02/11/2026)."""
    import clases
    pk = clases.aviso(texto, tipo=0)
    for s in _en_la_copia(ses):
        try:
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(pk)
            s.volcar()
        except Exception:
            pass


def premio_cada_diez(rng=None):
    """[(item, cantidad)] de un premio de 10 pisos: VALES_POR_PREMIO vales al azar de los cuatro y las Mount Coins."""
    import random
    rng = rng or random
    salen = {}
    for _ in range(VALES_POR_PREMIO):
        t = rng.choice(TICKETS)
        salen[t] = salen.get(t, 0) + 1
    return sorted(salen.items()) + [(MOUNT_COIN, MONEDAS_POR_PREMIO)]


def _premio_cada_diez(ses, piso, addr):
    """Cada 10 pisos, a cada uno de la copia: premio_cada_diez()."""
    import app
    for s in _en_la_copia(ses):
        salen = premio_cada_diez()
        try:
            app._aplicar_efectos(s, getattr(s, 'addr', addr), [('dar', salen)],
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
    _cartel(ses, 'Floor %d cleared! Going up to floor %d in %d seconds...' % (piso, piso + 1, int(PAUSA)))
    try:
        import asyncio
        asyncio.get_event_loop().call_later(PAUSA, _siguiente, ses, c)
    except RuntimeError:
        _siguiente(ses, c)


def _siguiente(ses, c):
    if corrida(ses) is not c or getattr(getattr(ses, 'personaje', None), 'stage', None) != STAGE:
        return
    subir(ses, c)


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
