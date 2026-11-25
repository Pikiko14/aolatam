"""Misiones diarias y semanales con racha (25/11/2026): "gana 1 MOBA, mata 200 monstruos, completa Pet Defense, con
mas premio si las haces varios dias seguidos". (misiones.py son las misiones del juego; esto es aparte.)

* CADA DIA salen 'por_dia' misiones de plantillas/misiones_diarias.json "diarias" y cada semana 'por_semana' de
  "semanales", las mismas para todos (sorteo con la fecha de semilla; como mucho una del MOBA). Se cuentan solas
  (sumar): monstruos y jefes (app, al morir el monstruo: al_matar), partidas del MOBA (moba_ranking.registrar), Pet
  Defense (pet_defense_partida.terminar), pisos de la Torre de Babel (torre_babel.al_morir) y el jefe de mundo
  (jefe_mundo.al_morir).
* AL CUMPLIR UNA se cobra sola: EXP (en partes de lo que pide el nivel), oro (por nivel) e items, todo por el
  multiplicador de la racha. Con TODAS las del dia hechas, la racha sube 1 (si ayer tambien; si no, vuelve a 1) y en
  los dias de "racha.premios" (del ciclo de 'ciclo' dias) hay premio de mas.
* EL PANEL (25/11/2026, "que tengamos algun panel para las diarias"): la ventana 58800 (tools/ventana_misiones.py,
  server/lua/misiones.lua), con el boton 59007 de la barra o /missions: el reinicio, la racha y su proximo premio, y
  cada mision con su progreso y su barra. Se refresca sola mientras esta abierta. Sin el parche del cliente (la ventana
  no se crea), /missions lo da por el chat. Al conectar, un recordatorio por el chat.
* c2s 0x002F [u8 176][u32 a][u32 b]: a = 1 abrir (el boton de la barra), 0 se cerro con la X, 8/9 se creo o no.
* data/misiones_diarias.db: progreso (char_id, periodo, mision, valor, cobrada) y racha (char_id, ultimo_dia, dias).
"""
import datetime as dt
import json
import logging
import pathlib
import random
import sqlite3
import struct
import threading

import canal_lua

log = logging.getLogger('misiones_diarias')

CMD_MD = 176
# Lo que define el cliente al saludar (subasta_ventana.procesar): el boton de la barra (59007) llama a esto.
SALUDO_LUA = ('function OnCommandMisiones(dwID, dwCmdID, dwParam, pParam) '
              'game.netcommand2(%d, 1, 0) return 1 end' % CMD_MD)

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'misiones_diarias.json'
DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'misiones_diarias.db'
_LOCK = threading.RLock()


def config():
    return json.loads(RUTA.read_text('utf-8'))


def _con():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('CREATE TABLE IF NOT EXISTS progreso (char_id INTEGER, periodo TEXT, mision TEXT, valor INTEGER, '
                'cobrada INTEGER DEFAULT 0, PRIMARY KEY (char_id, periodo, mision))')
    con.execute('CREATE TABLE IF NOT EXISTS racha (char_id INTEGER PRIMARY KEY, ultimo_dia TEXT, dias INTEGER)')
    return con


def _hoy(ahora=None):
    if ahora is not None:
        return ahora
    import calendario
    return calendario._ahora()


def periodos(ahora=None):
    """('d:2026-11-25', 'w:2026-W48')."""
    a = _hoy(ahora)
    y, w, _ = a.isocalendar()
    return 'd:' + a.date().isoformat(), 'w:%d-W%02d' % (y, w)


def _sorteo(periodo, pool, cuantas):
    rng = random.Random('misiones ' + periodo)
    out, moba = [], False
    for m in rng.sample(pool, len(pool)):
        es_moba = m['tipo'].startswith('moba')
        if es_moba and moba:
            continue
        moba = moba or es_moba
        out.append(m)
        if len(out) >= cuantas:
            break
    return out


