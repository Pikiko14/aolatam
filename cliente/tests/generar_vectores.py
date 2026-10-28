"""Genera cliente/tests/vectores.lua: casos que produce el servidor Python (proto/) para comprobar que net.lua da EXACTAMENTE lo mismo.

    python -I cliente/tests/generar_vectores.py
"""
import pathlib
import random
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'proto'))
sys.path.insert(0, str(RAIZ / 'server'))
import framing as fr          # noqa: E402
import handshake as hs        # noqa: E402

random.seed(28102026)
H = lambda b: bytes(b).hex()


def aleatorio(n):
    return bytes(random.randrange(256) for _ in range(n))


def lua_lista(items):
    return '{\n' + ''.join('  %s,\n' % i for i in items) + '}'


# 1) checksum
checks = []
for n in (0, 1, 2, 3, 7, 16, 33, 64, 200, 1001):
    p = aleatorio(n)
    checks.append('{ payload = "%s", csum = %d }' % (H(p), fr.checksum(p, len(p))))

# 2) frames en claro
claro = []
for n, seq in ((4, 1), (20, 2), (70, 3), (255, 0x7FFE)):
    p = aleatorio(n)
    f = fr.build_frame(p, seq)
    h = fr.decode_header(f)
    claro.append('{ payload = "%s", seq = %d, frame = "%s", length = %d, flags = %d, wire = %d }' % (H(p), seq, H(f), h['length'], h['flags'], h['wire']))

# 3) frames cifrados con la clave evolutiva (el estado cambia de un frame al siguiente, por eso es una SECUENCIA)
clave = bytes(range(1, 17))
cripto = hs.XorEvolving(clave)
cif = []
for n, seq in ((9, 1), (30, 2), (31, 3), (4, 4)):
    p = aleatorio(n)
    f = fr.build_frame(p, seq, cripto)
    h = fr.decode_header(f)
    cif.append('{ payload = "%s", seq = %d, frame = "%s", length = %d, flags = %d, wire = %d }' % (H(p), seq, H(f), h['length'], h['flags'], h['wire']))

# 4) lo mismo con la clave en cero (la que usa nuestro servidor: sigue evolucionando)
cripto0 = hs.XorEvolving(bytes(16))
cero = []
for n, seq in ((13, 1), (13, 2), (40, 3)):
    p = aleatorio(n)
    cero.append('{ payload = "%s", seq = %d, frame = "%s" }' % (H(p), seq, H(fr.build_frame(p, seq, cripto0))))

# 5) sub-mensajes
sub = [struct.pack('<H', 0x0005) + b'\x01\x02\x03\x04', struct.pack('<H', 0x0013) + aleatorio(8), struct.pack('<H', 0x000E) + b'hola\x00']
payload = fr.pack_submessages(sub)
msgs, _ = fr.submessages(payload)
subs = '{ payload = "%s", n = %d, opcodes = {%s} }' % (H(payload), len(msgs), ', '.join(str(o) for o, _ in msgs))

# 6) Hello: el que manda NUESTRO servidor (plantilla con cifrador embebido) y el minimo
plantilla = (RAIZ / 'server' / 'plantillas').glob('hello*.bin')
hellos = []
for f in sorted(plantilla):
    if 'archivos' in f.name:
        continue
    pl = f.read_bytes()
    r = hs.parse_hello(pl)
    hellos.append('{ nombre = "%s", payload = "%s", key = "%s", variante = "%s" }' % (f.name, H(pl), H(r['key']), r['variante']))
minimo = hs.build_hello(bytes(range(16)))
hellos.append('{ nombre = "minimo", payload = "%s", key = "%s", variante = "minima" }' % (H(minimo), H(bytes(range(16)))))

salida = RAIZ / 'cliente' / 'tests' / 'vectores.lua'
salida.write_text(
    '-- GENERADO por generar_vectores.py a partir de proto/ (no editar a mano)\n'
    'return {\n'
    '  checksum = %s,\n  claro = %s,\n  clave = "%s",\n  cifrado = %s,\n  cero = %s,\n  sub = %s,\n  hello = %s,\n}\n'
    % (lua_lista(checks), lua_lista(claro), H(clave), lua_lista(cif), lua_lista(cero), subs, lua_lista(hellos)),
    encoding='utf-8', newline='\n')
print('escrito', salida, '-', len(checks), 'checksums,', len(claro), 'claros,', len(cif), 'cifrados,', len(hellos), 'hello')
