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


# --- ICONOS DE LAS GEMAS ("no se ve la foto de la gema puesta, el icono", 16/11/2026) ---------------------------------
# El texto del tooltip no tiene marca de imagen, asi que el icono se pinta a mano encima, en una fila de lineas en
# blanco que se reservan detras de los nombres de las gemas:
#
# * 0x644F51  justo al volver de 0x641BB0 (las lineas "a diamond has been set" y los nombres de las gemas). Gancho 2:
#             apunta las gemas puestas (item+0x3D, cuantas en +0x51), busca la ventana del tooltip igual que 0x688CF0
#             ([caja+8]+0x28 + (id & 0xFFFF)*4, con id = [caja+0x7C] y [ventana+0x10] == id), mira cuantas lineas lleva
#             ([ventana+0x168]) y anade las que ocupa un icono de 32 px (alto de linea en [ventana+0x13C]).
# * La ventana es de la clase WND_CLASS_TOOLTIP (0xA; la crea 0x699CF0 desde la fabrica 0x6A13C0), vtable 0x8C33EC:
#     slot 3  (0x69A610) pinta el texto (0x68E590): la linea i va en y = [+0x24]+[+0x44]+[+0x124] + i*[+0x13C] y
#             x = [+0x20]+[+0x40]+[+0x120]. Se cambia el puntero por una funcion que llama a la original y despues
#             pinta los iconos si la ventana es la apuntada.
#     slot 15 (0x68E9B0) pone el texto entero (lo llama 0x688C70 al empezar cualquier tooltip): se olvida la ventana
#             apuntada, para que los iconos no salgan en el tooltip de otra cosa.
# * Pintar un icono de item, como 0x4B03B5: def = 0x49DD60(item) (cdecl), icono = def[0]; objeto icono de 0x54 bytes
#   en la pila: 0x6848A0 (ctor), recurso = ([[0xA38104]+0xC]).0x4B0440(icono), 0x684AF0(recurso), 0x684F10(x, y,
#   [ventana+0xE0], 0, 0) (pinta, ret 0x14) y 0x6849C0 (dtor).
GANCHO2_EN = 0x644F51
GANCHO2_ORIGINAL = bytes.fromhex('8b55fc528b4508')      # mov edx,[ebp-4]; push edx; mov eax,[ebp+8]
GANCHO2_VUELTA = 0x644F58
VTABLE_TOOLTIP = 0x8C33EC
SLOT_PINTAR, PINTAR_ORIGINAL = 3, 0x69A610
SLOT_TEXTO, TEXTO_ORIGINAL = 15, 0x68E9B0
DEF_ITEM = 0x49DD60
RECURSOS = 0xA38104
BUSCAR_RECURSO = 0x4B0440
ICONO_CTOR, ICONO_PONER, ICONO_PINTAR, ICONO_DTOR = 0x6848A0, 0x684AF0, 0x684F10, 0x6849C0
OFF_GEMAS, OFF_HUECOS, MAX_GEMAS = 0x3D, 0x51, 5
PASO_ICONO = 34                 # 32 px de icono y 2 de aire
ALTO_ICONO = 32


class _Asm:
    """Ensamblador minimo: bytes a mano, etiquetas y saltos/llamadas que se resuelven al final."""

    def __init__(self, va):
        self.va, self.c, self.etiquetas, self.arreglos = va, bytearray(), {}, []

    def b(self, hexa):
        self.c += bytes.fromhex(hexa.replace(' ', ''))

    def et(self, nombre):
        self.etiquetas[nombre] = self.va + len(self.c)

    def abs32(self, nombre):            # direccion absoluta de una etiqueta (datos)
        self.arreglos.append(('abs', len(self.c), nombre))
        self.c += b'\0\0\0\0'

    def rel32(self, nombre):            # despues de E8/E9/0F 8x
        self.arreglos.append(('rel', len(self.c), nombre))
        self.c += b'\0\0\0\0'

    def rel8(self, nombre):             # despues de 7x/EB
        self.arreglos.append(('rel8', len(self.c), nombre))
        self.c += b'\0'

    def call(self, destino):
        self.c += b'\xe8' + struct.pack('<i', destino - (self.va + len(self.c) + 5))

    def jmp(self, destino):
        self.c += b'\xe9' + struct.pack('<i', destino - (self.va + len(self.c) + 5))

    def fin(self):
        for tipo, pos, nombre in self.arreglos:
            dest = self.etiquetas[nombre]
            if tipo == 'abs':
                self.c[pos:pos + 4] = struct.pack('<I', dest)
            elif tipo == 'rel':
                self.c[pos:pos + 4] = struct.pack('<i', dest - (self.va + pos + 4))
            else:
                r = dest - (self.va + pos + 1)
                if not -128 <= r <= 127:
                    raise ValueError('salto corto fuera de rango: %s' % nombre)
                self.c[pos] = r & 0xFF
        return bytes(self.c)


