"""Back office de la web (/panel/): jugadores y admins entran con su usuario y contrasena del juego.

Lo atiende el mismo proceso que el registro de cuentas (web_registro.py, solo en 127.0.0.1; nginx hace proxy_pass de
/api/panel/). Pedido el 04/11/2026: "un back office donde se puedan loguear: personajes, recargar, cambio de
contrasena, una seccion de eventos"; "el admin pueda dar diamantes" (los diamantes son el Angel Gold del Item Mall) y
"el back office tambien es para usuarios normales".

    Cualquier cuenta:  sus personajes y su AG, cambiar su contrasena, el calendario de eventos.
    Admins (configuracion.USUARIOS_GM): ademas buscar cualquier cuenta (por usuario o por personaje), darle o quitarle
                       AG y ponerle una contrasena nueva. Cada accion de admin queda en la tabla panel_auditoria.

    POST /api/panel/login        {usuario, password}            -> cookie de sesion (HttpOnly, Secure, SameSite=Strict)
    POST /api/panel/logout
    GET  /api/panel/yo                                         -> {usuario, admin, ag, personajes}
    POST /api/panel/contrasena   {actual, nueva, confirmar}
    GET  /api/panel/eventos                                    -> calendario (proximas fechas en UTC)
    GET  /api/panel/admin/cuenta?q=usuario_o_personaje         (admin)
    POST /api/panel/admin/ag     {usuario, cantidad, motivo}    (admin; cantidad negativa quita)
    POST /api/panel/admin/contrasena {usuario, nueva}           (admin)

Los mensajes salen en ingles o en espanol (lang=es en la consulta o en el cuerpo), como el registro.

SEGURIDAD: sesiones en memoria (se pierden al reiniciar: hay que volver a entrar), freno de intentos de login por IP y
por usuario, y los POST solo se aceptan con Content-Type JSON y con Origin del propio sitio (contra CSRF, ademas de
SameSite=Strict).
"""
import datetime as dt
import json
import logging
import pathlib
import re
import secrets
import threading
import time

import cuentas
import configuracion

log = logging.getLogger('panel_web')

RAIZ = pathlib.Path(__file__).resolve().parent.parent
COOKIE = 'aof_panel'
DURACION_SESION = 8 * 3600
INTENTOS_MAX = 5                 # fallos de login...
VENTANA_INTENTOS = 15 * 60       # ...en estos segundos, por IP y por usuario
AG_MAX_POR_ACCION = 100_000_000
CONTRASENA_VALIDA = re.compile(r'^[\x21-\x7e]{4,16}$')

_SESIONES = {}                   # token -> {'usuario', 'exp'}
_FALLOS = {}                     # clave ('ip', x) / ('usuario', x) -> [instantes]
_CERROJO = threading.Lock()

# (ingles, espanol)
MENSAJES = {
    'credenciales': ('Wrong username or password.', 'Usuario o contraseña incorrectos.'),
    'formato_viejo': ('Log in to the game once with this account, then try again here.',
                      'Entra una vez al juego con esta cuenta y vuelve a intentarlo aquí.'),
    'demasiados': ('Too many attempts. Wait a few minutes and try again.',
                   'Demasiados intentos. Espera unos minutos y vuelve a intentarlo.'),
    'sin_sesion': ('Your session has expired. Log in again.', 'Tu sesión expiró. Vuelve a entrar.'),
    'no_admin': ('Only admins can do that.', 'Solo los admins pueden hacer eso.'),
    'invalida': ('Invalid request.', 'Petición inválida.'),
    'contrasena_mala': ('The password must be 4 to 16 characters, with no spaces or accented letters.',
                        'La contraseña debe tener de 4 a 16 caracteres, sin espacios ni acentos.'),
    'no_coinciden': ("The passwords don't match.", 'Las contraseñas no coinciden.'),
    'actual_mal': ('Your current password is not correct.', 'Tu contraseña actual no es correcta.'),
    'contrasena_ok': ('Password changed. Use the new one in the game.', 'Contraseña cambiada. Usa la nueva en el juego.'),
    'no_existe': ('No account or character with that name.', 'No hay ninguna cuenta ni personaje con ese nombre.'),
    'cantidad_mala': ('Enter a whole number of AG other than 0.', 'Escribe una cantidad entera de AG distinta de 0.'),
    'sin_saldo': ('The account does not have that much AG to remove.', 'La cuenta no tiene tanto AG para quitar.'),
    'ag_ok': ('Done: %s now has %s AG.', 'Hecho: %s tiene ahora %s AG.'),
    'reset_ok': ('Password of %s changed.', 'Contraseña de %s cambiada.'),
}


