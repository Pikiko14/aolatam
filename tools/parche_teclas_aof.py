"""Teclas de la barra a gusto de cada jugador y chat que se abre con Enter (angel.dat, 07/11/2026).

"habilita desde la config una opcion llamada aof ... cambiar los key de f1 y asi a lo que cada usuario quiera" y
"para hablar se presione enter y se active el chat, se escribe y luego se desactiva, y asi que puedan asignar numeros".

Todo medido con capstone sobre el angel.dat de parches/juego (base fija 0x400000, sin relocs). Anade la seccion .aolatk:

* NATIVOS NUEVOS de la tabla `game` de los Lua (la original, 605 pares {nombre, funcion} en 0x8BAF58, se copia aqui con
  cinco mas y el push de luaI_openlib en 0x5AE25E apunta a la copia):
      game.aofsetkey(casilla 0..11, dik, escribe 0|1)  la tecla (codigo DIK) de esa casilla de la barra; `escribe` dice
                                                      si es una tecla que escribe (numero, letra) para el modo chat
      game.aofgetkey(casilla)   -> dik
      game.aofpressed()         -> el primer DIK pulsado ahora, o -1 (0x812400), para el "pulsa una tecla"
      game.aofmode(0|1)         apaga / enciende el modo "el chat se abre con Enter"
      game.aofchat([0|1])       -> 1 si el chat esta abierto; con argumento lo abre o lo cierra
  Las teclas de la barra son los 12 primeros codigos del dispositivo de teclas [[0x958B88]+0x4F8] (0x500420 los pone
  F1..F12): el despacho (0x5B6B60) mira si se acaban de pulsar y usa la casilla. Basta cambiar esos codigos.
* MODO CHAT (con game.aofmode(1); apagado es el juego de siempre):
  P2  0x68A08A  Edit::HasKeyboard (0x68A000), rama de la caja del chat ("always-edit") sin foco en otra caja: con el
                modo encendido el chat cerrado NO recibe el teclado, y un Enter en la cola de eventos (0xB114C8, 9)
                lo abre (foco del gestor [0x9590C4]+0x4038 = la caja). Las demas cajas no cambian: entran por "el foco
                soy yo". Lo tecleado con el chat cerrado se tira solo al acabar el frame (0x811420).
  P3  0x68BDF6  tras enviar con Enter (0x68BD9E), la caja del chat tambien suelta el foco: se cierra.
  P4  0x5B6D5D  antes del despacho de la barra: con el chat abierto (foco en una caja de texto) o Ctrl/Alt pulsados
                ([dispositivo 0x4F4]+0x18 & 0x1E), se borran las casillas con tecla que escribe de "recien pulsadas"
                (+0x20): escribir "1" no usa la casilla, y Alt+1 sigue siendo el emote.
  Escape ya cerraba el chat (0x68BE1C).

    python tools/parche_teclas_aof.py <angel.dat de entrada> <salida>
    python tools/parche_teclas_aof.py <angel.dat> --ver
"""
import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from parche_canal_lua import _alinear, _base, _off, _secciones  # noqa: E402

NOMBRE_SECCION = b'.aolatk\0'

TABLA_GAME = 0x8BAF58
P1, P1_ORIG = 0x5AE25E, bytes.fromhex('6858af8b00')                 # push 0x8BAF58
P2, P2_ORIG = 0x68A08A, bytes.fromhex('837df800742c')               # cmp [ebp-8],0; je 0x68A0BC
P2_VERDADERO, P2_FALSO = 0x68A0BC, 0x68A0C2
P3, P3_ORIG = 0x68BDF6, bytes.fromhex('741f')                       # je 0x68BE17
P4, P4_ORIG = 0x5B6D5D, bytes.fromhex('8b15888b9500')               # mov edx, [0x958B88]
P4_VUELTA = 0x5B6D63

CTRL_JUEGO = 0x958B88            # +0x4F4 dispositivo de modificadores y letras, +0x4F8 el de la barra
DISPOSITIVOS = 0xB12D70          # [DISPOSITIVOS + 4*h] -> objeto: +0x18 mantenidas, +0x20 recien pulsadas, +0x38 dik[]
GESTOR_VENTANAS = 0x9590C4       # +0x4038 foco, +0x4044 caja "always-edit" (el chat), +0x28 ventanas por indice
COLA_EVENTOS, N_EVENTOS = 0xB114C8, 0xB12DDC
CONSUMIR_EVENTO = 0x811470       # cdecl (evento)
TECLA_PULSADA = 0x812400         # -> dik o -1
ARG_ENTERO = 0x51C210            # thiscall sobre {byte; L}, (indice)
LUA_GETTOP = 0x7E87D0
LUA_PUSHNUMBER = 0x7E9350
NATIVOS = ('aofsetkey', 'aofgetkey', 'aofpressed', 'aofmode', 'aofchat')


