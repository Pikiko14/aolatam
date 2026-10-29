"""Lectura y escritura de mapas .mpc de Free Angels Online (formato descifrado con map002.mpc; ver herramientas/generar_mapa/mpc.py del proyecto Dos Coronas).

Cabecera de 96 bytes = 24 u32 (little-endian):
  [0] 'MAP\\0'  [1] ancho  [2] alto  [3] version  [4][5] tamano de celda (32)
  [6][7] objetos: desplazamiento y NUMERO de registros (74 bytes cada uno)       [8][9] eventos: desplazamiento y bytes (u32 longitud + XML UTF-8)
  [10] version de eventos  [11][12] reservados  [13][14] lista de tilesets: desplazamiento y bytes
  [15][16] dialogos: desplazamiento y bytes (u32 longitud + XML)                [17][18] rutas: desplazamiento y bytes
  [19][20] puntos: desplazamiento y NUMERO de registros                          [21..23] reservados
Cuadricula: ancho*alto celdas de 6 bytes (tileset de pincel, atributo de terreno, 0, capa de agua profunda, 0, 0).
Orden de las secciones en el archivo: cabecera, cuadricula, lista de tilesets, objetos, eventos, dialogos, rutas, puntos.
"""
import struct

HEAD = 96


def leer(d):
    if d[:4] != b'MAP\x00' or len(d) < HEAD:
        raise ValueError('no es un .mpc')
    h = list(struct.unpack('<24I', d[:HEAD]))
    w, hh = h[1], h[2]
    if not (0 < w <= 4096 and 0 < hh <= 4096) or HEAD + w * hh * 6 > len(d):
        raise ValueError('tamano de mapa no valido')
    cel = bytearray(d[HEAD:HEAD + w * hh * 6])
    extra = bytes(d[HEAD + w * hh * 6:h[13]])      # version >= 0x10006: un byte mas por celda (segunda capa); se conserva tal cual
    v6 = h[3] >= 0x10006                                      # v6: tilesets como u16 y h[14] = cuantos hay; v5: un byte cada uno y h[14] = bytes
    nts = h[14]
    tilesets = list(struct.unpack('<%dH' % nts, d[h[13]:h[13] + 2 * nts])) if v6 else list(d[h[13]:h[13] + nts])
    hueco = bytes(d[h[13] + (2 if v6 else 1) * nts:h[6]])            # datos desconocidos entre la lista de tilesets y los objetos (versiones nuevas): se conservan
    objs = []
    for i in range(h[7]):
        r = d[h[6] + i * 74:h[6] + (i + 1) * 74]
        id_, x, y, a, e, c = struct.unpack('<6I', r[:24])
        objs.append([id_, x, y, a, e, c, r[24:].hex()])
    ln = struct.unpack('<I', d[h[8]:h[8] + 4])[0]
    eventos = d[h[8] + 4:h[8] + 4 + ln].decode('utf-8', errors='replace')
    ln2 = struct.unpack('<I', d[h[15]:h[15] + 4])[0]
    dialogos = d[h[15] + 4:h[15] + 4 + ln2].decode('utf-8', errors='replace')
    rs = d[h[17]:h[17] + h[18]]
    n = struct.unpack('<I', rs[:4])[0]
    rutas, p = [], 4
    for _ in range(n):
        id_, uno, npts, cero = struct.unpack('<4I', rs[p:p + 16]); p += 16
        pts = []
        for _ in range(npts):
            x, y, t, a, b, c = struct.unpack('<6I', rs[p:p + 24]); p += 24
            pts.append([x, y, t, a, b, c])
        rutas.append(dict(id=id_, uno=uno, cero=cero, puntos=pts))
    ps, p = d[h[19]:], 0
    puntos = []
    for _ in range(h[20]):
        id_, npts = struct.unpack('<2I', ps[p:p + 8]); p += 8
        pts = []
        for _ in range(npts):
            pts.append(list(struct.unpack('<2I', ps[p:p + 8]))); p += 8
        puntos.append(dict(id=id_, puntos=pts))
    return dict(w=w, h=hh, cabecera=h, celdas=bytes(cel), extra=extra, hueco=hueco, tilesets=tilesets, objetos=objs, eventos=eventos, dialogos=dialogos,
                rutas=rutas, puntos=puntos, resto=ps[p:].hex(), bytes=len(d))


def escribir(m):
    w, hh = m['w'], m['h']
    cel = bytes(m['celdas'])
    if len(cel) != w * hh * 6:
        raise ValueError('la cuadricula no coincide con el tamano')
    h = list(m['cabecera'])
    h[1], h[2] = w, hh
    usados = list(m['tilesets'])                      # la lista la mantiene el editor (se conserva tal cual al abrir)
    out = bytearray(b'\0' * HEAD)
    out += cel
    ex = bytes(m.get('extra', b''))
    if ex and len(ex) != w * hh:
        ex = b''
    out += ex
    h[13], h[14] = len(out), len(usados)
    out += struct.pack('<%dH' % len(usados), *usados) if h[3] >= 0x10006 else bytes(usados)
    out += bytes(m.get('hueco', b''))
    h[6], h[7] = len(out), len(m['objetos'])
    for o in m['objetos']:
        out += struct.pack('<6I', *(int(v) & 0xFFFFFFFF for v in o[:6])) + bytes.fromhex(o[6] if len(o) > 6 and o[6] else '00' * 50)
    ev = m['eventos'].encode('utf-8')
    h[8], h[9] = len(out), 4 + len(ev)
    out += struct.pack('<I', len(ev)) + ev
    dg = m['dialogos'].encode('utf-8')
    h[15], h[16] = len(out), 4 + len(dg)
    out += struct.pack('<I', len(dg)) + dg
    h[17] = len(out)
    rb = bytearray(struct.pack('<I', len(m['rutas'])))
    for r in m['rutas']:
        rb += struct.pack('<4I', r['id'], r.get('uno', 1), len(r['puntos']), r.get('cero', 0))
        for p in r['puntos']:
            rb += struct.pack('<6I', p[0], p[1], p[2] if len(p) > 2 else 3, *(p[3:6] if len(p) >= 6 else (0, 0, 0)))
    h[18] = len(rb)
    out += rb
    h[19], h[20] = len(out), len(m['puntos'])
    for p in m['puntos']:
        out += struct.pack('<2I', p['id'], len(p['puntos']))
        for q in p['puntos']:
            out += struct.pack('<2I', q[0], q[1])
    out += bytes.fromhex(m.get('resto', ''))
    out[:HEAD] = struct.pack('<24I', *h)
    return bytes(out)


if __name__ == '__main__':
    import glob, os, sys
    ok = bad = 0
    for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'map', '*.mpc'))):
        d = open(f, 'rb').read()
        try:
            m = leer(d); e = escribir(m)
        except Exception as ex:
            print('ERROR', os.path.basename(f), ex); bad += 1; continue
        if e == d: ok += 1
        else:
            bad += 1
            dif = next((i for i in range(min(len(e), len(d))) if e[i] != d[i]), None)
            print('DIFIERE', os.path.basename(f), len(d), len(e), 'primer byte distinto', dif)
    print('identicos', ok, 'distintos', bad)