def msg(clave, lang='en', *args):
    texto = MENSAJES[clave][1 if lang == 'es' else 0]
    return texto % args if args else texto


# --------------------------------------------------------------------------- sesiones y login

def _limpiar(ahora):
    for tok in [t for t, s in _SESIONES.items() if s['exp'] <= ahora]:
        _SESIONES.pop(tok, None)
    for k in [k for k, v in _FALLOS.items() if not v or v[-1] < ahora - VENTANA_INTENTOS]:
        _FALLOS.pop(k, None)


def _frenado(claves, ahora):
    return any(len([t for t in _FALLOS.get(k, ()) if t > ahora - VENTANA_INTENTOS]) >= INTENTOS_MAX for k in claves)


def _usuario_real(usuario):
    """El usuario tal como esta en la base (las cuentas son NOCASE), y su contrasena guardada; o (None, None)."""
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            fila = con.execute('SELECT usuario, password FROM cuentas WHERE usuario = ? COLLATE NOCASE',
                               (usuario,)).fetchone()
        finally:
            con.close()
    return (fila[0], fila[1] or '') if fila else (None, None)


def login(usuario, pw, ip, lang='en'):
    """(token, datos) o (None, mensaje de error)."""
    usuario = (usuario or '').strip()
    ahora = time.time()
    claves = (('ip', ip), ('usuario', usuario.casefold()))
    with _CERROJO:
        _limpiar(ahora)
        if _frenado(claves, ahora):
            return None, msg('demasiados', lang)
    real, guardado = _usuario_real(usuario) if usuario else (None, None)
    ok = bool(real and guardado.startswith(cuentas.PREFIJO_PW) and cuentas.contrasena_ok(guardado, pw or ''))
    if not ok:
        with _CERROJO:
            for k in claves:
                _FALLOS.setdefault(k, []).append(ahora)
        if real and guardado and not guardado.startswith(cuentas.PREFIJO_PW):
            return None, msg('formato_viejo', lang)
        return None, msg('credenciales', lang)
    token = secrets.token_urlsafe(32)
    with _CERROJO:
        _SESIONES[token] = {'usuario': real, 'exp': ahora + DURACION_SESION}
        for k in claves:
            _FALLOS.pop(k, None)
    log.info('panel: entra %s%s desde %s', real, ' (admin)' if es_admin(real) else '', ip)
    return token, {'usuario': real, 'admin': es_admin(real)}


def sesion(token):
    """El usuario de esa sesion, o None."""
    if not token:
        return None
    with _CERROJO:
        s = _SESIONES.get(token)
        if not s or s['exp'] <= time.time():
            _SESIONES.pop(token, None)
            return None
        return s['usuario']


def logout(token):
    with _CERROJO:
        _SESIONES.pop(token, None)


def es_admin(usuario):
    return configuracion.es_gm(usuario)


# --------------------------------------------------------------------------- datos de la cuenta

_CLASES = None


def nombre_clase(class_id):
    global _CLASES
    if _CLASES is None:
        _CLASES = {}
        f = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'class.xml'
        try:
            for m in re.finditer(r'<class\s+id="(\d+)"\s+name="([^"]*)"', f.read_text(encoding='utf-8', errors='ignore')):
                _CLASES[int(m.group(1))] = m.group(2)
        except OSError:
            pass
    try:
        return _CLASES.get(int(class_id or 0), 'Novice')
    except (TypeError, ValueError):
        return 'Novice'


def nombre_mapa(stage):
    try:
        import clases
        return clases.nombre_de_mapa(int(stage)) or str(stage)
    except Exception:
        return str(stage)