class Asm:
    """Lo justo para escribir el codigo a mano con etiquetas (saltos rel32 / rel8 resueltos al final)."""

    def __init__(self, va):
        self.va, self.b, self.et, self.arreglos = va, bytearray(), {}, []

    def aqui(self):
        return self.va + len(self.b)

    def __call__(self, hexa):
        self.b += bytes.fromhex(hexa.replace(' ', ''))
        return self

    def d32(self, v):
        self.b += struct.pack('<I', v & 0xFFFFFFFF)
        return self

    def etiqueta(self, nombre):
        self.et[nombre] = self.aqui()

    def _rel32(self, op, destino):
        self.b += op
        self.arreglos.append((len(self.b), destino))
        self.b += b'\0\0\0\0'

    def call(self, destino):
        self._rel32(b'\xe8', destino)

    def jmp(self, destino):
        self._rel32(b'\xe9', destino)

    def jcc(self, cc, destino):          # cc: 0x84 je, 0x85 jne, 0x8D jge, 0x83 jae...
        self._rel32(bytes([0x0F, cc]), destino)

    def cerrar(self):
        for pos, destino in self.arreglos:
            va_dest = self.et[destino] if isinstance(destino, str) else destino
            struct.pack_into('<i', self.b, pos, va_dest - (self.va + pos + 4))
        return bytes(self.b)


JE, JNE, JGE, JAE = 0x84, 0x85, 0x8D, 0x83


def _tabla_game(d):
    """Los pares {nombre, funcion} de la tabla game, sin el terminador."""
    o, pares = _off(d, TABLA_GAME), []
    while True:
        n, f = struct.unpack_from('<II', d, o + 8 * len(pares))
        if n == 0 and f == 0:
            return pares
        pares.append((n, f))
        if len(pares) > 2000:
            raise SystemExit('la tabla game no termina: no es este angel.dat')


