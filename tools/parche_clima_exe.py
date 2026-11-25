"""Climas propios en angel.dat: codigos 6+ del s2c 0x0015 sub 2 con sprites y velocidades propios (25/11/2026).

"agrega niebla y demas, crea los efectos tu". El cliente solo sabe 5 climas (server/mundo_vivo.py, EL CIELO DE
VERDAD): 1-3 lluvia, 4 nieve, 5 petalos. Medido con capstone sobre parches/juego/angel.dat (base 0x400000, sin relocs):

* CWeather::Set 0x684770 (thiscall, codigo, nivel): idx = codigo - 1 en [ebp-0x24]; en 0x6847A7
  "cmp [ebp-0x24],4; ja 0x684805" y la tabla 0x684888 ponen (tipo, sub) en [ebp-0x10], [ebp-0x14]; en 0x684805 crea
  la clase de particulas (vtable 0x8B4C40) y llama a su init(tipo, sub, cuantas). Con codigo > 5 el tipo quedaba
  sin poner. GANCHO 1: idx 0..4 como siempre; idx 5.. -> tipo 3 + (idx - 5), sub 0; fuera de la tabla, lluvia.
* init 0x4D09C0: elige el sprite por tipo (0 lluvia 0x4D0A5B, 1 nieve 0x4D0AA6, 2 petalos 0x4D0ABB) y si no, salta en
  0x4D0A56 (jmp 0x4D0AE1) sin sprite. GANCHO 2: tipo >= 3 -> sprite = 0x75E760(nombre de CLIMAS) en [this+0xC].
* En el bucle de particulas, 0x4D0B4E (jmp 0x4D0CA0) es el "otro tipo" del reparto de velocidades: vy en
  [[this+0x20]+i*4], vx en [[this+0x24]+i*4] (i en [ebp-4], tipo en [ebp-0x18]). GANCHO 3: tipo >= 3 ->
  vy = vy_min + rand() % vy_rango, vx = vx_min + rand() % vx_rango (rand = 0x82DFE6).
* El resto ya vale para cualquier tipo: el movimiento (0x4D0DE0) es x += vx, y += vy salvo los petalos (tipo 2), el
  dibujo (0x4D0CB0) pone cada particula modulo la pantalla y la pinta con 0x75C040 (modo de mezcla 4, translucido,
  el de la lluvia), y la luz (0x5B8770) oscurece con mas de 128 particulas.

Los sprites los dibuja tools/clima_sprites.py (parches/extras/shape/sf_aolat_*.shp -> SHAPE\\SF_AOLAT_*.SHP).

    python tools/parche_clima_exe.py <angel.dat de entrada> <salida>
    python tools/parche_clima_exe.py <angel.dat> --ver
"""
import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from parche_canal_lua import _alinear, _base, _off, _rel, _secciones  # noqa: E402
from parche_tooltip_verde import _Asm  # noqa: E402

NOMBRE_SECCION = b'.aolatw\0'

SET_EN = 0x6847A7
SET_ORIGINAL = bytes.fromhex('837ddc047758')            # cmp dword [ebp-0x24],4; ja 0x684805
SET_TABLA = 0x684888
SET_SIGUE = 0x684805
SPRITE_EN = 0x4D0A56
SPRITE_ORIGINAL = bytes.fromhex('e986000000')           # jmp 0x4D0AE1
SPRITE_SIGUE = 0x4D0AE1
VEL_EN = 0x4D0B4E
VEL_ORIGINAL = bytes.fromhex('e94d010000')              # jmp 0x4D0CA0
VEL_SIGUE = 0x4D0CA0
CARGAR_SPRITE = 0x75E760
RAND = 0x82DFE6
PRIMER_CODIGO = 6
TIPO_BASE = 3

# codigo -> (sprite, (vy_min, vy_rango), (vx_min, vx_rango)), en pixeles por paso. La lluvia va a 10..19 de vy y la
# nieve a 1..3 (init 0x4D09C0). vy > 0 baja, vx > 0 va a la derecha. Los codigos son los de server/mundo_vivo.py.
CLIMAS = {
    6: ('SF_AOLAT_FOG', (0, 1), (0, 2)),          # niebla: manchas grandes que apenas se mueven
    7: ('SF_AOLAT_EMBER', (-3, 3), (-1, 3)),      # brasas que suben (ola de calor)
    8: ('SF_AOLAT_ASH', (1, 2), (-1, 3)),         # ceniza roja que cae despacio (Luna de Sangre)
    9: ('SF_AOLAT_LEAF', (1, 3), (2, 3)),         # hojas con viento
    10: ('SF_AOLAT_FIREFLY', (-1, 3), (-1, 3)),   # luciernagas que flotan
    11: ('SF_AOLAT_SAND', (0, 3), (8, 7)),        # tormenta de arena, casi horizontal
    12: ('SF_AOLAT_BLOODRAIN', (10, 10), (0, 2)), # lluvia de sangre
    13: ('SF_AOLAT_STAR', (3, 3), (2, 2)),        # polvo de estrellas
}
TAM_ENTRADA = 24        # [nombre][0][vy_min][vy_rango][vx_min][vx_rango]


def lleva_el_parche(d) -> bool:
    return any(s['nombre'] == NOMBRE_SECCION for s in _secciones(d)[2])


