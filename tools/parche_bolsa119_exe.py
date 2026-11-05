"""Los bucles de la bolsa del angel.dat hasta la ranura 119 (05/11/2026).

Con el Prop de 50 (tools/parche_prop50_exe.py) las ranuras 95-119 ya se ven y se usan, pero el cliente tiene 20
bucles que recorren la bolsa de la 20 a la 94 (cmp i, 0x5e; jg fin) para contar o buscar objetos. Por eso el Angel Baby
marcaba 0 pociones cuando estaban en las casillas nuevas ("no detecta las pociones, creo que es porque el AB no lista
los otros 25 espacios del bag"). Cada bucle pasa a acabar en la 119 (0x77): un byte. 15 de ellos comprueban ademas el
tamano del vector y los otros 5 leen el array de objetos de la bolsa, que llega mas alla de la 166.

    python tools/parche_bolsa119_exe.py <angel.dat de entrada> <salida>
    python tools/parche_bolsa119_exe.py <angel.dat> --ver
"""
import argparse
import pathlib

from parche_canal_lua import _off

VIEJO, NUEVO = 0x5E, 0x77            # 94 -> 119
# (va del cmp [ebp+x], imm8): el imm8 es el ultimo byte de la instruccion; detras va un jg.
CMPS = ((0x4A46CB, '837dfc'), (0x4A48E2, '837df8'), (0x514B8B, '837dfc'), (0x514C8B, '837dfc'),
        (0x514CFB, '837dfc'), (0x555569, '837dfc'), (0x555BEF, '837df0'), (0x5566AA, '837dfc'),
        (0x56041B, '837dfc'), (0x594A44, '837df8'), (0x59C2CB, '837de4'), (0x59C5AB, '837de4'),
        (0x5BF950, '837df8'), (0x5C5007, '837df8'), (0x5C5313, '837df8'), (0x5F8907, '837dbc'),
        (0x637948, '837de8'), (0x6500C6, '83bd3cffffff'), (0x65493A, '837dd8'), (0x6583F0, '837dec'))


def _sitios(d):
    out = []
    for va, pre in CMPS:
        p = bytes.fromhex(pre)
        o = _off(d, va)
        jg = bytes(d[o + len(p) + 1:o + len(p) + 3])
        if bytes(d[o:o + len(p)]) != p or not (jg[0] == 0x7F or jg == bytes((0x0F, 0x8F))):   # jg corto o largo
            raise SystemExit('en %#x no esta el bucle esperado: no es este angel.dat' % va)
        out.append(o + len(p))
    return out


def lleva_el_parche(d) -> bool:
    return all(d[o] == NUEVO for o in _sitios(d))


def parchear(d: bytes) -> bytes:
    d = bytearray(d)
    for o in _sitios(d):
        if d[o] not in (VIEJO, NUEVO):
            raise SystemExit('tope inesperado %#x en %#x' % (d[o], o))
        d[o] = NUEVO
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    d = pathlib.Path(a.entrada).read_bytes()
    if a.ver or not a.salida:
        print('bolsa hasta la 119' if lleva_el_parche(d) else 'bolsa hasta la 94')
        return
    pathlib.Path(a.salida).write_bytes(parchear(d))
    print('escrito', a.salida)


if __name__ == '__main__':
    main()
