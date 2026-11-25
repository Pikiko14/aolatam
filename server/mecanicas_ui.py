"""La ventana Challenges (25/11/2026), sin comandos para los jugadores: Contracts (contratos.py), Pet Tournament
(torneo_mascotas.py) y Hardcore (hardcore.py). Ventana de tools/ventana_mecanicas.py, Lua en server/lua/mecanicas.lua.

c2s 0x002F [u8 180][u32 a][u32 b]:
    a=1 abrir / cambiar a la pestana b; 0 la cerraron; 9 el cliente no tiene la ventana
    Contracts: 10+i boton de la fila i (Deliver / Cancel); 20 / 21 pagina; 22 Item <-> Boss; 23..26 el texto a buscar
               en trozos de 4 letras y 27 buscar; 28 / 29 resultado anterior / siguiente; 31 cantidad (b), 30 publicar
               con b de recompensa
    Pet Tournament: 40+k inscribirse con la estrategia k (0 agresiva, 1 defensiva, 2 astuta); 43 salir
    Hardcore: 50 empezar
"""
import logging
import struct

import canal_lua
import sociales

log = logging.getLogger('mecanicas_ui')

CMD_CH = 180
SALUDO_LUA = (canal_lua.CARPETA / 'mecanicas.lua').read_text(encoding='utf-8')
ESTRATEGIAS = ('agresiva', 'defensiva', 'astuta')
POR_PAGINA = 6


def _estado(ses):
    e = getattr(ses, '_ch', None)
    if e is None:
        e = ses._ch = {'pestana': 1, 'pagina': 0, 'tipo': 'item', 'buscar': [b'\0' * 4] * 4, 'resultados': [],
                       'sel': 0, 'cantidad': 1, 'ayuda': '', 'filas': []}
    return e


