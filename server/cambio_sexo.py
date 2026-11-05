"""Gender Bolus (7032): cambia el sexo del personaje (04/11/2026, "no funciona el cambio de sexo").

El cliente no manda el 0x002E al usarlo: Angel.exe abre su confirmacion (ventana 12174, texto 2123 "Change your
gender? Your gender will change and you will have the default hairstyle.") y al aceptar, 0x60DFA0 llama a
0x614DA0(0x24, casilla), o sea C2S 0x0016 [u8 0x24][u32 casilla del objeto] (la 0x23 es la del cambio de faccion,
que comparte la ventana). Nadie contestaba esa accion y no pasaba nada.

El sexo es el primer byte de la apariencia (p.apariencia[0], 1 = hombre; ver personajes.py) y en el cliente el
+0x240 del personaje. Se le avisa con el 0x0013 de atributo 35, cuyo manejador (0x5FDFC0, el 4o de la tabla de
0x5FBE94: base +0x3EE8, 16 B por atributo, 0x4118 = 35) pone el sexo y deja el peinado en 0, el de por defecto.
"""
import logging

log = logging.getLogger('cambio_sexo')

ACCION = 0x24
ITEMS = frozenset((7032,))
ATRIBUTO_SEXO = 35
ATRIBUTO_PEINADO = 36
APARIENCIA_POR_DEFECTO = [0, 0, 0, 8, 8]


def equipo_que_no_vale(bolsa, hombre: bool):
    """Las casillas de equipo puestas con ropa del otro sexo (男女裝備 限男性 / 限女性)."""
    import house_services
    import inventario
    filas = house_services.xml_rows('item.xml')
    pide = '限女性' if hombre else '限男性'      # lo que deja de valer al cambiar
    malas = []
    for ranura, item in (bolsa or {}).items():
        try:
            r, i = int(ranura), int(item)
        except (TypeError, ValueError):
            continue
        if inventario.es_equipo(r) and (filas.get(i) or {}).get('男女裝備') == pide:
            malas.append(r)
    return sorted(malas)


def procesar(ses, casilla) -> bool:
    """Aplica el cambio con el objeto de esa casilla. True si se cambio."""
    import app
    import clases
    import combate
    import cuentas
    import presencia

    p = ses.personaje

    def aviso(texto):
        ses.enviar(clases.aviso(texto, tipo=0))

    # El parametro puede ser la casilla o el id del objeto (con el Gender Bolus llega el 7032, 04/11/2026): si no
    # es una casilla con el objeto, se busca la primera que lo tenga.
    item = ses.inventario.get(casilla)
    if item is None or int(item) not in ITEMS:
        quiere = int(casilla) if int(casilla) in ITEMS else None
        casilla = next((s for s in app._ranuras_bolsa(ses.inventario)
                        if s in ses.inventario and int(ses.inventario[s]) in ITEMS
                        and (quiere is None or int(ses.inventario[s]) == quiere)), None)
        item = ses.inventario.get(casilla) if casilla is not None else None
    log.info('[%s] Gender Bolus: parametro -> casilla %s (item %s)', getattr(ses, 'addr', '?'), casilla, item)
    if item is None or int(item) not in ITEMS or not 20 <= int(casilla) <= app._tope_bolsa(ses.inventario):
        aviso('Failed to change your gender without the right props.')
        return False
    apariencia = (list(getattr(p, 'apariencia', None) or APARIENCIA_POR_DEFECTO) + APARIENCIA_POR_DEFECTO)[:5]
    hombre = bool(int(apariencia[0]) & 1)
    # Lo que diga su descripcion: "you will be unable to use some items and equipment which gender limitations".
    # Para no dejar puesta ropa que ya no le corresponde, se pide quitarla antes.
    malas = equipo_que_no_vale(ses.inventario, not hombre)
    if malas:
        aviso('Please take off your gender-limited equipment before changing your gender.')
        return False
    app._sacar(ses, casilla, 1)
    apariencia[0] = 0 if hombre else 1
    apariencia[1] = 0                                   # el peinado por defecto, como hace el cliente
    p.apariencia = apariencia
    if getattr(ses, 'usuario', None):
        cuentas.guardar_apariencia(ses.usuario, p.char_id, apariencia)
        app._guardar_bolsa(ses, p.char_id)
    ses.enviar(*app._refrescar(ses, [casilla]),
               combate.atributo(p.entity_id, apariencia[0], ATRIBUTO_SEXO),
               combate.atributo(p.entity_id, 0, ATRIBUTO_PEINADO))
    presencia.notificar_equipo(ses)
    aviso('Your gender has been changed.')
    log.info('[%s] %s cambia de sexo: %s -> %s %s', getattr(ses, 'addr', '?'), p.nombre,
             'hombre' if hombre else 'mujer', 'mujer' if hombre else 'hombre', apariencia)
    return True
