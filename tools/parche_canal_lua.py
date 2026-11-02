"""Canal servidor -> Lua en angel.dat: el s2c 0x01A0 ejecuta su texto como codigo Lua (02/11/2026).

El cliente no tiene ninguna forma de que el servidor le pase datos a una ventana Lua: el servidor solo puede abrir
ventanas por nombre (0x001D) y las que llena con datos lo hacen desde C con su propio paquete. Para la subasta con
ventana propia (y lo que venga despues) hace falta un canal generico, y este es el mas corto: un paquete cuyo texto
se carga con luaL_loadbuffer y se ejecuta con la llamada protegida del propio juego. Asi el servidor llama a la
funcion Lua que quiera con los datos que quiera ("SubastaFila(3, 1513, ...)"), y un error en el codigo solo se
descarta (lo pinta la consola del juego) sin tirar el cliente.

    [u16 0x01A0][texto Lua ASCIIZ]          (submensaje normal, con su largo delante como todos)

Lo que hace en el exe (todo medido con capstone sobre angel_descomprimido.dat, base fija 0x400000, sin relocs):
- Anade una seccion .aolat (ejecutable) al final con el manejador y un gancho.
- El manejador (thiscall, 1 argumento = el paquete desde el opcode, ret 4, como los demas de la tabla):
      L = [[0x9590c0] + 4 + 4]                         el envoltorio Lua del juego, igual que CreateHitParadeWin
      luaL_loadbuffer(L, texto, strlen, "=servidor")   0x7eba70 (lo usa luaB_loadstring)
      ok  -> envoltorio.llamar(0 argumentos)           0x494000 (lua_pcall + su aviso de error)
      mal -> lua_settop(L, -2)                         0x7e87f0, quita el mensaje de error
- La tabla de manejadores s2c la llena 0x5e5350 en this + 0x7b0 + op*16 (punteros a metodo de 16 bytes). En su
  final (0x5e97ae, "mov eax, [ebp-0xca4]") se salta al gancho, que hace lo que habia (copia la ultima entrada y
  sale) y antes escribe el manejador en el hueco del 0x01A0, que estaba vacio.

    python tools/parche_canal_lua.py <angel.dat de entrada> <salida>
    python tools/parche_canal_lua.py <angel.dat> --ver          # solo dice si ya lo lleva

Va sobre el angel.dat DESCOMPRIMIDO (el de UPX no tiene el codigo a la vista; ver tools/icono_angel_dat.py).
"""
import argparse
import pathlib
import struct

OPCODE = 0x01A0
NOMBRE_SECCION = b'.aolat\0\0'

# Direcciones del exe (VA).
ENVOLTORIO_LUA = 0x9590C0       # [this] + 4 es el envoltorio; su +4 es el lua_State
LUAL_LOADBUFFER = 0x7EBA70
LUA_SETTOP = 0x7E87F0
LLAMAR_LUA = 0x494000           # thiscall (envoltorio), push nargs
GANCHO_EN = 0x5E97AE
GANCHO_ORIGINAL = bytes.fromhex('8b855cf3ffff')         # mov eax, [ebp-0xca4]
TABLA_OFF = 0x7B0


