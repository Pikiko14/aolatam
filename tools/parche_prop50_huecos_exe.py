"""Los bucles del Prop viejo (20..44) del angel.dat tambien pasan por las casillas nuevas 95..119 (05/11/2026).

"si tengo los primeros 25 puestos de la mochila ocupados, no me funciona el trade por espacio, ni puedo sacar items de
bag y mas... los props ahora tienen 50 espacios, deben poder aceptarlos". El cliente busca hueco recorriendo el Prop
viejo (cmp i, 0x2c; jg) y luego la Backpack (45..94): con las 25 primeras llenas decia que no habia sitio sin mirar la
95..119. Son 7 bucles sobre el vector de objetos (+0x208, con su comprobacion de tamano); el contador salta de 45 a 95
y el tope pasa a 119, igual que hace tools/parche_prop50_exe.py con los de las ventanas. El de 0x645f36 calcula ids de
ventana y no se toca.

Va despues de tools/parche_prop50_exe.py y tools/parche_bolsa119_exe.py; anade la seccion .aolatq.

    python tools/parche_prop50_huecos_exe.py <angel.dat de entrada> <salida>
    python tools/parche_prop50_huecos_exe.py <angel.dat> --ver
"""
import argparse
import pathlib
import struct

from parche_canal_lua import _alinear, _base, _off, _rel, _secciones
from parche_prop50_exe import _b8, _incremento

NOMBRE_SECCION = b'.aolatq\0'
EAX, ECX, EDX = 0, 1, 2
# (va del incremento "mov reg,[ebp+d]; add reg,1; mov [ebp+d],reg", reg, desp, va del "cmp [ebp+d], 0x2c")
BUCLES = (
    (0x558383, EDX, -0x0C, 0x55838C),
    (0x5BC278, EAX, -0x20, 0x5BC281),
    (0x62133A, EAX, -0x10, 0x621343),
    (0x6608FF, ECX, -0x1C, 0x660908),
    (0x6649F3, EAX, -0x08, 0x6649FC),
    (0x664E71, ECX, -0x08, 0x664E7A),
    (0x6C0AB9, EAX, -0x04, 0x6C0AC2),
)
TOPE_VIEJO, TOPE_NUEVO = 0x2C, 0x77          # 44 -> 119
SALTA_DE, SALTA_A = 45, 95


def lleva_el_parche(d) -> bool:
    return any(s['nombre'] == NOMBRE_SECCION for s in _secciones(d)[2])


def _comprobar(d):
    for inc, reg, desp, tope_va in BUCLES:
        esperado_inc = bytes((0x8B, 0x45 | reg << 3)) + _b8(desp) + bytes((0x83, 0xC0 | reg, 1, 0x89,
                                                                             0x45 | reg << 3)) + _b8(desp)
        o = _off(d, inc)
        if bytes(d[o:o + 9]) != esperado_inc:
            raise SystemExit('en %#x no esta el incremento esperado: no es este angel.dat' % inc)
        o = _off(d, tope_va)
        if bytes(d[o:o + 4]) != b'\x83\x7d' + _b8(desp) + bytes((TOPE_VIEJO,)):
            raise SystemExit('en %#x no esta el tope esperado: no es este angel.dat' % tope_va)


def parchear(d: bytes) -> bytes:
    if lleva_el_parche(d):
        raise SystemExit('ya lleva los huecos del Prop de 50')
    d = bytearray(d)
    _comprobar(d)
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
    saltos = []
    for inc, reg, desp, _t in BUCLES:
        f = va0 + len(codigo)
        codigo += _incremento(reg, desp, SALTA_DE, SALTA_A)
        saltos.append((inc, f))

    rptr = _alinear(len(d), al_arch)
    rsz = _alinear(len(codigo), al_arch)
    d.extend(bytes(rptr - len(d)))
    d.extend(codigo + bytes(rsz - len(codigo)))
    d[cab_nueva:cab_nueva + 40] = NOMBRE_SECCION + struct.pack('<IIIIIIHHI', len(codigo), va_rel, rsz, rptr,
                                                               0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, pe + 6, len(secs) + 1)
    struct.pack_into('<I', d, opt + 56, _alinear(va_rel + len(codigo), al_sec))     # SizeOfImage
    for va, destino in saltos:
        o = _off(d, va)
        d[o:o + 9] = b'\xe8' + _rel(va, destino) + b'\x90' * 4
    for _i, _r, _d, tope_va in BUCLES:
        d[_off(d, tope_va) + 3] = TOPE_NUEVO
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    d = pathlib.Path(a.entrada).read_bytes()
    if a.ver or not a.salida:
        print('lleva los huecos del Prop de 50' if lleva_el_parche(d) else 'no los lleva')
        return
    pathlib.Path(a.salida).write_bytes(parchear(d))
    print('escrito', a.salida)


if __name__ == '__main__':
    main()