def _contratos(ses):
    import contratos
    e = _estado(ses)
    todos = contratos.abiertos()
    paginas = max(1, (len(todos) + POR_PAGINA - 1) // POR_PAGINA)
    e['pagina'] = min(e['pagina'], paginas - 1)
    trozo = todos[e['pagina'] * POR_PAGINA:(e['pagina'] + 1) * POR_PAGINA]
    cid = int(ses.personaje.char_id)
    filas = []
    for c in trozo:
        if c['cid'] == cid:
            boton = 'Cancel'
        elif c['tipo'] == 'item':
            boton = 'Deliver'
        else:
            boton = ''                      # jefe: se cobra al matarlo
        filas.append([contratos.texto_contrato(c), boton])
    e['filas'] = [c['id'] for c in trozo]
    if e['resultados']:
        i, n = e['resultados'][e['sel']]
        resultado = '%s %d of %d: %s' % ('Item' if e['tipo'] == 'item' else 'Boss', e['sel'] + 1,
                                         len(e['resultados']), n)
    else:
        resultado = 'Type a name and press Find.'
    pagina = 'Page %d/%d, %d open. Boss contracts pay whoever kills it.' % (e['pagina'] + 1, paginas, len(todos))
    return [e['ayuda'] or 'Post gold for an item or a boss; anyone can fulfil it.', filas, pagina,
            'Item' if e['tipo'] == 'item' else 'Boss', resultado, 1 if e['tipo'] == 'item' else 0]


def _torneo(ses):
    import torneo_mascotas as tm
    from sociales_ui import proxima
    e = _estado(ses)
    ficha, st = tm.mascota_de(ses)
    ins = tm.INSCRITOS.get(int(ses.personaje.char_id))
    c = tm.cfg()
    lineas = []
    if ficha is None:
        lineas.append('You need a pet to enter the Pet Tournament.')
    else:
        lineas.append('Your pet: %s, level %d (HP %d, ATK %d, DEF %d).' % (
            ficha.get('nombre') or 'Pet', int(ficha.get('nivel') or 1), int(st.get('hp') or 0),
            max(int(st.get('atk') or 0), int(st.get('matk') or 0)), int(st.get('dfs') or 0)))
    nxt = proxima('torneo')
    lineas.append('Next tournament: %s. %d pets signed up.' % (nxt or '-', len(tm.INSCRITOS)))
    lineas.append(('Signed up as %s. Pick another strategy to change it.' % c['estrategias'][ins['estrategia']]['nombre'])
                  if ins else 'Pick a strategy to sign up. Pets fight on their own!')
    lineas.append('Aggressive beats Tricky, Tricky beats Defensive, Defensive beats Aggressive.')
    resultados = []
    if tm.ULTIMO['podio']:
        resultados.append('Last tournament: 1. %s  2. %s' % (tm.ULTIMO['podio'][0],
                                                            tm.ULTIMO['podio'][1] if len(tm.ULTIMO['podio']) > 1 else '-'))
        mios = tm.ULTIMO['combates'].get(int(ses.personaje.char_id)) or []
        resultados += (mios or tm.ULTIMO['lineas'])[-7:]
    return [e['ayuda'] or 'Pet Tournament: your strongest pet fights for you.', lineas,
            1 if ficha is not None else 0, 1 if ins else 0, resultados]


def _hardcore(ses):
    import hardcore
    e = _estado(ses)
    f = hardcore.ficha(ses.personaje.char_id)
    c = hardcore.cfg()
    if f and f['estado'] == 'vivo':
        lineas = ['You are in the Hardcore season %s. +%d%% EXP.' % (hardcore.temporada(), int(c['exp_extra'])),
                  'If a monster kills you, back to level %d and season lost. PvP is safe.' % int(f['nivel_ini']),
                  ('Level %d without dying: %s Angel Gold. ' % (int(c['nivel_premio']), format(int(c['ag_premio']), ','))
                   + 'Survive the month: %s.' % c['texto_premio'])]
        empezar = 0
    elif f:
        lineas = ['You fell this season at level %d. Try again next month.' % int(f['nivel']), '', '']
        empezar = 0
    else:
        lineas = ['Hardcore season %s: +%d%% EXP. Die to a monster and you lose it all.' % (
                      hardcore.temporada(), int(c['exp_extra'])),
                  'Only characters up to level %d can start. PvP deaths do not count.' % int(c['nivel_max']),
                  'Reach level %d without dying: %s Angel Gold. Survivors: %s.' % (
                      int(c['nivel_premio']), format(int(c['ag_premio']), ','), c['texto_premio'])]
        empezar = 1 if int(ses.personaje.nivel) <= int(c['nivel_max']) else 0
    lineas.append('SEASON RANKING')
    ranking = ['%d. %s  Lv%d%s' % (i, n, nv, '' if est == 'vivo' else '  (fallen)')
               for i, (n, nv, est) in enumerate(hardcore.ranking(), 1)] or ['Nobody has started this season yet.']
    return [e['ayuda'] or 'Hardcore: separate risk, separate glory.', lineas, empezar, ranking]


def datos(ses, pestana):
    return {1: _contratos, 2: _torneo, 3: _hardcore}[pestana](ses)


def abrir(ses, pestana=None):
    e = _estado(ses)
    e['pestana'] = int(pestana or e['pestana'] or 1)
    if e['pestana'] not in (1, 2, 3):
        e['pestana'] = 1
    ses._ch_abierto = True
    ses.enviar(canal_lua.paquete(SALUDO_LUA), canal_lua.llamar('CHAbrir', e['pestana'], datos(ses, e['pestana'])))


def refrescar(ses):
    if getattr(ses, '_ch_abierto', False):
        e = _estado(ses)
        try:
            ses.enviar(canal_lua.llamar('CHDatos', e['pestana'], datos(ses, e['pestana'])))
        except Exception:
            log.debug('challenges: refrescar', exc_info=True)


def procesar(ses, cuerpo) -> bool:
    if len(cuerpo) < 9 or cuerpo[0] != CMD_CH or getattr(ses, 'personaje', None) is None:
        return False
    import contratos
    import hardcore
    import torneo_mascotas as tm
    a, b = struct.unpack_from('<II', cuerpo, 1)
    e = _estado(ses)
    if a == 1:
        e['ayuda'] = ''
        abrir(ses, b)
        return True
    if a == 0:
        ses._ch_abierto = False
        return True
    if a == 9:
        ses._ch_abierto = False
        sociales.aviso(ses, '[Challenges] Update the game to use the Challenges window.')
        return True
    texto = None
    if 10 <= a <= 15:
        i = a - 10
        if i < len(e['filas']):
            idc = e['filas'][i]
            c = next((x for x in contratos.abiertos() if x['id'] == idc), None)
            if c is None:
                texto = 'That contract is closed.'
            elif c['cid'] == int(ses.personaje.char_id):
                texto = contratos.cancelar(ses, idc)
            else:
                texto = contratos.entregar(ses, idc)
    elif a in (20, 21):
        e['pagina'] = max(0, e['pagina'] + (1 if a == 21 else -1))
    elif a == 22:
        e['tipo'] = 'jefe' if e['tipo'] == 'item' else 'item'
        e['resultados'], e['sel'] = [], 0
    elif 23 <= a <= 26:
        e['buscar'][a - 23] = struct.pack('<I', b)
        return True
    elif a == 27:
        t = b''.join(e['buscar']).split(b'\0')[0].decode('latin-1', 'replace')
        e['buscar'] = [b'\0' * 4] * 4
        e['resultados'], e['sel'] = contratos.buscar(e['tipo'], t), 0
        texto = None if e['resultados'] else 'Nothing found for "%s".' % t
    elif a in (28, 29) and e['resultados']:
        e['sel'] = (e['sel'] + (1 if a == 29 else -1)) % len(e['resultados'])
    elif a == 31:
        e['cantidad'] = max(1, int(b))
        return True
    elif a == 30:
        if not e['resultados']:
            texto = 'Find the item or boss first.'
        else:
            texto = contratos.publicar(ses, e['tipo'], e['resultados'][e['sel']][0], e['cantidad'], int(b))
    elif 40 <= a <= 42:
        texto = tm.inscribir(ses, ESTRATEGIAS[a - 40])
    elif a == 43:
        texto = tm.retirar(ses)
    elif a == 50:
        texto = hardcore.apuntar(ses)
    e['ayuda'] = texto or ''
    if texto:
        sociales.aviso(ses, '[Challenges] ' + texto)
    refrescar(ses)
    return True