FACCIONES = {'Aurora': 'Aurora', 'Beasts': 'Beasts', 'Steel': 'Steel', 'Shadow': 'Shadow'}


def personajes_de(usuario):
    out = []
    for p in cuentas.lista_de_personajes(usuario):
        out.append({
            'nombre': p.get('nombre', ''),
            'nivel': int(p.get('nivel') or 1),
            'clase': nombre_clase(p.get('class_id')),
            'faccion': FACCIONES.get(p.get('faction'), 'Heaven' if p.get('faction') in (None, '', 'Heaven', 'Graduated',
                                                                                         'Neutral', 'Neutrally') else str(p.get('faction'))),
            'mapa': nombre_mapa(p.get('stage_id') or 0),
            'oro': int(p.get('oro') or 0),
            'ranura': p.get('ranura'),
        })
    return out


def saldo_ag(usuario):
    import item_mall
    return item_mall.saldo(usuario)


def datos_de(usuario):
    return {'usuario': usuario, 'admin': es_admin(usuario), 'ag': saldo_ag(usuario), 'personajes': personajes_de(usuario)}


def cambiar_contrasena(usuario, actual, nueva, confirmar, lang='en'):
    """(ok, mensaje). El propio jugador: pide la actual."""
    real, guardado = _usuario_real(usuario)
    if not real or not guardado.startswith(cuentas.PREFIJO_PW) or not cuentas.contrasena_ok(guardado, actual or ''):
        return False, msg('actual_mal', lang)
    return _poner_contrasena(real, nueva, confirmar, lang)


def _poner_contrasena(usuario, nueva, confirmar, lang):
    if not CONTRASENA_VALIDA.fullmatch(nueva or ''):
        return False, msg('contrasena_mala', lang)
    if confirmar is not None and nueva != confirmar:
        return False, msg('no_coinciden', lang)
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('UPDATE cuentas SET password = ? WHERE usuario = ?', (cuentas.contrasena_hash(nueva), usuario))
            con.commit()
        finally:
            con.close()
    cuentas._notificar_cambio(inmediato=True)
    return True, msg('contrasena_ok', lang)


# --------------------------------------------------------------------------- admin

def _auditar(admin, accion, objetivo, detalle, ip):
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('CREATE TABLE IF NOT EXISTS panel_auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha REAL, '
                        'admin TEXT, accion TEXT, objetivo TEXT, detalle TEXT, ip TEXT)')
            con.execute('INSERT INTO panel_auditoria (fecha, admin, accion, objetivo, detalle, ip) VALUES (?,?,?,?,?,?)',
                        (time.time(), admin, accion, objetivo, json.dumps(detalle, ensure_ascii=False), ip))
            con.commit()
        finally:
            con.close()
    log.info('panel admin %s: %s %s %s (%s)', admin, accion, objetivo, detalle, ip)


def buscar_cuenta(q, lang='en'):
    """La cuenta por usuario o por nombre de personaje. (datos, None) o (None, mensaje)."""
    q = (q or '').strip()
    if not q:
        return None, msg('no_existe', lang)
    real, _ = _usuario_real(q)
    if not real:
        pj = cuentas.personaje_por_nombre(q)
        real = pj[0] if pj else None
    if not real:
        return None, msg('no_existe', lang)
    return datos_de(real), None


def dar_ag(admin, usuario, cantidad, motivo, ip, lang='en'):
    """(ok, mensaje, saldo nuevo). Cantidad negativa quita, sin dejar el saldo por debajo de 0."""
    real, _ = _usuario_real((usuario or '').strip())
    if not real:
        return False, msg('no_existe', lang), None
    try:
        cantidad = int(cantidad)
    except (TypeError, ValueError):
        return False, msg('cantidad_mala', lang), None
    if not cantidad or abs(cantidad) > AG_MAX_POR_ACCION:
        return False, msg('cantidad_mala', lang), None
    import item_mall
    with cuentas._LOCK, cuentas._get_conn() as con:
        item_mall._schema(con)
        antes = item_mall._wallet(con, real)
        if antes + cantidad < 0:
            return False, msg('sin_saldo', lang), antes
        con.execute('UPDATE item_mall_wallet SET ag = ag + ? WHERE usuario = ?', (cantidad, real))
        con.execute('INSERT INTO item_mall_movimientos (id, usuario, delta, motivo, referencia, fecha) VALUES (?,?,?,?,?,?)',
                    ('panel:%s' % secrets.token_hex(8), real, cantidad, 'panel:%s' % admin, None, time.time()))
        nuevo = int(con.execute('SELECT ag FROM item_mall_wallet WHERE usuario = ?', (real,)).fetchone()[0])
    _auditar(admin, 'ag', real, {'cantidad': cantidad, 'antes': antes, 'despues': nuevo, 'motivo': (motivo or '')[:200]}, ip)
    return True, msg('ag_ok', lang, real, '{:,}'.format(nuevo)), nuevo