def _codigo_gemas(va):
    a = _Asm(va)
    # --- gancho 2: (caja, item) a la funcion apuntar, rehace lo pisado y vuelve
    a.et('gancho2')
    a.b('60 ff750c ff7508')                     # pushad; push [ebp+0xc]; push [ebp+8]
    a.b('e8'); a.rel32('apuntar')
    a.b('83c408 61')                            # add esp,8; popad
    a.c += GANCHO2_ORIGINAL
    a.jmp(GANCHO2_VUELTA)

    # --- apuntar(caja, item), cdecl
    a.et('apuntar')
    a.b('55 8bec 53 56 57')
    a.b('c705'); a.abs32('g_win'); a.b('00000000')          # g_win = 0
    a.b('8b750c 85f6 0f84'); a.rel32('a_fin')               # esi = item
    a.b('33db 33ff')                                        # i = 0, n = 0
    a.b('0fb64e' + '%02x' % OFF_HUECOS)                     # movzx ecx, byte [esi+0x51]
    a.b('83f9%02x 7e05 b9%02x000000' % (MAX_GEMAS, MAX_GEMAS))
    a.et('a_bucle')
    a.b('3bd9 7d'); a.rel8('a_contadas')                    # cmp ebx,ecx; jge
    a.b('8b449e%02x 85c0 74' % OFF_GEMAS); a.rel8('a_sig')  # mov eax,[esi+ebx*4+0x3d]; test; jz
    a.b('8904bd'); a.abs32('g_gemas')                       # mov [edi*4+g_gemas], eax
    a.b('47')                                               # inc edi
    a.et('a_sig')
    a.b('43 eb'); a.rel8('a_bucle')
    a.et('a_contadas')
    a.b('85ff 0f84'); a.rel32('a_fin')
    a.b('893d'); a.abs32('g_n')
    a.b('8b4d08 85c9 0f84'); a.rel32('a_fin')               # ecx = caja
    a.b('8b417c 85c0 0f84'); a.rel32('a_fin')               # eax = id
    a.b('8b5108 0fb7d8 8b5c9a28')                           # edx=[caja+8]; ebx=id&0xffff; ebx=[edx+ebx*4+0x28]
    a.b('85db 0f84'); a.rel32('a_fin')
    a.b('394310 0f85'); a.rel32('a_fin')                    # [ventana+0x10] == id
    a.b('8b8368010000 a3'); a.abs32('g_linea')              # g_linea = lineas que lleva
    a.b('8b8b3c010000 83f904 7d05 b90e000000')              # ecx = alto de linea (14 si no lo sabe)
    a.b('b8%02x000000 03c1 48 99 f7f9 a3' % (ALTO_ICONO + 3)); a.abs32('g_k')   # k = ceil((32+2)/alto)
    a.b('8bf8')                                             # edi = k
    a.et('a_lineas')
    a.b('85ff 7e'); a.rel8('a_listo')
    a.b('68'); a.abs32('salto')
    a.b('8b4d08'); a.call(ANADIR_LINEA)
    a.b('4f eb'); a.rel8('a_lineas')
    a.et('a_listo')
    a.b('891d'); a.abs32('g_win')                           # g_win = ventana
    a.et('a_fin')
    a.b('5f 5e 5b 5d c3')

    # --- slot 3: pintar (thiscall, sin argumentos)
    a.et('pintar')
    a.b('55 8bec 83ec60 53 56 57 8bd9')                     # ebx = ventana
    a.call(PINTAR_ORIGINAL)                                 # ecx sigue siendo la ventana
    a.b('3b1d'); a.abs32('g_win'); a.b('0f85'); a.rel32('p_fin')
    a.b('8b8368010000 3b05'); a.abs32('g_linea'); a.b('0f8e'); a.rel32('p_fin')   # aun tiene esas lineas
    a.b('8b8b3c010000 a1'); a.abs32('g_linea')
    a.b('0fafc1 034324 034344 038324010000')                # y = linea*alto + y de la caja
    a.b('8b15'); a.abs32('g_k')
    a.b('0fafd1 83ea%02x d1fa 03c2 8945f8' % ALTO_ICONO)    # centrado en las k lineas
    a.b('8b4320 034340 038320010000 8945fc')                # x
    a.b('33f6')
    a.et('p_bucle')
    a.b('3b35'); a.abs32('g_n'); a.b('0f8d'); a.rel32('p_fin')
    a.b('ff34b5'); a.abs32('g_gemas')
    a.call(DEF_ITEM)
    a.b('83c404 85c0 0f84'); a.rel32('p_sig')
    a.b('8b38')                                             # edi = icono
    a.b('8d4da0'); a.call(ICONO_CTOR)
    a.b('a1'); a.c += struct.pack('<I', RECURSOS)
    a.b('8b480c 57'); a.call(BUSCAR_RECURSO)
    a.b('85c0 74'); a.rel8('p_dtor')
    a.b('50 8d4da0'); a.call(ICONO_PONER)
    a.b('6a00 6a00 ffb3e0000000 ff75f8')                    # 0, 0, [ventana+0xe0], y
    a.b('8bc6 6bc0%02x 0345fc 50 8d4da0' % PASO_ICONO)      # x + i*34
    a.call(ICONO_PINTAR)
    a.et('p_dtor')
    a.b('8d4da0'); a.call(ICONO_DTOR)
    a.et('p_sig')
    a.b('46 e9'); a.rel32('p_bucle')
    a.et('p_fin')
    a.b('5f 5e 5b 8be5 5d c3')

    # --- slot 15: poner texto (thiscall, 1 argumento): si es la ventana apuntada, se olvida
    a.et('texto')
    a.b('3b0d'); a.abs32('g_win'); a.b('750a')
    a.b('c705'); a.abs32('g_win'); a.b('00000000')
    a.jmp(TEXTO_ORIGINAL)

    a.et('salto'); a.c += SALTO
    while len(a.c) % 4:
        a.c += b'\0'
    for nombre, tam in (('g_win', 4), ('g_n', 4), ('g_linea', 4), ('g_k', 4), ('g_gemas', 4 * MAX_GEMAS)):
        a.et(nombre)
        a.c += bytes(tam)
    codigo = a.fin()
    return codigo, {k: a.etiquetas[k] for k in ('gancho2', 'pintar', 'texto')}


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
    for va, orig in ((GANCHO2_EN, GANCHO2_ORIGINAL),
                     (VTABLE_TOOLTIP + 4 * SLOT_PINTAR, struct.pack('<I', PINTAR_ORIGINAL)),
                     (VTABLE_TOOLTIP + 4 * SLOT_TEXTO, struct.pack('<I', TEXTO_ORIGINAL))):
        o = _off(d, va)
        if d[o:o + len(orig)] != orig:
            raise SystemExit('%#x no es lo esperado: no es este angel.dat' % va)
    codigo1, gancho = _codigo(_base(d) + va_rel)
    codigo1 += bytes(_alinear(len(codigo1), 16) - len(codigo1))
    codigo2, entradas = _codigo_gemas(_base(d) + va_rel + len(codigo1))
    codigo = codigo1 + codigo2
    rsz = _alinear(len(codigo), al_arch)
    d.extend(bytes(rptr - len(d)))
    d.extend(codigo + bytes(rsz - len(codigo)))
    # Ejecutable y ESCRIBIBLE: las gemas apuntadas y la ventana viven al final de la seccion.
    d[cab_nueva:cab_nueva + 40] = NOMBRE_SECCION + struct.pack('<IIIIIIHHI', len(codigo), va_rel, rsz, rptr,
                                                               0, 0, 0, 0, 0xE0000020)
    struct.pack_into('<H', d, pe + 6, len(secs) + 1)
    struct.pack_into('<I', d, opt + 56, _alinear(va_rel + len(codigo), al_sec))     # SizeOfImage
    o = _off(d, GANCHO_EN)
    d[o:o + len(GANCHO_ORIGINAL)] = b'\xe9' + _rel(GANCHO_EN, gancho) + b'\x90\x90'
    o = _off(d, GANCHO2_EN)
    d[o:o + len(GANCHO2_ORIGINAL)] = b'\xe9' + _rel(GANCHO2_EN, entradas['gancho2']) + b'\x90\x90'
    struct.pack_into('<I', d, _off(d, VTABLE_TOOLTIP + 4 * SLOT_PINTAR), entradas['pintar'])
    struct.pack_into('<I', d, _off(d, VTABLE_TOOLTIP + 4 * SLOT_TEXTO), entradas['texto'])
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
