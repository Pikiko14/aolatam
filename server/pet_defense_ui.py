"""Pet Defense: las ventanas (server/lua/pet_defense.lua, tools/ventana_pet_defense.py).

* EL BOTON de la barra de abajo (59005) llama a OnCommandPetDefense (SALUDO_LUA, se manda al entrar con los demas
  saludos de subasta_ventana.py), que pide abrir el menu: la galeria de las mascotas-torre y Start. No se elige nada al
  empezar ("que no se seleccione al iniciar, que tengamos posiciones para ello, se clickeen y se pueda seleccionar cual
  quiero poner ahi", 21/11/2026).
* EN LA PARTIDA, el clic en una piedra (pet_defense_partida.pulsar) abre ELEGIR si esta libre (PDElegir: las mascotas
  con su coste) o la FICHA de su torre (PDTorre: fase, nivel, numeros, Upgrade y Sell). La piedra pulsada queda en
  ses._pd_espacio para lo que se pida despues.
* c2s 0x002F [u8 174][u32 accion][u32 valor]:
    1 abrir el menu             3 empezar                     4 mandar ya la siguiente oleada (en la pausa)
    5 salir (vuelve a la ciudad)      6 jugar otra vez        7 poner la mascota `valor` (0..11) en la piedra elegida
    8 mejorar la torre de la piedra   9 venderla
* LA BARRA DE LA PARTIDA (PDHud) se refresca desde pet_defense_partida.tick_partida cuando cambia algo; al acabar,
  PDFin con el cartel de victoria o derrota y los numeros.
"""
import logging
import time

import canal_lua

log = logging.getLogger('pet_defense')

CMD_PD = 174
N_MAX = 12
SALUDO_LUA = ('function OnCommandPetDefense(dwID, dwCmdID, dwParam, pParam) '
              'game.netcommand2(%d, 1, 0) return 1 end' % CMD_PD)


def _lua():
    return (canal_lua.CARPETA / 'pet_defense.lua').read_text(encoding='utf-8')


def preparar(ses):
    """El script de las ventanas, una vez por conexion."""
    if getattr(ses, '_pd_lua', False):
        return []
    ses._pd_lua = True
    return [canal_lua.paquete(_lua())]


def _torres():
    """[(clave, datos)] en el orden de la configuracion (el de los iconos de tools/ventana_pet_defense.py)."""
    import pet_defense as pd
    return list((pd.config().get('torres') or {}).items())[:N_MAX]


def _stats(d, nivel=1):
    import pet_defense as pd
    cfg = pd.config()
    extra = max(0, int(nivel) - 1)
    ataque = pd.dano_de(d, nivel) or int(round(int(d.get('ataque', 0)) * float(cfg.get('multiplicador_ataque', 1))
                                               * float(cfg.get('mejora_ataque', 1.5)) ** extra))
    alcance = int(d.get('alcance', 0)) + extra * int(cfg.get('mejora_alcance', 1))
    return ataque, alcance


def abrir(ses):
    import pet_defense as pd
    import pet_defense_partida as pp
    cfg = pd.config()
    n = len(cfg.get('oleadas') or [])
    jefe = any(t == 'jefe' for ol in cfg.get('oleadas') or () for t, _ in ol.get('enemigos') or ())
    sub = '%d waves%s - defend the crystal' % (n, ', boss at the end' if jefe else '')
    import pet_defense_ranking as rk
    quedan = rk.quedan_hoy(getattr(ses.personaje, 'char_id', 0))
    hoy = '' if quedan is None else '  Games left today: %d/%d.' % (quedan, rk.maximo_al_dia())
    info = _linea_marca(ses) + '.' + hoy
    filas = []
    for clave, d in _torres():
        ataque, alcance = _stats(d)
        filas.append([d.get('nombre', clave), d.get('rol', ''), 'DMG %d  RNG %d' % (ataque, alcance),
                      int(d.get('coste', 0))])
    pk = preparar(ses) + [canal_lua.llamar('PDAbrir', filas, sub, info)]
    if pp.partida(ses) is not None:
        pk.append(canal_lua.llamar('PDAviso', 'A game is running. Leave it to start again.'))
    return pk