def _secciones(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    tabla = pe + 24 + opt
    out = []
    for i in range(n):
        s = tabla + 40 * i
        vsz, va, rsz, rptr = struct.unpack_from('<IIII', d, s + 8)
        out.append(dict(nombre=d[s:s + 8], vsz=vsz, va=va, rsz=rsz, rptr=rptr, cab=s))
    return pe, tabla, out


def _base(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    return struct.unpack_from('<I', d, pe + 24 + 28)[0]


def _off(d, va):
    base = _base(d)
    for s in _secciones(d)[2]:
        if s['va'] <= va - base < s['va'] + max(s['vsz'], s['rsz']):
            return va - base - s['va'] + s['rptr']
    raise ValueError(hex(va))


def lleva_el_canal(d) -> bool:
    return any(s['nombre'] == NOMBRE_SECCION for s in _secciones(d)[2])


def _rel(desde_va, destino_va):
    """rel32 de un call/jmp de 5 bytes que empieza en desde_va."""
    return struct.pack('<i', destino_va - (desde_va + 5))


def _codigo(va):
    """(bytes, va_manejador) de la seccion: manejador, gancho y el nombre del trozo."""
    c = bytearray()

    def call(dest):
        c.extend(b'\xe8' + _rel(va + len(c), dest))

    manejador = va
    c += b'\x55\x8b\xec\x56\x57'                                   # push ebp; mov ebp,esp; push esi; push edi
    c += b'\x8b\x35' + struct.pack('<I', ENVOLTORIO_LUA)           # mov esi, [ENVOLTORIO]
    c += b'\x83\xc6\x04'                                           # add esi, 4
    c += b'\x8b\x7d\x08\x83\xc7\x02'                               # mov edi, [ebp+8]; add edi, 2  (texto)
    c += b'\x8b\xcf'                                               # mov ecx, edi
    c += b'\x80\x39\x00\x74\x03\x41\xeb\xf8'                       # strlen: cmp byte[ecx],0; je +3; inc ecx; jmp
    c += b'\x2b\xcf'                                               # sub ecx, edi
    pos_nombre = len(c) + 1
    c += b'\x68\x00\x00\x00\x00'                                   # push NOMBRE (se rellena)
    c += b'\x51\x57\xff\x76\x04'                                   # push ecx; push edi; push [esi+4]
    call(LUAL_LOADBUFFER)
    c += b'\x83\xc4\x10'                                           # add esp, 16
    c += b'\x85\xc0\x75\x0b'                                       # test eax,eax; jnz mal
    c += b'\x6a\x00\x8b\xce'                                       # push 0; mov ecx, esi
    call(LLAMAR_LUA)
    c += b'\xeb\x0d'                                               # jmp fin
    c += b'\x6a\xfe\xff\x76\x04'                                   # mal: push -2; push [esi+4]
    call(LUA_SETTOP)
    c += b'\x83\xc4\x08'                                           # add esp, 8
    c += b'\x5f\x5e\x5d\xc2\x04\x00'                               # fin: pop edi; pop esi; pop ebp; ret 4

    gancho = va + len(c)
    c += GANCHO_ORIGINAL                                           # mov eax, [ebp-0xca4]
    c += b'\x89\x41\x0c'                                           # mov [ecx+0xc], eax
    c += b'\x8b\x8d\x4c\xf3\xff\xff'                               # mov ecx, [ebp-0xcb4]   (this)
    c += b'\xc7\x81' + struct.pack('<II', TABLA_OFF + OPCODE * 16, manejador)   # mov [ecx+hueco], manejador
    c += b'\x8b\xe5\x5d\xc3'                                       # mov esp,ebp; pop ebp; ret

    nombre = va + len(c)
    c += b'=servidor\0'
    c[pos_nombre:pos_nombre + 4] = struct.pack('<I', nombre)
    return bytes(c), manejador, gancho


def _alinear(x, a):
    return (x + a - 1) // a * a


def parchear(d: bytes) -> bytes:
    if lleva_el_canal(d):
        raise SystemExit('ya lleva el canal')
    d = bytearray(d)
    if d[_off(d, GANCHO_EN):_off(d, GANCHO_EN) + 6] != GANCHO_ORIGINAL:
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
    codigo, manejador, gancho = _codigo(_base(d) + va_rel)
    rsz = _alinear(len(codigo), al_arch)
    d.extend(bytes(rptr - len(d)))
    d.extend(codigo + bytes(rsz - len(codigo)))
    d[cab_nueva:cab_nueva + 40] = NOMBRE_SECCION + struct.pack('<IIIIIIHHI', len(codigo), va_rel, rsz, rptr,
                                                               0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, pe + 6, len(secs) + 1)
    struct.pack_into('<I', d, opt + 56, _alinear(va_rel + len(codigo), al_sec))     # SizeOfImage
    o = _off(d, GANCHO_EN)
    d[o:o + 6] = b'\xe9' + _rel(GANCHO_EN, gancho) + b'\x90'
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    d = pathlib.Path(a.entrada).read_bytes()
    if a.ver or not a.salida:
        print('lleva el canal' if lleva_el_canal(d) else 'no lleva el canal')
        return
    pathlib.Path(a.salida).write_bytes(parchear(d))
    print('escrito', a.salida)


if __name__ == '__main__':
    main()