def _codigo(va):
    codigos = sorted(CLIMAS)
    assert codigos == list(range(PRIMER_CODIGO, PRIMER_CODIGO + len(codigos)))
    n = len(codigos)
    a = _Asm(va)

    # --- gancho 1, en CWeather::Set
    a.et('set')
    a.b('8b45dc 83f804 77 07')                              # mov eax,[ebp-0x24]; cmp eax,4; ja +7
    a.b('ff2485'); a.c += struct.pack('<I', SET_TABLA)      # jmp [eax*4+0x684888]
    a.b('83e8%02x' % (PRIMER_CODIGO - 1))                   # sub eax,5
    a.b('3d'); a.c += struct.pack('<I', n)                  # cmp eax,n
    a.b('73'); a.rel8('set_otro')                           # jae
    a.b('83c0%02x 8945f0 c745ec00000000' % TIPO_BASE)       # add eax,3; [ebp-0x10]=tipo; [ebp-0x14]=0
    a.jmp(SET_SIGUE)
    a.et('set_otro')
    a.b('c745f000000000 c745ec00000000')                    # lluvia suave
    a.jmp(SET_SIGUE)

    # --- gancho 2, el sprite en init
    a.et('sprite')
    a.b('8b45ec 83e8%02x' % TIPO_BASE)                      # mov eax,[ebp-0x14]; sub eax,3
    a.b('3d'); a.c += struct.pack('<I', n)
    a.b('0f83'); a.c += struct.pack('<i', SPRITE_SIGUE - (a.va + len(a.c) + 4))   # jae fuera
    a.b('6bc0%02x ffb0' % TAM_ENTRADA); a.abs32('tabla')    # imul eax,24; push [eax+tabla]
    a.call(CARGAR_SPRITE)
    a.b('83c404 8b4df0 89410c')                             # add esp,4; ecx=this; [this+0xc]=sprite
    a.jmp(SPRITE_SIGUE)

    # --- gancho 3, la velocidad de cada particula
    a.et('vel')
    a.b('8b45e8 83e8%02x' % TIPO_BASE)                      # mov eax,[ebp-0x18]; sub eax,3
    a.b('3d'); a.c += struct.pack('<I', n)
    a.b('0f83'); a.c += struct.pack('<i', VEL_SIGUE - (a.va + len(a.c) + 4))
    a.b('6bc0%02x 50' % TAM_ENTRADA)                        # imul eax,24; push eax
    for campo_min, campo_rango, arreglo in ((8, 12, 0x20), (16, 20, 0x24)):
        a.call(RAND)
        a.b('8b0c24 99 f7b9'); a.abs32('tabla_%d' % campo_rango)     # ecx=[esp]; cdq; idiv [ecx+tabla+rango]
        a.b('0391'); a.abs32('tabla_%d' % campo_min)                  # add edx,[ecx+tabla+min]
        a.b('8b45f0 8b40%02x 8b4dfc 891488' % arreglo)                # [[this+arr]+i*4] = edx
    a.b('83c404')
    a.jmp(VEL_SIGUE)

    while len(a.c) % 4:
        a.c += b'\xcc'
    a.et('tabla')
    for k in (8, 12, 16, 20):
        a.etiquetas['tabla_%d' % k] = a.etiquetas['tabla'] + k
    nombres_pos = []
    for c in codigos:
        sprite, (vy0, vyr), (vx0, vxr) = CLIMAS[c]
        assert vyr >= 1 and vxr >= 1
        nombres_pos.append(len(a.c))
        a.c += struct.pack('<IIiiii', 0, 0, vy0, vyr, vx0, vxr)
    for c, pos in zip(codigos, nombres_pos):
        struct.pack_into('<I', a.c, pos, a.va + len(a.c))
        a.c += CLIMAS[c][0].encode('ascii') + b'\0'
    codigo = a.fin()
    return codigo, {k: a.etiquetas[k] for k in ('set', 'sprite', 'vel', 'tabla')}


def parchear(d: bytes) -> bytes:
    if lleva_el_parche(d):
        raise SystemExit('ya lleva los climas propios')
    d = bytearray(d)
    for va, orig in ((SET_EN, SET_ORIGINAL), (SPRITE_EN, SPRITE_ORIGINAL), (VEL_EN, VEL_ORIGINAL)):
        o = _off(d, va)
        if d[o:o + len(orig)] != orig:
            raise SystemExit('%#x no es lo esperado: no es este angel.dat' % va)
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
    codigo, e = _codigo(_base(d) + va_rel)
    rsz = _alinear(len(codigo), al_arch)
    d.extend(bytes(rptr - len(d)))
    d.extend(codigo + bytes(rsz - len(codigo)))
    d[cab_nueva:cab_nueva + 40] = NOMBRE_SECCION + struct.pack('<IIIIIIHHI', len(codigo), va_rel, rsz, rptr,
                                                               0, 0, 0, 0, 0x60000020)   # codigo, leer, ejecutar
    struct.pack_into('<H', d, pe + 6, len(secs) + 1)
    struct.pack_into('<I', d, opt + 56, _alinear(va_rel + len(codigo), al_sec))       # SizeOfImage
    o = _off(d, SET_EN)
    d[o:o + len(SET_ORIGINAL)] = b'\xe9' + _rel(SET_EN, e['set']) + b'\x90'
    o = _off(d, SPRITE_EN)
    d[o:o + 5] = b'\xe9' + _rel(SPRITE_EN, e['sprite'])
    o = _off(d, VEL_EN)
    d[o:o + 5] = b'\xe9' + _rel(VEL_EN, e['vel'])
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    d = pathlib.Path(a.entrada).read_bytes()
    if a.ver or not a.salida:
        print('lleva los climas propios' if lleva_el_parche(d) else 'no lleva los climas propios')
        return
    pathlib.Path(a.salida).write_bytes(parchear(d))
    print('escrito', a.salida)


if __name__ == '__main__':
    main()
