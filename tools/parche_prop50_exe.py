"""Prop (Alt+B) de 50 casillas en angel.dat (04/11/2026): "haz que en la mochila principal tengamos 50 espacios".

El exe solo conoce 25 casillas de Prop: las ventanas 3101-3125 son las ranuras 20-44 y las de la Backpack
(3801-3850) las 45-94. Las 25 nuevas del parche (wnd03.xml, ventanas 3151-3175) van a las ranuras 95-119, que el
cliente no usa (la 95-125 esta libre en su numeracion: despues vienen 126.. del puesto, 166 la tarjeta, 167.. Fashion)
y el servidor ya admitia hasta la 120. La Backpack no se toca.

Cambios (todo medido con capstone sobre el angel.dat descomprimido, base 0x400000, sin relocs):
  A. 0x57b320, ventana -> ranura: el primer caso (3101-3125 -> id-3081) se reescribe en su sitio para tambien
     3151-3175 -> id-3056.
  B. 0x57b740 registra los rangos de ventanas de objetos (lo, hi, tipo, nombre) con 0x57b620; tras el de Prop
     (tipo 1) se registra 3151-3175 igual.
  C. 0x62ef88 mete en un mapa el manejador de cada casilla de Prop (i de 0 a 24, ventana 0xc1d+i).
  D. 0x645863 prepara las casillas de Prop (i de 0 a 24, ventana 0xc1d+i).
  E1. 0x64772e repinta el Prop (ranura de 20 a 44, ventana ranura+0xc09).
  E2. 0x6483f0 lo mismo con otro metodo (0x6896e0).
  En C y D el contador salta de 25 a 50 (ventana 3151..) y el tope pasa a 75; en E1 y E2 salta de 45 a 95, el tope
  pasa a 119 y la ventana de 95-119 es ranura+3056. Los saltos van a una seccion nueva, .aolatp.

    python tools/parche_prop50_exe.py <angel.dat de entrada> <salida>
    python tools/parche_prop50_exe.py <angel.dat> --ver

Va encima del que ya lleva el canal Lua (tools/parche_canal_lua.py); tambien sobre uno sin el.
"""
import argparse
import pathlib
import struct

from parche_canal_lua import _alinear, _base, _off, _rel, _secciones

NOMBRE_SECCION = b'.aolatp\0'
PRIMERA_NUEVA, ULTIMA_NUEVA = 3151, 3175      # ventanas
RANURA_NUEVA = 95                             # 3151 -> 95
EAX, ECX, EDX = 0, 1, 2

# (va, bytes originales) de cada sitio que se toca; si no casan, no es este angel.dat.
DESPACHO = (0x57B326, bytes.fromhex('817d081d0c0000721b817d08350c000077128b4508' '2d090c0000e9ca020000e9c5020000'))
REGISTRO = (0x57B783, bytes.fromhex('83c42883ec1c'))
FIN_REGISTRO = 0x57B789
STRING_CTOR = 0x496210          # thiscall std::string(const char*), ret 4
REGISTRAR = 0x57B620            # cdecl (lo, hi, tipo, std::string por valor)
NOMBRE_SLOT = 0x8BC358          # "物品欄slot" en big5
SALIDA_DESPACHO = 0x57B60F
SIGUIENTE_CASO = 0x57B34A

# bucles: (va del incremento, reg, desp ebp, va del tope, tope viejo, tope nuevo, salta_de, salta_a)
BUCLES = (
    (0x62EF91, EDX, -4, 0x62EF9A, 0x19, 0x4B, 25, 50),       # C
    (0x64586C, EAX, -8, 0x645875, 0x19, 0x4B, 25, 50),       # D
    (0x647737, EDX, -0xC, 0x647740, 0x2C, 0x77, 45, 95),     # E1
    (0x6483F9, EAX, -8, 0x648402, 0x2C, 0x77, 45, 95),       # E2
)
# ventana = ranura + 0xc09: (va, reg, bytes originales)
VENTANAS = (
    (0x647749, EAX, bytes.fromhex('05090c0000')),
    (0x64840B, ECX, bytes.fromhex('81c1090c0000')),
)


