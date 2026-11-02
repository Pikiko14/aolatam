"""Canal servidor -> Lua del cliente: el s2c 0x01A0 lleva codigo Lua que el cliente ejecuta (02/11/2026).

No existe en el cliente original: lo anade tools/parche_canal_lua.py a angel.dat (ver alli como funciona). Sirve
para llenar ventanas Lua propias, como la de la subasta, llamando a sus funciones con los datos:

    ses.enviar(canal_lua.llamar('SubastaFila', 3, 1513, 'Espada +4', 2000))

Un cliente sin el parche no tiene manejador para el 0x01A0 y lo ignora. Los GM pueden probarlo con /lua <codigo>.
"""
import struct

OPCODE = 0x01A0
# Lo que cabe en un submensaje (largo u16) menos el opcode y el cero del final.
MAXIMO = 0xFFFF - 3


def paquete(codigo: str) -> bytes:
    """El 0x01A0 con ese codigo Lua."""
    texto = codigo.encode('latin1', 'replace').replace(b'\0', b'')
    if len(texto) > MAXIMO:
        raise ValueError('codigo Lua demasiado largo (%d bytes)' % len(texto))
    return struct.pack('<H', OPCODE) + texto + b'\0'


def literal(v) -> str:
    """Un valor de Python como literal Lua: numeros, textos, booleanos, None, listas y diccionarios."""
    if v is None:
        return 'nil'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return '{' + ','.join(literal(x) for x in v) + '}'
    if isinstance(v, dict):
        return '{' + ','.join('[%s]=%s' % (literal(k), literal(x)) for k, x in v.items()) + '}'
    s = str(v)
    for a, b in (('\\', '\\\\'), ('"', '\\"'), ('\n', '\\n'), ('\r', '\\r'), ('\0', '')):
        s = s.replace(a, b)
    return '"%s"' % s


def llamar(funcion: str, *args) -> bytes:
    """El 0x01A0 que llama a la funcion global `funcion` del cliente con esos argumentos."""
    if not funcion.replace('_', '').replace('.', '').isalnum():
        raise ValueError('nombre de funcion Lua no valido: %r' % funcion)
    return paquete('%s(%s)' % (funcion, ','.join(literal(a) for a in args)))


def es_comando_gm(texto: str) -> bool:
    return texto.strip().lower().startswith('/lua ')


def codigo_del_comando(texto: str) -> str:
    return texto.strip()[5:].strip()
