"""Objetos de peluqueria: Height Potion, Magic Comb, Hair Color Potion y
Complexion Potion (7033..7036, y sus copias intransferibles 8895..8898).

El cliente NO manda el 0x002E al usarlos. Angel.exe 0x5BD953 los busca en la
tabla de 0x60E040 y abre su ventana (CreateSalonWnd); al confirmar, la nativa
salonok (0x60ECD0) manda C2S 0x002F [u8 0x25][u32 item][u32 opcion].

Cada objeto toca un byte de los cinco de la apariencia, que en el cliente son
+0x240..+0x244 del personaje, y el servidor lo avisa con el 0x0013 cuyo
atributo cae en la tabla de 0x5FBE94 (base +0x3EE8, 16 B por atributo).
"""
import logging
import struct

log = logging.getLogger('salon')

SUBTIPO = 0x25

# item -> (posicion en p.apariencia, atributo del 0x0013, opciones)
# Las opciones son las del cliente: 0x54C470 limita la lista a 3, 12, 36 y 26.
OBJETOS = {
    7033: (2, 62, 3), 8895: (2, 62, 3),      # altura
    7034: (1, 36, 12), 8896: (1, 36, 12),    # peinado
    7035: (3, 37, 36), 8897: (3, 37, 36),    # color de pelo
    7036: (4, 38, 26), 8898: (4, 38, 26),    # color de piel
}

APARIENCIA_POR_DEFECTO = [0, 0, 0, 8, 8]


def procesar(ses, cuerpo) -> bool:
    """True si el 0x002F era de la peluqueria (lo haya aplicado o no)."""
    if len(cuerpo) < 9 or cuerpo[0] != SUBTIPO:
        return False
    import app
    import clases
    import combate
    import cuentas
    import presencia
    import recent_mall
    item, opcion = struct.unpack_from('<II', cuerpo, 1)
    p = ses.personaje

    def aviso(texto):
        ses.enviar(clases.aviso(texto, tipo=0))

    datos = OBJETOS.get(item)
    if datos is None:
        log.info('[%s] peluqueria: item %s desconocido (opcion %s)', getattr(ses, 'addr', '?'), item, opcion)
        return True
    pos, atributo, opciones = datos
    tope = app._tope_bolsa(ses.inventario)
    casilla = next((s for s, v in sorted(ses.inventario.items())
                    if int(v) == item and 20 <= s <= tope), None)
    if casilla is None:
        aviso('Failed to change your appearance without the right props.')
        return True
    if not 0 <= opcion < opciones:
        aviso('Failed to change your appearance because you chose the wrong one.')
        return True
    apariencia = (list(getattr(p, 'apariencia', None) or APARIENCIA_POR_DEFECTO) + APARIENCIA_POR_DEFECTO)[:5]
    if apariencia[pos] == opcion:
        aviso('Failed to change your appearance. There is no change.')
        return True
    try:
        recent_mall.cambiar(ses, {casilla: 1}, [])
    except recent_mall.Rechazo as exc:
        aviso(str(exc))
        return True
    apariencia[pos] = opcion
    p.apariencia = apariencia
    if getattr(ses, 'usuario', None):
        cuentas.guardar_apariencia(ses.usuario, p.char_id, apariencia)
    ses.enviar(combate.atributo(p.entity_id, opcion, atributo))
    presencia.notificar_equipo(ses)
    aviso('Appearance changed successfully.')
    log.info('[%s] peluqueria: %s -> apariencia[%d] = %d %s',
             getattr(ses, 'addr', '?'), app._nombre_item(item), pos, opcion, apariencia)
    return True