def de_hoy(ahora=None):
    """[(periodo, mision)] de hoy y de la semana; mision = {'id', 'tipo', 'n', 'texto'}."""
    cfg = config()
    d, w = periodos(ahora)
    return ([(d, m) for m in _sorteo(d, cfg['diarias'], int(cfg.get('por_dia', 3)))]
            + [(w, m) for m in _sorteo(w, cfg['semanales'], int(cfg.get('por_semana', 3)))])


def _valores(con, cid, periodo):
    return {m: (v, c) for m, v, c in con.execute('SELECT mision, valor, cobrada FROM progreso WHERE char_id=? AND '
                                                 'periodo=?', (cid, periodo))}


def racha(cid, ahora=None):
    """Los dias seguidos con todas las diarias hechas (0 si se corto: el ultimo fue antes de ayer)."""
    with _LOCK:
        con = _con()
        try:
            fila = con.execute('SELECT ultimo_dia, dias FROM racha WHERE char_id=?', (cid,)).fetchone()
        finally:
            con.close()
    if not fila:
        return 0
    return int(fila[1]) if (_hoy(ahora).date() - dt.date.fromisoformat(fila[0])).days <= 1 else 0


def multiplicador(dias):
    r = config()['racha']
    return min(float(r.get('tope', 2.0)), 1.0 + float(r.get('por_dia', 0.1)) * max(0, dias - 1))


def _aviso(ses, texto):
    import clases
    try:
        ses.enviar(clases.aviso(texto, tipo=0, msg_id=clases.MSG_TEXTO))
    except Exception:
        log.debug('misiones diarias: aviso', exc_info=True)


def _cobrar(ses, premio, mult, rng=None):
    """Da el premio (exp en partes del nivel, oro por nivel, items con su probabilidad), por el multiplicador."""
    import app
    import combate
    import trade_routes
    rng = rng or random
    p = ses.personaje
    exp = int((combate.exp_para_nivel(p.nivel + 1) - combate.exp_para_nivel(p.nivel)) * float(premio.get('exp', 0))
              * mult)
    oro = int(float(premio.get('oro_por_nivel', 0)) * max(1, int(p.nivel)) * mult)
    items = [int(rng.choice(it['de'])) for it in premio.get('items') or [] if rng.random() < float(it.get('prob', 1))]
    if exp > 0:
        app._dar_exp_y_creditos(ses, exp=exp)
    if oro > 0:
        trade_routes._cambiar_oro(ses, oro)
    for it in items:
        app._gm_dar_item(ses, it, 1)
    return exp, oro, items


def _subir_racha(cid, ahora=None):
    hoy = _hoy(ahora).date()
    with _LOCK:
        con = _con()
        try:
            fila = con.execute('SELECT ultimo_dia, dias FROM racha WHERE char_id=?', (cid,)).fetchone()
            if fila and fila[0] == hoy.isoformat():
                return int(fila[1])
            dias = int(fila[1]) + 1 if fila and (hoy - dt.date.fromisoformat(fila[0])).days == 1 else 1
            con.execute('INSERT OR REPLACE INTO racha VALUES (?,?,?)', (cid, hoy.isoformat(), dias))
            con.commit()
            return dias
        finally:
            con.close()


