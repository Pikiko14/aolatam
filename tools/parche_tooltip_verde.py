"""Tooltip del equipo: seccion con los stats del martillo verde (幸運骰) que lleva la pieza (angel.dat, 16/11/2026).

"que sea posible ver otra seccion en esa ficha, los atributos que coloca el martillo verde, es decir los que tiene
actualmente aplicados". El cliente ya los recibe (entrada de inventario desde el 13, registros u32 [valor:26][id/4:6],
ver server/inventario.py marcar_extras) pero el tooltip solo los suma dentro de las lineas de stats que ya existian
(tabla this+0x14460 de 0x644A13), asi que no se veia cuales eran ni cuanto daba cada uno.

Medido con capstone sobre parches/juego/angel.dat (base fija 0x400000, sin relocs):

* 0x644980  construye el tooltip de un item: thiscall, [ebp+8] = la caja de texto, [ebp+0xC] = el item. Los stats
            verdes del item estan en item+0xC (5 dwords), los huecos en +0x51 y las gemas en +0x3D.
* 0x644EDC  justo despues de la ultima seccion de stats (0x642530) y antes del "\\n" + "has been intensified" +
            "a diamond has been set" (0x644EF2..0x644F4C). El gancho va aqui: mov edx,[ebp+0xC]; movzx eax,[edx+0x51].
* 0x71DBD0  cdecl (id/4) -> char* con el nombre del stat (string.xml; "" si no lo conoce). La usa el propio cuadro
            del martillo verde (0x57FCAF).
* 0x688CF0  thiscall (caja), push texto: anade una linea. Entiende /c#RRGGBB ... /c* (0x68EFD8); no hay marca de imagen.
* 0x8287AC  sprintf.

Anade la seccion .aolatv con el gancho y una funcion que, si la pieza tiene algun stat verde, escribe una linea en
blanco, la cabecera "Lucky Dice attributes" y una linea "+N Nombre" por stat, en verde como el cuadro del juego.

    python tools/parche_tooltip_verde.py <angel.dat de entrada> <salida>
    python tools/parche_tooltip_verde.py <angel.dat> --ver
"""
import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from parche_canal_lua import _alinear, _base, _off, _rel, _secciones  # noqa: E402

NOMBRE_SECCION = b'.aolatv\0'

GANCHO_EN = 0x644EDC
GANCHO_ORIGINAL = bytes.fromhex('8b550c0fb64251')        # mov edx,[ebp+0xc]; movzx eax, byte [edx+0x51]
GANCHO_VUELTA = 0x644EE3
NOMBRE_STAT = 0x71DBD0
ANADIR_LINEA = 0x688CF0
SPRINTF = 0x8287AC
OFF_VERDES = 0x0C
N_VERDES = 5
ID_MAX = 58                      # el switch de 0x71DBD0 va de 1 a 58

SALTO = b'\n\0'
CABECERA = b'/c#00FF00Lucky Dice attributes/c*\0'
LINEA = b'/c#00FF00 +%d %s/c*\0'


def lleva_el_parche(d) -> bool:
    return any(s['nombre'] == NOMBRE_SECCION for s in _secciones(d)[2])


