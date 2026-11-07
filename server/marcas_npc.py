"""[!] delante del nombre de los NPC que tienen una mision para ti (06/11/2026).

"podriamos colocar en los mapas un simbolo de Informacion en los npc que dan quest??": el mapa lo pinta el cliente y
no se le puede anadir un icono sin parchear el ejecutable, pero el nombre del NPC viaja en su 0x0008 (offset 16, 16
bytes con el cero detras), igual que el de las mascotas. Se reescribe al mandarlo, por jugador: solo lleva la marca
si misiones.misiones_disponibles_npc le ofrece alguna que aun no ha hecho. Sale sobre la cabeza y en el mapa.

Se calcula al entrar al mapa (cuando el servidor manda los NPC); al aceptar o entregar se actualiza con refrescar().
"""
import logging
import struct

log = logging.getLogger('marcas_npc')

MARCA = '[!]'
LARGO_NOMBRE = 16
KLASS_MONSTRUO = 1
KLASS_INVOCACION = 38

# entity_id -> [bytes originales del 0x0008, nombre sin marca, marcado] de lo ultimo que se mando a cada sesion
_ULTIMOS = {}


def _es_npc(sub) -> bool:
    if len(sub) < 2 + 47 or sub[:2] != b'\x08\x00':
        return False
    klass = struct.unpack_from('<I', sub, 2 + 40)[0]
    npc_type = struct.unpack_from('<H', sub, 2 + 45)[0]
    return klass not in (KLASS_MONSTRUO, KLASS_INVOCACION) and npc_type > 1


def _nombre(sub) -> str:
    crudo = bytes(sub[2 + 16:2 + 16 + LARGO_NOMBRE + 1]).split(b'\x00', 1)[0]
    return crudo.decode('ascii', 'replace')


def tiene_mision(p, nombre, stage, entidad=0) -> bool:
    import misiones
    try:
        disp = misiones.misiones_disponibles_npc(p, nombre, stage=stage, entidad=entidad)
    except Exception:
        log.debug('misiones_disponibles_npc fallo para %r', nombre, exc_info=True)
        return False
    return any(not misiones.mision_completada(p, q) for q in disp)


def con_marca(sub, nombre) -> bytes:
    nuevo = (MARCA + nombre).encode('ascii', 'replace')[:LARGO_NOMBRE]
    b = bytearray(sub)
    b[2 + 16:2 + 16 + LARGO_NOMBRE + 1] = bytes(LARGO_NOMBRE + 1)
    b[2 + 16:2 + 16 + len(nuevo)] = nuevo
    return bytes(b)


def marcar(ses, submsgs):
    """Los mismos sub-mensajes, con [!] en los NPC con mision para este jugador."""
    p = getattr(ses, 'personaje', None)
    if p is None or getattr(ses, 'rol', None) != 'mundo':
        return submsgs
    if any(isinstance(s, (bytes, bytearray)) and s[:2] == b'\x0c\x00' for s in submsgs):
        olvidar(ses)                      # cambio de mapa: los NPC de antes ya no estan
    if not any(isinstance(s, (bytes, bytearray)) and s[:2] == b'\x08\x00' for s in submsgs):
        return submsgs
    stage = int(getattr(p, 'stage', 0) or 0)
    vistos = _ULTIMOS.setdefault(id(ses), {})
    salida = []
    for s in submsgs:
        if isinstance(s, (bytes, bytearray)) and _es_npc(s):
            nombre = _nombre(s)
            if nombre.startswith(MARCA):
                salida.append(s)
                continue
            eid = struct.unpack_from('<I', s, 2)[0]
            marcado = tiene_mision(p, nombre, stage, eid)
            vistos[eid] = [bytes(s), nombre, marcado]
            if marcado:
                s = con_marca(s, nombre)
        salida.append(s)
    return tuple(salida)


def refrescar(ses):
    """Vuelve a mandar los NPC del mapa cuya marca cambio (tras aceptar o entregar una mision)."""
    p = getattr(ses, 'personaje', None)
    vistos = _ULTIMOS.get(id(ses))
    if p is None or not vistos:
        return
    import combate
    stage = int(getattr(p, 'stage', 0) or 0)
    cambios = []
    for eid, dato in list(vistos.items()):
        orig, nombre, antes = dato
        marcado = tiene_mision(p, nombre, stage, eid)
        if marcado == antes:
            continue
        dato[2] = marcado
        # Se quita y se vuelve a poner: asi el cliente no se queda con dos copias del mismo NPC.
        cambios += [combate.despawn_monstruo(eid), con_marca(orig, nombre) if marcado else orig]
    if cambios:
        ses.enviar(*cambios)


def olvidar(ses):
    """Al cambiar de mapa o desconectarse."""
    _ULTIMOS.pop(id(ses), None)