def sumar(ses, tipo, cuanto=1, ahora=None):
    """Suma `cuanto` a las misiones de ese tipo de hoy y de la semana; cobra las que se cumplan. [(periodo, mision)]."""
    p = getattr(ses, 'personaje', None)
    cid = int(getattr(p, 'char_id', 0) or 0) if p is not None else 0
    if not cid or cuanto <= 0:
        return []
    todas_hoy = de_hoy(ahora)
    misiones = [(per, m) for per, m in todas_hoy if m['tipo'] == tipo]
    if not misiones:
        return []
    dia = periodos(ahora)[0]
    cumplidas, todas = [], False
    with _LOCK:
        con = _con()
        try:
            for per, m in misiones:
                v, cobrada = _valores(con, cid, per).get(m['id'], (0, 0))
                if cobrada:
                    continue
                v = min(int(m['n']), v + int(cuanto))
                hecha = v >= int(m['n'])
                con.execute('INSERT OR REPLACE INTO progreso VALUES (?,?,?,?,?)', (cid, per, m['id'], v, int(hecha)))
                if hecha:
                    cumplidas.append((per, m))
            con.commit()
            if any(per == dia for per, _m in cumplidas):
                hechas = _valores(con, cid, dia)
                todas = all(hechas.get(m['id'], (0, 0))[1] for per, m in todas_hoy if per == dia)
        finally:
            con.close()
    _refrescar(ses, ahora)
    if not cumplidas:
        return []
    dias = _subir_racha(cid, ahora) if todas else racha(cid, ahora)
    mult = multiplicador(max(1, dias))
    cfg = config()
    for per, m in cumplidas:
        diaria = per[0] == 'd'
        try:
            exp, oro, items = _cobrar(ses, cfg['premio_diaria' if diaria else 'premio_semanal'], mult)
            _aviso(ses, '[%s mission] %s: done! +%d EXP, +%d gold%s.' % (
                'Daily' if diaria else 'Weekly', m['texto'], exp, oro,
                (', +%d item%s' % (len(items), '' if len(items) == 1 else 's')) if items else ''))
        except Exception:
            log.exception('misiones diarias: premio')
    if todas:
        _premio_racha(ses, dias)
    _refrescar(ses, ahora)
    return cumplidas


def _premio_racha(ses, dias):
    r = config()['racha']
    texto = '[Daily missions] All done today! Streak: %d day%s (rewards x%.1f).' % (
        dias, '' if dias == 1 else 's', multiplicador(dias))
    premio = (r.get('premios') or {}).get(str((dias - 1) % int(r.get('ciclo', 7)) + 1))
    if premio:
        try:
            _exp, _oro, items = _cobrar(ses, premio, 1.0)
            if items:
                texto += ' Streak bonus: +%d item%s!' % (len(items), '' if len(items) == 1 else 's')
        except Exception:
            log.exception('misiones diarias: premio de racha')
    _aviso(ses, texto)


def lineas(ses, ahora=None):
    cid = int(ses.personaje.char_id)
    out = []
    with _LOCK:
        con = _con()
        try:
            vals = {}
            for per, m in de_hoy(ahora):
                if per not in vals:
                    vals[per] = _valores(con, cid, per)
                v, hecha = vals[per].get(m['id'], (0, 0))
                out.append('%s %s: %d/%d%s' % ('[Daily]' if per[0] == 'd' else '[Weekly]', m['texto'], v, int(m['n']),
                                               ' (done)' if hecha else ''))
        finally:
            con.close()
    dias = racha(cid, ahora)
    out.append('Streak: %d day%s (rewards x%.1f). Finish all the daily missions every day to keep it.' % (
        dias, '' if dias == 1 else 's', multiplicador(max(1, dias))))
    return out


