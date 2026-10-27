"""Desensamblador de los scripts Lua 5.1 compilados del cliente (SCRIPT\\*.L).

Uso:
    python tools/luac_dis.py archivo.luac [funcion ...]

Sin nombres lista todas las funciones; con nombres solo esas. Las funciones
se nombran por la global a la que se asignan (SETGLOBAL tras CLOSURE).
"""
import struct
import sys

OPS = ('MOVE LOADK LOADBOOL LOADNIL GETUPVAL GETGLOBAL GETTABLE SETGLOBAL SETUPVAL '
       'SETTABLE NEWTABLE SELF ADD SUB MUL DIV MOD POW UNM NOT LEN CONCAT JMP EQ LT LE '
       'TEST TESTSET CALL TAILCALL RETURN FORLOOP FORPREP TFORLOOP SETLIST CLOSE '
       'CLOSURE VARARG').split()


class Lector:
    def __init__(self, raw):
        self.b, self.i = raw, 0

    def u8(self):
        self.i += 1
        return self.b[self.i - 1]

    def i32(self):
        self.i += 4
        return struct.unpack_from('<i', self.b, self.i - 4)[0]

    def cadena(self):
        n = struct.unpack_from('<I', self.b, self.i)[0]
        self.i += 4
        s = self.b[self.i:self.i + n]
        self.i += n
        return s[:-1].decode('latin-1') if n else None

    def funcion(self):
        f = {'fuente': self.cadena(), 'linea': self.i32(), 'ultima': self.i32()}
        f['nups'], f['params'], f['vararg'], f['pila'] = self.u8(), self.u8(), self.u8(), self.u8()
        f['codigo'] = [self.i32() & 0xFFFFFFFF for _ in range(self.i32())]
        ks = []
        for _ in range(self.i32()):
            t = self.u8()
            if t == 0:
                ks.append(None)
            elif t == 1:
                ks.append(bool(self.u8()))
            elif t == 3:
                ks.append(struct.unpack_from('<d', self.b, self.i)[0])
                self.i += 8
            elif t == 4:
                ks.append(self.cadena())
            else:
                raise ValueError('constante de tipo %d' % t)
        f['k'] = ks
        f['hijas'] = [self.funcion() for _ in range(self.i32())]
        [self.i32() for _ in range(self.i32())]
        for _ in range(self.i32()):
            self.cadena(); self.i32(); self.i32()
        [self.cadena() for _ in range(self.i32())]
        return f


def cargar(raw):
    lec = Lector(raw)
    if raw[:4] != b'\x1bLua':
        raise ValueError('no es Lua compilado')
    lec.i = 12
    return lec.funcion()


def _rk(f, x):
    return repr(f['k'][x - 256]) if x >= 256 else 'R%d' % x


def listar(f):
    out = []
    for pc, ins in enumerate(f['codigo']):
        op = OPS[ins & 0x3F] if (ins & 0x3F) < len(OPS) else '?%d' % (ins & 0x3F)
        a, c, b = (ins >> 6) & 0xFF, (ins >> 14) & 0x1FF, (ins >> 23) & 0x1FF
        bx = ins >> 14
        sbx = bx - 131071
        if op in ('LOADK', 'GETGLOBAL', 'SETGLOBAL'):
            txt = 'R%d %r' % (a, f['k'][bx])
        elif op in ('GETTABLE', 'SELF'):
            txt = 'R%d R%d[%s]' % (a, b, _rk(f, c))
        elif op == 'SETTABLE':
            txt = 'R%d[%s] = %s' % (a, _rk(f, b), _rk(f, c))
        elif op in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'POW', 'EQ', 'LT', 'LE'):
            txt = '%d %s %s' % (a, _rk(f, b), _rk(f, c))
        elif op in ('JMP', 'FORLOOP', 'FORPREP'):
            txt = 'R%d -> %d' % (a, pc + 1 + sbx)
        elif op == 'CLOSURE':
            txt = 'R%d hija %d' % (a, bx)
        else:
            txt = 'A=%d B=%d C=%d' % (a, b, c)
        out.append('  %4d %-9s %s' % (pc, op, txt))
    return out


def con_nombres(principal):
    """{nombre global: funcion} siguiendo CLOSURE + SETGLOBAL en el bloque principal."""
    nombres = {}
    cod = principal['codigo']
    for pc, ins in enumerate(cod):
        if ins & 0x3F == OPS.index('CLOSURE') and pc + 1 < len(cod):
            sig = cod[pc + 1]
            if sig & 0x3F == OPS.index('SETGLOBAL'):
                nombres[principal['k'][sig >> 14]] = principal['hijas'][ins >> 14]
    return nombres


def main():
    raw = open(sys.argv[1], 'rb').read()
    principal = cargar(raw)
    nombres = con_nombres(principal)
    pedidas = sys.argv[2:] or list(nombres)
    print('constantes del bloque principal:')
    cod = principal['codigo']
    for pc, ins in enumerate(cod):
        if ins & 0x3F == OPS.index('LOADK') and pc + 1 < len(cod) and cod[pc + 1] & 0x3F == OPS.index('SETGLOBAL'):
            print('  %s = %r' % (principal['k'][cod[pc + 1] >> 14], principal['k'][ins >> 14]))
    for n in pedidas:
        if n in nombres:
            print('\nfunction %s' % n)
            print('\n'.join(listar(nombres[n])))


if __name__ == '__main__':
    main()
