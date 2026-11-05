"""Aviso a todos los jugadores antes de reiniciar el servidor (05/11/2026): "habilita una opcion para enviar mensajes
antes de reiniciar el server diciendo habra una actualizacion pronto por favor desconecta".

Comandos GM (consola o data/gm.txt, una linea por comando):
    reinicio <minutos>    cuenta atras: avisa ya y luego a los 10, 5, 3, 2 y 1 minutos y a los 30 s
    reinicio cancelar     corta la cuenta atras (y avisa de que no hay reinicio)
    (para un mensaje cualquiera a todos esta el /notice <texto> de siempre)

El aviso es el cartel que cruza la parte de arriba de la pantalla (totem_war.cartel_deslizante, 0x0128 canal 0, que
el cliente tambien copia al chat). El reinicio en si lo hacen los scripts de subida (tools/subir_servidor.py y
tools/publicar_setting.py con --avisar N, que escriben el comando en el gm.txt del VPS y esperan los N minutos).
"""
import asyncio
import logging

log = logging.getLogger('aviso_reinicio')

MENSAJE = ('[Server] A game update is coming soon: the server will restart in %s. Please log out now to keep your '
           'progress safe. / Habra una actualizacion pronto: el servidor se reinicia en %s. Por favor desconectate.')
CANCELADO = '[Server] The scheduled restart was cancelled. / Se cancelo el reinicio programado.'
MARCAS_S = (600, 300, 180, 120, 60, 30)        # cuando se repite el aviso, en segundos que faltan
MAX_MINUTOS = 120

_pendientes = []                               # los call_later de la cuenta atras en curso


def _cuanto(segundos: int) -> str:
    if segundos >= 60:
        m = segundos // 60
        return '%d minute%s' % (m, '' if m == 1 else 's')
    return '%d seconds' % segundos


def _cuanto_es(segundos: int) -> str:
    if segundos >= 60:
        m = segundos // 60
        return '%d minuto%s' % (m, '' if m == 1 else 's')
    return '%d segundos' % segundos


def difundir(texto: str) -> int:
    """El cartel a todos los que estan en el mundo. Devuelve a cuantos."""
    import app
    import totem_war
    sesiones = app._tw_sesiones()
    app._tw_difundir(totem_war.cartel_deslizante(texto))
    return len(sesiones)


def texto_para(segundos: int) -> str:
    return MENSAJE % (_cuanto(segundos), _cuanto_es(segundos))


def cancelar() -> bool:
    hubo = bool(_pendientes)
    for h in _pendientes:
        h.cancel()
    _pendientes.clear()
    return hubo


def programar(minutos: float, loop=None) -> list:
    """Avisa ahora y deja programados los siguientes. Devuelve los segundos que faltaran en cada aviso."""
    cancelar()
    total = int(round(float(minutos) * 60))
    if total <= 0:
        return []
    loop = loop or asyncio.get_event_loop()
    avisos = [total] + [m for m in MARCAS_S if m < total]
    for queda in avisos:
        demora = total - queda

        def _avisar(q=queda):
            n = difundir(texto_para(q))
            log.info('aviso de reinicio (faltan %ds) a %d jugadores', q, n)

        if demora == 0:
            _avisar()
        else:
            _pendientes.append(loop.call_later(demora, _avisar))
    return avisos


def comando(partes) -> str:
    """Lo que hace el comando GM; devuelve la respuesta para la consola o el log."""
    if not partes:
        return 'uso: reinicio <minutos> | reinicio cancelar'
    cmd, args = partes[0].lower(), partes[1:]
    if cmd == 'aviso':
        texto = ' '.join(args).strip()
        if not texto:
            return 'uso: aviso <texto>'
        return 'aviso enviado a %d jugadores' % difundir('[Server] ' + texto)
    if args and args[0].lower() in ('cancelar', 'cancel', 'stop'):
        if cancelar():
            difundir(CANCELADO)
            return 'cuenta atras cancelada'
        return 'no habia cuenta atras'
    try:
        minutos = float(args[0]) if args else 5.0
    except ValueError:
        return 'uso: reinicio <minutos>'
    if not 0 < minutos <= MAX_MINUTOS:
        return 'los minutos van de 0 a %d' % MAX_MINUTOS
    avisos = programar(minutos)
    return 'reinicio avisado: %s (avisos a falta de %s s)' % (_cuanto(int(minutos * 60)), ', '.join(map(str, avisos)))