# ---------------------------------------------------------------------------------------------- elegir y ficha
def elegir(pa, i):
    """La ventana para elegir que mascota poner en la piedra libre i."""
    opciones = [[d.get('nombre', c), d.get('rol', ''), int(d.get('coste', 0)), pa.essence >= int(d.get('coste', 0))]
                for c, d in _torres()]
    titulo = 'Stone %d - choose a pet   (Essence %d)' % (i + 1, pa.essence)
    return preparar(pa.ses) + [canal_lua.llamar('PDElegir', titulo, opciones)]


def ficha_torre(pa, i):
    """La ficha de la torre de la piedra i: fase, nivel, numeros, lo del siguiente nivel, Upgrade y Sell."""
    import pet_defense as pd
    import pet_defense_partida as pp
    t = pp.torre_en(pa, i)
    if t is None:
        return elegir(pa, i)
    claves = [c for c, _ in _torres()]
    tipo = claves.index(t.tipo) + 1 if t.tipo in claves else 1
    tope = int(pd.config().get('nivel_maximo', 3))
    fase = min(3, t.nivel)
    nombre = t.ficha.get('nombre') or t.datos.get('nombre', t.tipo)
    extras = []
    if t.n_objetivos > 1:
        extras.append('x%d' % t.n_objetivos)
    if t.area:
        extras.append('splash')
    if t.ralentiza:
        extras.append('slow')
    stats = 'DMG %d  RNG %d  %.1fs %s' % (t.dano_fijo or t.ataque, t.alcance, t.cadencia, ' '.join(extras))
    puede = t.nivel < tope
    if puede:
        ataque, alcance = _stats(t.datos, t.nivel + 1)
        coste = pp.coste_mejora(t)
        siguiente = 'Next: DMG %d  RNG %d - %d' % (ataque, alcance, coste)
        ayuda_mejorar = 'Evolve to level %d for %d Essence' % (t.nivel + 1, coste)
    else:
        siguiente, ayuda_mejorar = 'Max level', ''
    vuelta = int(getattr(t, 'gastado', 0) * float(pd.config().get('venta_reembolso', 0.5)))
    return preparar(pa.ses) + [canal_lua.llamar(
        'PDTorre', tipo, fase, '%s  (%s)' % (nombre, t.datos.get('nombre', t.tipo)), 'Level %d / %d' % (t.nivel, tope),
        stats.strip(), siguiente, puede, ayuda_mejorar, 'Sell for %d Essence' % vuelta)]


# ---------------------------------------------------------------------------------------------- la barra
def _aviso(pa, ahora):
    if pa.cola or pa.enemigos:
        quedan = len(pa.cola) + len(pa.enemigos)
        return 'Wave %d: %d enem%s left' % (pa.oleada, quedan, 'y' if quedan == 1 else 'ies')
    if pa.proxima_oleada > ahora:
        return 'Next wave in %d s' % max(1, int(pa.proxima_oleada - ahora + 0.99))
    return ''


def refrescar(pa, ahora=None, forzar=False):
    """Manda PDHud si cambio algo de lo que ensena (como mucho lo de la cuenta atras, una vez por segundo)."""
    ahora = time.time() if ahora is None else ahora
    ses = pa.ses
    en_pausa = not pa.cola and not pa.enemigos and pa.proxima_oleada > ahora
    estado = ('%d/%d' % (pa.vida, pa.vida_max), '%d/%d' % (pa.oleada, pa.total_oleadas), pa.essence,
              _aviso(pa, ahora), en_pausa)
    if not forzar and getattr(pa, '_hud', None) == estado:
        return False
    pa._hud = estado
    try:
        ses.enviar(*(preparar(ses) + [canal_lua.llamar('PDHud', *estado)]))
    except Exception:
        log.debug('PDHud', exc_info=True)
    return True


