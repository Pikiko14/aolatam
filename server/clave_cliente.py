"""La contrasena que manda el cliente de Windows en el AUTH (bytes 21..53 del paquete de login).

Va CIFRADA con Blowfish en modo ECB, palabras little-endian, con una clave fija que trae el cliente
(la cadena "d593b7880791f844", en angel.dat junto a "reg.ini"). Lo cifrado es un bufer de 32 bytes:
la contrasena, un 0 que la termina y, detras, lo que hubiera en la memoria del cliente (basura que
cambia entre ingresos). Por eso comparar los 32 bytes enteros no servia ("la contrasena no se valida",
docs/07_LOGIN_REAL.md): hay que descifrar y quedarse con lo que va hasta el 0.

Medido 31/10/2026 con los AUTH de logs/sesiones: con esa clave los bloques de contrasenas distintas
se descifran a texto legible terminado en 0, y volver a cifrar da exactamente lo capturado.

Las tablas de Blowfish son constantes publicas (los digitos hexadecimales de pi): se calculan aqui,
no se copian del cliente.
"""
import functools
import struct

CLAVE = b'd593b7880791f844'
LARGO = 32
_M = 0xFFFFFFFF


@functools.lru_cache(maxsize=1)
def _pi_hex(palabras: int):
    """Las primeras `palabras` palabras de 32 bits de la parte fraccionaria de pi (Machin, con enteros)."""
    bits = palabras * 32 + 64
    uno = 1 << bits

    def arctan_inv(x):
        total, termino, n, signo = 0, uno // x, 1, 1
        x2 = x * x
        while termino:
            total += signo * (termino // n)
            termino //= x2
            n += 2
            signo = -signo
        return total

    pi = 16 * arctan_inv(5) - 4 * arctan_inv(239)
    frac = pi - (3 << bits)
    frac >>= 64
    return [(frac >> (32 * (palabras - 1 - i))) & _M for i in range(palabras)]


@functools.lru_cache(maxsize=1)
def _tablas_base():
    w = _pi_hex(18 + 4 * 256)
    return w[:18], [w[18 + 256 * i: 18 + 256 * (i + 1)] for i in range(4)]


def _F(S, x):
    return ((((S[0][x >> 24] + S[1][(x >> 16) & 255]) & _M) ^ S[2][(x >> 8) & 255]) + S[3][x & 255]) & _M


def _cifrar(P, S, l, r):
    for i in range(16):
        l ^= P[i]
        r ^= _F(S, l)
        l, r = r, l
    l, r = r, l
    r ^= P[16]
    l ^= P[17]
    return l, r


def _descifrar(P, S, l, r):
    for i in range(17, 1, -1):
        l ^= P[i]
        r ^= _F(S, l)
        l, r = r, l
    l, r = r, l
    r ^= P[1]
    l ^= P[0]
    return l, r


@functools.lru_cache(maxsize=1)
def _horario():
    P0, S0 = _tablas_base()
    P, S = P0[:], [s[:] for s in S0]
    n = len(CLAVE)
    for i in range(18):
        d = 0
        for j in range(4):
            d = (d << 8) | CLAVE[(i * 4 + j) % n]
        P[i] ^= d
    l = r = 0
    for i in range(0, 18, 2):
        l, r = _cifrar(P, S, l, r)
        P[i], P[i + 1] = l, r
    for s in range(4):
        for i in range(0, 256, 2):
            l, r = _cifrar(P, S, l, r)
            S[s][i], S[s][i + 1] = l, r
    return P, S


def cifrar(bufer: bytes) -> bytes:
    """Cifra 32 bytes como el cliente (sirve para probar y para reconstruir un AUTH)."""
    P, S = _horario()
    salida = b''
    for i in range(0, len(bufer), 8):
        l, r = struct.unpack('<II', bufer[i:i + 8])
        salida += struct.pack('<II', *_cifrar(P, S, l, r))
    return salida


def descifrar(bloque: bytes) -> bytes:
    P, S = _horario()
    salida = b''
    for i in range(0, len(bloque) - len(bloque) % 8, 8):
        l, r = struct.unpack('<II', bloque[i:i + 8])
        salida += struct.pack('<II', *_descifrar(P, S, l, r))
    return salida


def contrasena(bloque: bytes):
    """La contrasena en claro de un bloque de 32 bytes del AUTH, o None si no es del cliente de Windows
    (no termina en 0 o lleva caracteres raros: el cliente LOVE manda otra cosa, ver cuentas.validar)."""
    if len(bloque) < LARGO:
        return None
    claro = descifrar(bloque[:LARGO])
    if b'\0' not in claro:
        return None
    texto = claro.split(b'\0', 1)[0]
    if not texto or not all(32 < c < 127 for c in texto):
        return None
    return texto.decode('ascii')