def _b8(x):
    return struct.pack('<b', x)


def _incremento(reg, desp, de, a):
    """mov reg,[ebp+desp]; inc reg; cmp reg,de; jne +5; mov reg,a; mov [ebp+desp],reg; ret"""
    return (bytes((0x8B, 0x45 | reg << 3)) + _b8(desp) + bytes((0x40 + reg, 0x83, 0xF8 | reg, de, 0x75, 5,
                                                                 0xB8 + reg)) + struct.pack('<I', a)
            + bytes((0x89, 0x45 | reg << 3)) + _b8(desp) + b'\xc3')


def _ventana(reg):
    """cmp reg,95; jl +3; sub reg,25; add reg,0xc09; ret  (3151 - 95 = 3056 = 0xc09 - 25)"""
    resta = PRIMERA_NUEVA - RANURA_NUEVA
    return (bytes((0x83, 0xF8 | reg, RANURA_NUEVA, 0x7C, 3, 0x83, 0xE8 | reg, 0xC09 - resta))
            + bytes((0x81, 0xC0 | reg)) + struct.pack('<I', 0xC09) + b'\xc3')


def _despacho(va):
    """El primer caso de 0x57b320 reescrito en sus 36 bytes."""
    c = bytearray(b'\x8b\x45\x08')                         # mov eax, [ebp+8]
    c += b'\x2d' + struct.pack('<I', 3101)                 # sub eax, 3101
    c += b'\x83\xf8\x18'                                   # cmp eax, 24
    c += b'\x76\x00'                                       # jbe vieja (se rellena)
    pos_jbe = len(c)
    c += b'\x83\xe8' + bytes((PRIMERA_NUEVA - 3101,))      # sub eax, 50
    c += b'\x83\xf8' + bytes((ULTIMA_NUEVA - PRIMERA_NUEVA,))   # cmp eax, 24
    c += b'\x0f\x87' + struct.pack('<i', 0)                # ja siguiente caso (se rellena)
    pos_ja = len(c)
    c += b'\x83\xc0' + bytes((RANURA_NUEVA - 20,))         # add eax, 75
    c[pos_jbe - 1] = len(c) - pos_jbe                      # vieja:
    c += b'\x83\xc0\x14'                                   # add eax, 20
    c += b'\xe9' + _rel(va + len(c), SALIDA_DESPACHO)
    c[pos_ja - 4:pos_ja] = struct.pack('<i', SIGUIENTE_CASO - (va + pos_ja))
    return bytes(c)


def _registro(va):
    """Lo que habia (add esp,0x28; sub esp,0x1c) con el registro de 3151-3175 en medio."""
    c = bytearray(b'\x83\xc4\x28')
    c += b'\x83\xec\x1c\x8b\xcc'                           # sub esp,0x1c; mov ecx,esp
    c += b'\x68' + struct.pack('<I', NOMBRE_SLOT)
    c += b'\xe8' + _rel(va + len(c), STRING_CTOR)
    c += b'\x6a\x01\x68' + struct.pack('<I', ULTIMA_NUEVA) + b'\x68' + struct.pack('<I', PRIMERA_NUEVA)
    c += b'\xe8' + _rel(va + len(c), REGISTRAR)
    c += b'\x83\xc4\x28'
    c += b'\x83\xec\x1c'
    c += b'\xe9' + _rel(va + len(c), FIN_REGISTRO)
    return bytes(c)


def lleva_el_parche(d) -> bool:
    return any(s['nombre'] == NOMBRE_SECCION for s in _secciones(d)[2])