def reset_contrasena(admin, usuario, nueva, ip, lang='en'):
    real, _ = _usuario_real((usuario or '').strip())
    if not real:
        return False, msg('no_existe', lang)
    ok, texto = _poner_contrasena(real, nueva, None, lang)
    if not ok:
        return ok, texto
    _auditar(admin, 'contrasena', real, {}, ip)
    return True, msg('reset_ok', lang, real)


# --------------------------------------------------------------------------- calendario

def _proximas(weekday, hora, minuto, ahora, n=2):
    """Las proximas n fechas (hora del servidor) de ese dia de la semana (lunes = 0) y hora."""
    out = []
    base = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    for d in range(0, 15):
        t = base + dt.timedelta(days=d)
        if t.weekday() == weekday and t > ahora - dt.timedelta(hours=3):
            out.append(t)
        if len(out) >= n:
            break
    return out


def eventos(ahora=None):
    """Los eventos programados del servidor, con sus proximas fechas en epoch (UTC) y duracion en minutos.
    Cada modulo usa su convencion: Totem War y Holy cuentan el lunes como 0; los diarios, el domingo."""
    ahora = ahora or dt.datetime.now()
    filas = []

    def poner(clave, nombre_en, nombre_es, weekday, hora, minuto, duracion):
        for t in _proximas(weekday, hora, minuto, ahora):
            filas.append({'evento': clave, 'en': nombre_en, 'es': nombre_es, 'inicio': t.timestamp(),
                          'duracion': int(duracion)})

    try:
        import totem_war
        for dia, h, m in totem_war.HORARIO:
            poner('totem_war', 'Totem War', 'Totem War', dia, h, m, totem_war.DURACION_HORARIO)
    except Exception:
        log.exception('calendario: Totem War')
    try:
        cfg = json.loads((RAIZ / 'server' / 'plantillas' / 'competiciones_config.json').read_text(encoding='utf-8'))
        hh = cfg.get('holy_horario') or {}
        for dia in hh.get('dias') or ():
            for h in hh.get('horas') or ():
                poner('holy', 'Holy Battlefield', 'Holy Battlefield', int(dia), int(h), 0, hh.get('duracion_min', 60))
    except Exception:
        log.exception('calendario: Holy')
    try:
        ds = json.loads((RAIZ / 'server' / 'plantillas' / 'daily_schedule.json').read_text(encoding='utf-8'))
        for slot in ds.get('slots') or ():
            h, m = (int(x) for x in str(slot['start']).split(':'))
            poner('daily_' + str(slot.get('alias', '')), 'Daily event (%s)' % slot.get('alias', ''),
                  'Evento diario (%s)' % slot.get('alias', ''), (int(slot['day']) - 1) % 7, h, m,
                  ds.get('duration_minutes', 30))
    except Exception:
        log.exception('calendario: eventos diarios')
    filas.sort(key=lambda f: f['inicio'])
    return filas


# --------------------------------------------------------------------------- HTTP (lo llama web_registro.Handler)

def _token_de(handler):
    for parte in (handler.headers.get('Cookie') or '').split(';'):
        k, _, v = parte.strip().partition('=')
        if k == COOKIE:
            return v
    return None