def _codigo(va, pares):
    a = Asm(va)
    modo, mascara = va, va + 4
    a('00000000').d32(0)                                   # modo (byte) y mascara de casillas que escriben
    nombres = {}
    for n in NATIVOS:
        nombres[n] = a.aqui()
        a.b += n.encode() + b'\0'
    while len(a.b) % 16:
        a('cc')

    def entrada():                                         # push ebp; mov ebp,esp; sub esp,0x20; {0; L} en ebp-0xc
        a('55 8bec 83ec20 8b4508 8945f8 c645f400')

    def arg(n):                                            # eax = argumento n
        a('6a').b += bytes([n])
        a('8d4df4')
        a.call(ARG_ENTERO)

    def devolver_eax(n_ret=1):                             # lua_pushnumber(L, (double)eax); return 1
        a('8945fc db45fc 83ec08 dd1c24 ff7508')
        a.call(LUA_PUSHNUMBER)
        a('83c40c b8').d32(n_ret)
        a('8be5 5d c3')

    def salir_0():
        a('33c0 8be5 5d c3')

    def dispositivo(off):                                  # eax = objeto del dispositivo [CTRL_JUEGO]+off
        a('a1').d32(CTRL_JUEGO)
        a('8b80').d32(off)
        a('8b0485').d32(DISPOSITIVOS)

    fun = {}
    # aofsetkey(casilla, dik, escribe)
    fun['aofsetkey'] = a.aqui()
    entrada()
    arg(1); a('8945f0')                                    # [ebp-0x10] casilla
    arg(2); a('8945ec')                                    # [ebp-0x14] dik
    arg(3); a('8945e8')                                    # [ebp-0x18] escribe
    a('837df00c'); a.jcc(JAE, 'set_fin')                   # casilla >= 12: nada
    dispositivo(0x4F8)
    a('8b4df0 8b55ec 89548838')                            # mov ecx,[ebp-0x10]; mov edx,[ebp-0x14]; [eax+ecx*4+0x38]=edx
    a('b801000000 d3e0')                                   # eax = 1 << casilla
    a('837de800'); a.jcc(JE, 'set_quita')
    a('0905').d32(mascara); a.jmp('set_fin')               # or [mascara], eax
    a.etiqueta('set_quita')
    a('f7d0 2105').d32(mascara)                            # not eax; and [mascara], eax
    a.etiqueta('set_fin')
    salir_0()

    # aofgetkey(casilla) -> dik
    fun['aofgetkey'] = a.aqui()
    entrada()
    arg(1); a('8bc8')                                      # ecx = casilla
    a('83f90c'); a.jcc(JAE, 'get_malo')
    a('51')                                                # push ecx
    dispositivo(0x4F8)
    a('59 8b448838')                                       # pop ecx; mov eax, [eax+ecx*4+0x38]
    devolver_eax()
    a.etiqueta('get_malo')
    a('83c8ff')                                            # or eax, -1
    devolver_eax()

    # aofpressed() -> dik o -1
    fun['aofpressed'] = a.aqui()
    entrada()
    a.call(TECLA_PULSADA)
    devolver_eax()

    # aofmode(0|1)
    fun['aofmode'] = a.aqui()
    entrada()
    arg(1)
    a('85c0 0f95c0 a2').d32(modo)                          # test eax,eax; setne al; mov [modo], al
    salir_0()

    # aofchat([0|1]) -> abierto
    fun['aofchat'] = a.aqui()
    entrada()
    a('ff7508'); a.call(LUA_GETTOP); a('83c404')
    a('85c0'); a.jcc(JE, 'chat_ver')
    arg(1)
    a('8b0d').d32(GESTOR_VENTANAS)                         # mov ecx, [gestor]
    a('33d2 85c0'); a.jcc(JE, 'chat_pon')                  # xor edx,edx; test eax,eax; je
    a('8b9144400000')                                      # mov edx, [ecx+0x4044]
    a.etiqueta('chat_pon')
    a('899138400000')                                      # mov [ecx+0x4038], edx
    a.etiqueta('chat_ver')
    a('8b0d').d32(GESTOR_VENTANAS)
    a('8b8138400000 33d2 85c0'); a.jcc(JE, 'chat_res')     # eax = foco; edx = 0; foco 0 -> cerrado
    a('3b8144400000 0f94c2')                               # cmp eax, [ecx+0x4044]; sete dl
    a.etiqueta('chat_res')
    a('8bc2')
    devolver_eax()

    # P2: Edit::HasKeyboard, rama de la caja del chat. [ebp-8] la ventana con foco (0 si no hay), [ebp-0x14] la caja.
    cueva_teclado = a.aqui()
    a('8b45f8 85c0'); a.jcc(JE, 'p2_sin_caja')
    a('6a03 8bc8 8b11 ff5204 84c0'); a.jcc(JNE, P2_FALSO)  # IsKindOf(3): el foco esta en otra caja de texto
    a('6a0b 8b4df8 8b11 ff5204 84c0'); a.jcc(JNE, P2_FALSO)
    a.etiqueta('p2_sin_caja')
    a('803d').d32(modo).b += b'\x00'                       # cmp byte [modo], 0
    a.jcc(JE, P2_VERDADERO)                                # modo apagado: como siempre
    a('8b0d').d32(N_EVENTOS)
    a('33c0')
    a.etiqueta('p2_busca')
    a('3bc1'); a.jcc(JGE, P2_FALSO)                        # sin Enter en la cola: el chat sigue cerrado
    a('833c85').d32(COLA_EVENTOS).b += b'\x09'             # cmp dword [eax*4+cola], 9
    a.jcc(JE, 'p2_abre')
    a('40'); a.jmp('p2_busca')
    a.etiqueta('p2_abre')
    a('6a09'); a.call(CONSUMIR_EVENTO); a('83c404')        # el Enter que lo abre no envia nada
    a('8b4dec 8b4108 8b5110 899038400000')                 # foco del gestor = la caja del chat
    a.jmp(P2_FALSO)                                        # este frame todavia no

    # P4: antes del despacho de la barra.
    cueva_barra = a.aqui()
    a('803d').d32(modo).b += b'\x00'
    a.jcc(JE, 'p4_fin')
    dispositivo(0x4F4)
    a('f740181e000000'); a.jcc(JNE, 'p4_limpia')           # test dword [eax+0x18], 0x1E (Ctrl / Alt)
    a('8b0d').d32(GESTOR_VENTANAS)
    a('8b8138400000 85c0'); a.jcc(JE, 'p4_fin')            # sin foco: el chat esta cerrado
    a('0fb7d0 8b549128 85d2'); a.jcc(JE, 'p4_fin')         # movzx edx,ax; mov edx,[ecx+edx*4+0x28]
    a('394210'); a.jcc(JNE, 'p4_fin')                      # cmp [edx+0x10], eax
    a('56 8bf2')                                           # push esi; mov esi, edx
    a('6a03 8bce 8b06 ff5004 84c0'); a.jcc(JNE, 'p4_limpia_pop')
    a('6a0b 8bce 8b06 ff5004 84c0'); a.jcc(JNE, 'p4_limpia_pop')
    a('5e'); a.jmp('p4_fin')
    a.etiqueta('p4_limpia_pop')
    a('5e')
    a.etiqueta('p4_limpia')
    dispositivo(0x4F8)
    a('8b0d').d32(mascara)
    a('f7d1 214820')                                       # not ecx; and [eax+0x20], ecx
    a.etiqueta('p4_fin')
    a('8b15').d32(CTRL_JUEGO)                              # lo que se piso: mov edx, [0x958B88]
    a.jmp(P4_VUELTA)

    while len(a.b) % 16:
        a('cc')
    tabla = a.aqui()
    for n, f in pares:
        a.d32(n).d32(f)
    for n in NATIVOS:
        a.d32(nombres[n]).d32(fun[n])
    a.d32(0).d32(0)
    return a.cerrar(), dict(tabla=tabla, cueva_teclado=cueva_teclado, cueva_barra=cueva_barra, modo=modo,
                            mascara=mascara, **{'f_' + k: v for k, v in fun.items()})