def _codigo(va):
    c = bytearray()
    arreglos = []                                  # (posicion, nombre del dato) para rellenar al final

    def call(dest):
        c.extend(b'\xe8' + _rel(va + len(c), dest))

    def push_dato(nombre):
        c.extend(b'\x68')
        arreglos.append((len(c), nombre))
        c.extend(b'\0\0\0\0')

    # --- gancho: llama a la funcion con (caja, item), rehace lo pisado y vuelve
    gancho = va
    c += b'\x60'                                   # pushad
    c += b'\xff\x75\x0c\xff\x75\x08'               # push [ebp+0xc]; push [ebp+8]
    llamada_funcion = len(c)
    c += b'\xe8\0\0\0\0'                           # call funcion (se rellena)
    c += b'\x83\xc4\x08\x61'                       # add esp, 8; popad
    c += GANCHO_ORIGINAL
    c.extend(b'\xe9' + _rel(va + len(c), GANCHO_VUELTA))

    # --- funcion cdecl (caja, item)
    funcion = va + len(c)
    c[llamada_funcion + 1:llamada_funcion + 5] = _rel(va + llamada_funcion, funcion)
    c += b'\x55\x8b\xec\x81\xec\x00\x02\x00\x00'   # push ebp; mov ebp,esp; sub esp,0x200
    c += b'\x53\x56\x57'                           # push ebx; push esi; push edi
    c += b'\x8b\x75\x0c'                           # mov esi, [ebp+0xc]     item
    # Primero se mira que los cinco tengan forma de stat verde: en las mascotas ahi va el NOMBRE ("Water Elf"), y
    # eso no debe salir como stats. Un registro valido es [u16 valor][u8 0][u8 id] con id/4 entre 1 y 58.
    c += b'\x33\xdb'                               # xor ebx, ebx
    valida = len(c)
    c += b'\x83\xfb' + bytes([N_VERDES])           # cmp ebx, 5
    c += b'\x7d\x00'                               # jge bien (se rellena)
    pos_bien = len(c) - 1
    c += b'\x8b\x44\x9e' + bytes([OFF_VERDES])     # mov eax, [esi+ebx*4+0xc]
    c += b'\x85\xc0\x74\x00'                       # test eax,eax; jz vsig (se rellena)
    pos_vsig = len(c) - 1
    c += b'\xa9\x00\x00\xff\x00'                   # test eax, 0x00ff0000
    saltos_fin = [len(c)]
    c += b'\x0f\x85\0\0\0\0'                       # jnz fin
    c += b'\xc1\xe8\x1a'                           # shr eax, 26
    saltos_fin.append(len(c))
    c += b'\x0f\x84\0\0\0\0'                       # jz fin
    c += b'\x83\xf8' + bytes([ID_MAX])             # cmp eax, 58
    saltos_fin.append(len(c))
    c += b'\x0f\x87\0\0\0\0'                       # ja fin
    c[pos_vsig] = len(c) - (pos_vsig + 1)
    c += b'\x43'                                   # vsig: inc ebx
    c += b'\xeb' + bytes([(valida - (len(c) + 2)) & 0xff])   # jmp valida
    c[pos_bien] = len(c) - (pos_bien + 1)
    c += b'\x33\xff\x33\xdb'                       # bien: xor edi,edi (cabecera puesta); xor ebx,ebx (i)
    bucle = len(c)
    c += b'\x83\xfb' + bytes([N_VERDES])           # cmp ebx, 5
    salto_fin = len(c)
    c += b'\x0f\x8d\0\0\0\0'                       # jge fin
    c += b'\x8b\x44\x9e' + bytes([OFF_VERDES])     # mov eax, [esi+ebx*4+0xc]
    c += b'\x8b\xc8\x81\xe1\xff\xff\xff\x03'       # mov ecx,eax; and ecx,0x3ffffff
    salto_sig1 = len(c)
    c += b'\x0f\x84\0\0\0\0'                       # jz sig
    c += b'\xc1\xe8\x1a'                           # shr eax, 26
    salto_sig2 = len(c)
    c += b'\x0f\x84\0\0\0\0'                       # jz sig
    c += b'\x85\xff\x75\x00'                       # test edi,edi; jnz ya (se rellena)
    pos_jnz = len(c) - 1
    c += b'\x47'                                   # inc edi
    push_dato('salto')
    c += b'\x8b\x4d\x08'                           # mov ecx, [ebp+8]
    call(ANADIR_LINEA)
    push_dato('cabecera')
    c += b'\x8b\x4d\x08'
    call(ANADIR_LINEA)
    c[pos_jnz] = len(c) - (pos_jnz + 1)
    # nombre = 71DBD0(id)
    c += b'\x8b\x44\x9e' + bytes([OFF_VERDES])     # mov eax, [esi+ebx*4+0xc]
    c += b'\xc1\xe8\x1a\x50'                       # shr eax,26; push eax
    call(NOMBRE_STAT)
    c += b'\x83\xc4\x04'                           # add esp, 4
    c += b'\x8b\x4c\x9e' + bytes([OFF_VERDES])     # mov ecx, [esi+ebx*4+0xc]
    c += b'\x81\xe1\xff\xff\xff\x03'               # and ecx, 0x3ffffff
    c += b'\x50\x51'                               # push eax (nombre); push ecx (valor)
    push_dato('linea')
    c += b'\x8d\x95\x00\xfe\xff\xff\x52'           # lea edx,[ebp-0x200]; push edx
    call(SPRINTF)
    c += b'\x83\xc4\x10'                           # add esp, 16
    c += b'\x8d\x95\x00\xfe\xff\xff\x52'           # lea edx,[ebp-0x200]; push edx
    c += b'\x8b\x4d\x08'
    call(ANADIR_LINEA)
    sig = len(c)
    c += b'\x43'                                   # inc ebx
    c.extend(b'\xe9' + struct.pack('<i', bucle - (len(c) + 5)))
    fin = len(c)
    c += b'\x5f\x5e\x5b\x8b\xe5\x5d\xc3'           # pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret
    for pos, dest in [(salto_fin, fin), (salto_sig1, sig), (salto_sig2, sig)] + [(p, fin) for p in saltos_fin]:
        c[pos + 2:pos + 6] = struct.pack('<i', dest - (pos + 6))

    datos = {}
    for nombre, texto in (('salto', SALTO), ('cabecera', CABECERA), ('linea', LINEA)):
        datos[nombre] = va + len(c)
        c += texto
    for pos, nombre in arreglos:
        c[pos:pos + 4] = struct.pack('<I', datos[nombre])
    return bytes(c), gancho


def parchear(d: bytes) -> bytes:
    if lleva_el_parche(d):
        raise SystemExit('ya lleva el tooltip verde')
    d = bytearray(d)
    o = _off(d, GANCHO_EN)
    if d[o:o + len(GANCHO_ORIGINAL)] != GANCHO_ORIGINAL:
        raise SystemExit('el gancho no esta donde se espera: no es este angel.dat')
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
    rptr = _alinear(len(d), al_arch)
    codigo, gancho = _codigo(_base(d) + va_rel)
    rsz = _alinear(len(codigo), al_arch)
    d.extend(bytes(rptr - len(d)))
    d.extend(codigo + bytes(rsz - len(codigo)))
    d[cab_nueva:cab_nueva + 40] = NOMBRE_SECCION + struct.pack('<IIIIIIHHI', len(codigo), va_rel, rsz, rptr,
                                                               0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, pe + 6, len(secs) + 1)
    struct.pack_into('<I', d, opt + 56, _alinear(va_rel + len(codigo), al_sec))     # SizeOfImage
    o = _off(d, GANCHO_EN)
    d[o:o + len(GANCHO_ORIGINAL)] = b'\xe9' + _rel(GANCHO_EN, gancho) + b'\x90\x90'
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    d = pathlib.Path(a.entrada).read_bytes()
    if a.ver or not a.salida:
        print('lleva el tooltip verde' if lleva_el_parche(d) else 'no lleva el tooltip verde')
        return
    pathlib.Path(a.salida).write_bytes(parchear(d))
    print('escrito', a.salida)


if __name__ == '__main__':
    main()