def _origen_ok(handler):
    """POST solo desde el propio sitio: Origin (o Referer) con el mismo host que la peticion."""
    host = (handler.headers.get('X-Forwarded-Host') or handler.headers.get('Host') or '').split(':')[0].lower()
    origen = handler.headers.get('Origin') or handler.headers.get('Referer') or ''
    m = re.match(r'^https?://([^/:]+)', origen)
    return bool(host and m and m.group(1).lower() == host)


def _cookie(token, max_age):
    return '%s=%s; Path=/api/panel/; HttpOnly; Secure; SameSite=Strict; Max-Age=%d' % (COOKIE, token, max_age)


def atender(handler, metodo, ruta, consulta):
    """Atiende /api/panel/*. handler es el BaseHTTPRequestHandler; usa handler._json(codigo, cuerpo, cabeceras)."""
    ip = handler.headers.get('X-Real-IP') or handler.client_address[0]
    cuerpo = {}
    if metodo == 'POST':
        if 'application/json' not in (handler.headers.get('Content-Type') or '') or not _origen_ok(handler):
            return handler._json(403, {'ok': False, 'mensaje': msg('invalida')})
        largo = int(handler.headers.get('Content-Length') or 0)
        if largo <= 0 or largo > 4096:
            return handler._json(400, {'ok': False, 'mensaje': msg('invalida')})
        try:
            cuerpo = json.loads(handler.rfile.read(largo).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            cuerpo = None
        if not isinstance(cuerpo, dict):
            return handler._json(400, {'ok': False, 'mensaje': msg('invalida')})
    lang = str(cuerpo.get('lang') or (consulta.get('lang') or ['en'])[0])
    lang = 'es' if lang == 'es' else 'en'

    if metodo == 'POST' and ruta == '/api/panel/login':
        token, datos = login(str(cuerpo.get('usuario', '')), str(cuerpo.get('password', '')), ip, lang)
        if not token:
            return handler._json(200, {'ok': False, 'mensaje': datos})
        return handler._json(200, {'ok': True, **datos}, {'Set-Cookie': _cookie(token, DURACION_SESION)})
    if metodo == 'GET' and ruta == '/api/panel/eventos':
        return handler._json(200, {'ok': True, 'eventos': eventos(), 'ahora': time.time()})

    token = _token_de(handler)
    usuario = sesion(token)
    if metodo == 'POST' and ruta == '/api/panel/logout':
        logout(token)
        return handler._json(200, {'ok': True}, {'Set-Cookie': _cookie('', 0)})
    if not usuario:
        return handler._json(401, {'ok': False, 'mensaje': msg('sin_sesion', lang)})

    if metodo == 'GET' and ruta == '/api/panel/yo':
        return handler._json(200, {'ok': True, **datos_de(usuario)})
    if metodo == 'POST' and ruta == '/api/panel/contrasena':
        ok, texto = cambiar_contrasena(usuario, str(cuerpo.get('actual', '')), str(cuerpo.get('nueva', '')),
                                       str(cuerpo.get('confirmar', '')), lang)
        return handler._json(200, {'ok': ok, 'mensaje': texto})

    if ruta.startswith('/api/panel/admin/'):
        if not es_admin(usuario):
            return handler._json(403, {'ok': False, 'mensaje': msg('no_admin', lang)})
        if metodo == 'GET' and ruta == '/api/panel/admin/cuenta':
            datos, error = buscar_cuenta((consulta.get('q') or [''])[0], lang)
            return handler._json(200, {'ok': True, **datos} if datos else {'ok': False, 'mensaje': error})
        if metodo == 'POST' and ruta == '/api/panel/admin/ag':
            ok, texto, nuevo = dar_ag(usuario, cuerpo.get('usuario'), cuerpo.get('cantidad'), cuerpo.get('motivo'), ip, lang)
            return handler._json(200, {'ok': ok, 'mensaje': texto, 'ag': nuevo})
        if metodo == 'POST' and ruta == '/api/panel/admin/contrasena':
            ok, texto = reset_contrasena(usuario, cuerpo.get('usuario'), str(cuerpo.get('nueva', '')), ip, lang)
            return handler._json(200, {'ok': ok, 'mensaje': texto})
    return handler._json(404, {'ok': False, 'mensaje': msg('invalida', lang)})