def fin(pa):
    """El cartel del final (o solo quitar la barra si abandono)."""
    ses = pa.ses
    d = getattr(pa, 'resultado_datos', None) or {}
    if pa.resultado == 'abandono' or not d:
        try:
            ses.enviar(canal_lua.llamar('PDHudCerrar'))
        except Exception:
            pass
        return
    s = int(d.get('segundos', 0))
    lineas = ['Waves cleared: %d / %d   Crystal: %d / %d' % (d.get('oleadas', 0), pa.total_oleadas, pa.vida, pa.vida_max),
              'Time: %d:%02d   Enemies defeated: %d' % (s // 60, s % 60, d.get('muertos', 0)),
              'Score: {:,}   Reward: {:,} AG'.format(int(d.get('puntos', 0)), int(d.get('angel_gold', 0))),
              _linea_marca(ses, int(d.get('puntos', 0)))]
    try:
        ses.enviar(*(preparar(ses) + [canal_lua.llamar('PDFin', pa.resultado == 'victoria', lineas)]))
    except Exception:
        log.debug('PDFin', exc_info=True)


# ---------------------------------------------------------------------------------------------- mejoras por oleada
def bono(pa):
    """La ventana para elegir la mejora de las mascotas (pet_defense_partida.BONOS), con lo que lleva cada una."""
    import pet_defense_partida as pp
    opciones = []
    for clave in pp.BONOS:
        d = (pa.cfg.get('bonos') or {}).get(clave) or {}
        opciones.append([d.get('nombre', clave), d.get('texto', ''), 'Lv %d' % int(pa.bonos.get(clave, 0))])
    quedan = '' if pa.elecciones <= 1 else '  (%d to choose)' % pa.elecciones
    titulo = 'Wave %d cleared! Choose a blessing for all your pets%s' % (pa.oleada, quedan)
    return preparar(pa.ses) + [canal_lua.llamar('PDBono', titulo, opciones)]


# ---------------------------------------------------------------------------------------------- el ranking
def _tiempo(s):
    s = int(s or 0)
    return '%d:%02d' % (s // 60, s % 60)


def _linea_marca(ses, puntos=None):
    """'Season 3 best: #4 21,300 (Gold)' del jugador, o 'No score yet this season'."""
    import pet_defense_ranking as rk
    n = rk.temporada()[0]
    puesto, fila = rk.mi_marca(getattr(ses.personaje, 'char_id', 0), n)
    if fila is None:
        return 'No score yet in season %d' % n
    r = rk.rango(fila[4], puesto)
    nuevo = ' NEW BEST!' if puntos is not None and int(puntos) >= int(fila[4]) and int(puntos) > 0 else ''
    return 'Season %d best: #%d  {:,}%s%s'.format(int(fila[4])) % (n, puesto, (' (%s)' % r) if r else '', nuevo)


def ranking(ses):
    """La ventana del ranking de la temporada: los 10 mejores, la marca del jugador y los premios por rango."""
    import pet_defense as pd
    import pet_defense_ranking as rk
    n, _desde, hasta = rk.temporada()
    dias = max(0, int((hasta - time.time()) // 86400))
    horas = max(0, int((hasta - time.time()) % 86400 // 3600))
    titulo = 'Season %d - ends in %dd %dh' % (n, dias, horas)
    filas = []
    for i, (cid, _u, nombre, nivel, puntos, oleadas, segundos, _res) in enumerate(rk.ranking(n)):
        filas.append([i + 1, nombre, rk.rango(puntos, i + 1) or '-', '{:,}'.format(int(puntos)),
                      '%d/%d  %s' % (oleadas, len(pd.config().get('oleadas') or []), _tiempo(segundos))])
    premios = pd.config().get('premios') or {}
    def _ag(v):
        v = int(v or 0)
        return '%dk' % (v // 1000) if v and v % 1000 == 0 else '{:,}'.format(v)
    linea_premios = 'Rewards (AG): ' + '  '.join('%s %s' % (k, _ag((premios.get(k) or {}).get('angel_gold', 0)))
                                                 for k in ('Champion', 'Angel', 'Gold', 'Silver', 'Bronze') if premios.get(k))
    r = pd.config().get('rangos') or {}
    linea_rangos = 'Bronze {:,}  Silver {:,}  Gold {:,}  Angel top {}  Champion #1'.format(
        int(r.get('Bronze', 0)), int(r.get('Silver', 0)), int(r.get('Gold', 0)), int(r.get('angel_top', 10)))
    return preparar(ses) + [canal_lua.llamar('PDRanking', titulo, filas, _linea_marca(ses), linea_rangos, linea_premios)]


# ---------------------------------------------------------------------------------------------- los botones
def _salir(ses, addr):
    import app
    import pet_defense as pd
    import pet_defense_partida as pp
    pp.terminar(ses, 'abandono', avisar=False)
    mp = pd.config().get('mapa') or {}
    p = getattr(ses, 'personaje', None)
    if p is not None and int(getattr(p, 'stage', 0) or 0) == int(mp.get('stage', -1)):
        st, (x, y) = mp.get('salida', [41, [173, 91]])
        app._sincronizar_cambio_mapa(ses, int(st), int(x), int(y))


def procesar(ses, cuerpo, addr='?') -> bool:
    """El 0x002F de las ventanas de Pet Defense. True si era suyo."""
    import struct
    import pet_defense_partida as pp
    if len(cuerpo) < 9 or cuerpo[0] != CMD_PD:
        return False
    a, b = struct.unpack_from('<II', cuerpo, 1)
    pa = pp.partida(ses)
    i = getattr(ses, '_pd_espacio', None)
    if a == 1:
        ses.enviar(*abrir(ses))
    elif a in (3, 6):
        if a == 3 and pa is not None:
            ses.enviar(canal_lua.llamar('PDAviso', 'A game is already running.'))
            return True
        msg = pp.empezar(ses, addr)
        log.info('Pet Defense: %s pide empezar: %s', getattr(ses.personaje, 'nombre', '?'), msg)
        if msg.startswith('You already played'):
            ses.enviar(canal_lua.llamar('PDAviso', 'No games left today. Come back tomorrow!'))
            pp._aviso(ses, msg)
            return True
        ses.enviar(canal_lua.llamar('PDCerrar'))
    elif a == 10:
        ses.enviar(*ranking(ses))
    elif a == 11 and pa is not None:
        import pet_defense_partida as pp_b
        ok, msg = pp_b.elegir_bono(pa, pp_b.BONOS[b] if b < len(pp_b.BONOS) else '')
        if ok and pa.elecciones > 0:
            ses.enviar(*bono(pa))
        elif ok:
            ses.enviar(canal_lua.llamar('PDBonoCerrar'))
        if ok:
            pp_b._aviso(ses, msg)
        else:
            ses.enviar(canal_lua.llamar('PDBonoAviso', msg))
    elif a == 4:
        if pa is not None and pp.saltar_pausa(pa):
            refrescar(pa, forzar=True)
    elif a == 5:
        _salir(ses, addr)
    elif a == 7 and pa is not None and i is not None:
        torres = _torres()
        if b >= len(torres):
            return True
        ok, msg = pp.construir(pa, i, torres[b][0])
        ses.enviar(canal_lua.llamar('PDElegirCerrar') if ok else canal_lua.llamar('PDElegirAviso', msg))
        if ok:
            refrescar(pa, forzar=True)
    elif a in (8, 9) and pa is not None and i is not None:
        ok, msg = (pp.mejorar if a == 8 else pp.vender)(pa, i)
        if ok and a == 8:
            ses.enviar(*ficha_torre(pa, i))
        elif ok:
            ses.enviar(canal_lua.llamar('PDTorreCerrar'))
        if not ok or a == 8:
            ses.enviar(canal_lua.llamar('PDTorreAviso', msg))
        if ok:
            refrescar(pa, forzar=True)
    return True