def lleva_el_parche(d) -> bool:
    return any(s['nombre'] == NOMBRE_SECCION for s in _secciones(d)[2])


def parchear(d: bytes):
    if lleva_el_parche(d):
        raise SystemExit('ya lleva el parche de teclas')
    d = bytearray(d)
    for va, orig in ((P1, P1_ORIG), (P2, P2_ORIG), (P3, P3_ORIG), (P4, P4_ORIG)):
        if bytes(d[_off(d, va):_off(d, va) + len(orig)]) != orig:
            raise SystemExit('%#x no tiene lo esperado: no es este angel.dat' % va)
    pares = _tabla_game(d)
    nombres_viejos = set()
    for n, _ in pares:
        o = _off(d, n)
        nombres_viejos.add(bytes(d[o:d.index(b'\0', o)]).decode('latin1'))
    if nombres_viejos & set(NATIVOS):
        raise SystemExit('la tabla game ya tiene alguno de estos nativos')
    pe, tabla_sec, secs = _secciones(d)
    opt = pe + 24
    al_sec = struct.unpack_from('<I', d, opt + 32)[0]
    al_arch = struct.unpack_from('<I', d, opt + 36)[0]
    tam_cab = struct.unpack_from('<I', d, opt + 60)[0]
    cab_nueva = tabla_sec + 40 * len(secs)
    if cab_nueva + 40 > tam_cab or any(d[cab_nueva:cab_nueva + 40]):
        raise SystemExit('no hay sitio para otra seccion en la cabecera')
    ultima = max(secs, key=lambda s: s['va'])
    va_rel = _alinear(ultima['va'] + max(ultima['vsz'], ultima['rsz']), al_sec)
    rptr = _alinear(len(d), al_arch)
    codigo, info = _codigo(_base(d) + va_rel, pares)
    rsz = _alinear(len(codigo), al_arch)
    d.extend(bytes(rptr - len(d)))
    d.extend(codigo + bytes(rsz - len(codigo)))
    # Lectura, escritura y ejecucion: los datos (modo, mascara) viven en la misma seccion.
    d[cab_nueva:cab_nueva + 40] = NOMBRE_SECCION + struct.pack('<IIIIIIHHI', len(codigo), va_rel, rsz, rptr,
                                                               0, 0, 0, 0, 0xE0000020)
    struct.pack_into('<H', d, pe + 6, len(secs) + 1)
    struct.pack_into('<I', d, opt + 56, _alinear(va_rel + len(codigo), al_sec))     # SizeOfImage

    def poner(va, datos):
        o = _off(d, va)
        d[o:o + len(datos)] = datos

    poner(P1, b'\x68' + struct.pack('<I', info['tabla']))
    poner(P2, b'\xe9' + struct.pack('<i', info['cueva_teclado'] - (P2 + 5)) + b'\x90')
    poner(P3, b'\x90\x90')
    poner(P4, b'\xe9' + struct.pack('<i', info['cueva_barra'] - (P4 + 5)) + b'\x90')
    return bytes(d), info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    d = pathlib.Path(a.entrada).read_bytes()
    if a.ver or not a.salida:
        print('lleva el parche de teclas' if lleva_el_parche(d) else 'no lleva el parche de teclas')
        return
    nuevo, info = parchear(d)
    pathlib.Path(a.salida).write_bytes(nuevo)
    print('escrito', a.salida, {k: hex(v) for k, v in info.items()})


if __name__ == '__main__':
    main()