def _falta(segundos):
    h, m = divmod(max(0, int(segundos)) // 60, 60)
    d, h = divmod(h, 24)
    return ('%dd %dh' % (d, h)) if d else ('%dh %02dm' % (h, m))


def vista(ses, ahora=None):
    """(titulo, racha, racha2, pie, filas) del panel; filas = [[texto, estado, porcentaje]] (diarias y semanales)."""
    a = _hoy(ahora)
    cid = int(ses.personaje.char_id)
    manana = (a + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    lunes = manana + dt.timedelta(days=(7 - manana.weekday()) % 7)
    titulo = 'Daily reset in %s   |   Weekly reset in %s' % (_falta((manana - a).total_seconds()),
                                                             _falta((lunes - a).total_seconds()))
    filas, hechas_hoy = [], 0
    with _LOCK:
        con = _con()
        try:
            vals = {}
            for per, m in de_hoy(ahora):
                if per not in vals:
                    vals[per] = _valores(con, cid, per)
                v, hecha = vals[per].get(m['id'], (0, 0))
                n = int(m['n'])
                hechas_hoy += int(bool(hecha) and per[0] == 'd')
                filas.append([m['texto'], 'Done!' if hecha else '%d / %d' % (v, n), int(100 * min(v, n) / max(1, n))])
        finally:
            con.close()
    r = config()['racha']
    dias = racha(cid, ahora)
    hoy_cuenta = _hecho_hoy(cid, ahora)
    if dias:
        linea = 'Streak: %d day%s   -   rewards x%.1f%s' % (dias, '' if dias == 1 else 's', multiplicador(dias),
                                                           '' if hoy_cuenta else '   -   finish today to keep it!')
    else:
        linea = 'No streak yet: finish all the daily missions (%d/%d today) to start one.' % (
            hechas_hoy, int(config().get('por_dia', 3)))
    ciclo = int(r.get('ciclo', 7))
    premios = sorted((int(k), v) for k, v in (r.get('premios') or {}).items())
    racha2 = 'Streak bonus: ' + ', '.join('day %d %s' % (k, v.get('texto', 'bonus')) for k, v in premios) + '.'
    if premios:
        # El siguiente dia de racha es el dias + 1: hoy si aun faltan las de hoy, manana si ya estan.
        n = dias + 1
        d = next(d for d in range(n, n + ciclo) if (d - 1) % ciclo + 1 in dict(premios))
        falta = d - n + (1 if hoy_cuenta else 0)
        racha2 += ('  Next: today!' if falta == 0 else '  Next in %d day%s.' % (falta, '' if falta == 1 else 's'))
    return titulo, linea, racha2, config().get('pie', ''), filas


def _hecho_hoy(cid, ahora=None):
    with _LOCK:
        con = _con()
        try:
            fila = con.execute('SELECT ultimo_dia FROM racha WHERE char_id=?', (cid,)).fetchone()
        finally:
            con.close()
    return bool(fila) and fila[0] == _hoy(ahora).date().isoformat()


def abrir(ses):
    ses._md_abierto = True
    ses.enviar(canal_lua.paquete((canal_lua.CARPETA / 'misiones.lua').read_text(encoding='utf-8')),
               canal_lua.llamar('MDAbrir', *vista(ses)))


def _refrescar(ses, ahora=None):
    if getattr(ses, '_md_abierto', False):
        try:
            ses.enviar(canal_lua.llamar('MDDatos', *vista(ses, ahora)))
        except Exception:
            log.debug('misiones diarias: refrescar el panel', exc_info=True)


def comando(ses):
    """/missions: el panel (o el chat, si el cliente no tiene la ventana)."""
    abrir(ses)


def comando_chat(ses):
    for linea in lineas(ses):
        _aviso(ses, linea)


def procesar(ses, cuerpo) -> bool:
    """El 0x002F del panel. True si era suyo."""
    if len(cuerpo) < 9 or cuerpo[0] != CMD_MD or getattr(ses, 'personaje', None) is None:
        return False
    a, b = struct.unpack_from('<II', cuerpo, 1)
    if a == 1:
        abrir(ses)
    elif a == 0:
        ses._md_abierto = False
    elif a == 9:
        ses._md_abierto = False
        log.info('%s: sin la ventana de misiones (cliente sin parche): por el chat', ses.personaje.nombre)
        comando_chat(ses)
    return True


def al_conectar(ses):
    if getattr(ses, '_misiones_saludado', False) or getattr(ses, 'personaje', None) is None:
        return
    ses._misiones_saludado = True
    hechas = sum(1 for linea in lineas(ses) if linea.startswith('[Daily]') and linea.endswith('(done)'))
    _aviso(ses, 'Daily missions: %d/%d done. Type /missions to see them.' % (hechas, int(config().get('por_dia', 3))))


def al_matar(ses, m):
    """Un monstruo cayo (app): cuenta para quien lo mato; si es jefe, para todos los que le pegaron."""
    import app
    import combate
    sumar(ses, 'matar')
    if combate.es_jefe(int(getattr(m, 'npc_type', 0) or 0)) or getattr(m, 'jefe_mundo', False):
        cids = {int(c) for c, d in (getattr(m, 'dano_por', None) or {}).items() if int(d) > 0}
        cids.add(int(getattr(getattr(ses, 'personaje', None), 'char_id', 0) or 0))
        for s in app._tw_sesiones():
            if int(getattr(getattr(s, 'personaje', None), 'char_id', 0) or 0) in cids:
                sumar(s, 'jefe')