def _comprobar(d, va, esperado):
    o = _off(d, va)
    if bytes(d[o:o + len(esperado)]) != esperado:
        raise SystemExit('en %#x no esta lo esperado (%s): no es este angel.dat' % (va, d[o:o + len(esperado)].hex()))
    return o


def parchear(d: bytes) -> bytes:
    if lleva_el_parche(d):
        raise SystemExit('ya lleva el Prop de 50')
    d = bytearray(d)
    _comprobar(d, *DESPACHO)
    _comprobar(d, *REGISTRO)
    for inc, reg, desp, tope_va, viejo, _n, _de, _a in BUCLES:
        _comprobar(d, inc, bytes((0x8B, 0x45 | reg << 3)) + _b8(desp) + bytes((0x83, 0xC0 | reg, 1, 0x89,
                                                                                0x45 | reg << 3)) + _b8(desp))
        _comprobar(d, tope_va, b'\x83\x7d' + _b8(desp) + bytes((viejo,)))
    for va, _reg, orig in VENTANAS:
        _comprobar(d, va, orig)

    pe, tabla, secs = _secciones(d)
    opt = pe + 24
    al_sec = struct.unpack_from('<I', d, opt + 32)[0]
    al_arch = struct.unpack_from('<I', d, opt + 36)[0]
    tam_cab = struct.unpack_from('<I', d, opt + 60)[0]
    cab_nueva = tabla + 40 * len(secs)
    if cab_nueva + 40 > tam_cab or any(d[cab_nueva:cab_nueva + 40]):
        raise SystemExit('no hay sitio para otra seccion en la cabecera')
    ultima = max(secs, key=lambda s: s['va'])
    va_rel = _alinear(ultima['va'] + max(ultima['vsz'], ultima['rsz']), al_sec)
    va0 = _base(d) + va_rel

    codigo = bytearray()
    saltos = []                                   # (va del sitio, largo a pisar, va destino, es_call)
    reg_va = va0 + len(codigo)
    codigo += _registro(reg_va)
    saltos.append((REGISTRO[0], 6, reg_va, False))
    for inc, reg, desp, _t, _v, _n, de, a in BUCLES:
        f = va0 + len(codigo)
        codigo += _incremento(reg, desp, de, a)
        saltos.append((inc, 9, f, True))
    for va, reg, orig in VENTANAS:
        f = va0 + len(codigo)
        codigo += _ventana(reg)
        saltos.append((va, len(orig), f, True))

    rptr = _alinear(len(d), al_arch)
    rsz = _alinear(len(codigo), al_arch)
    d.extend(bytes(rptr - len(d)))
    d.extend(codigo + bytes(rsz - len(codigo)))
    d[cab_nueva:cab_nueva + 40] = NOMBRE_SECCION + struct.pack('<IIIIIIHHI', len(codigo), va_rel, rsz, rptr,
                                                               0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, pe + 6, len(secs) + 1)
    struct.pack_into('<I', d, opt + 56, _alinear(va_rel + len(codigo), al_sec))     # SizeOfImage

    o = _off(d, DESPACHO[0])
    nuevo = _despacho(DESPACHO[0])
    d[o:o + len(DESPACHO[1])] = nuevo + b'\x90' * (len(DESPACHO[1]) - len(nuevo))
    for va, largo, destino, es_call in saltos:
        o = _off(d, va)
        d[o:o + largo] = (b'\xe8' if es_call else b'\xe9') + _rel(va, destino) + b'\x90' * (largo - 5)
    for _i, _r, desp, tope_va, _v, nuevo_tope, _de, _a in BUCLES:
        d[_off(d, tope_va) + 3] = nuevo_tope
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    d = pathlib.Path(a.entrada).read_bytes()
    if a.ver or not a.salida:
        print('lleva el Prop de 50' if lleva_el_parche(d) else 'no lleva el Prop de 50')
        return
    pathlib.Path(a.salida).write_bytes(parchear(d))
    print('escrito', a.salida)


if __name__ == '__main__':
    main()
