"""
Bot de pruebas: un cliente falso que juega contra el servidor como un jugador.

Habla el protocolo real (proto/): Hello, AUTH de 73 B con la contrasena cifrada
igual que el cliente de Windows (server/clave_cliente.py), lista de personajes,
crear/borrar, 0x0006 -> redirect, entrada al mundo y despues los mensajes de
juego que manda el cliente de verdad (sacados de logs/sesiones/*_orden.jsonl).

Cada escenario es una lista de PASOS: un paso manda algo (o nada) y espera una
respuesta que cumpla una condicion. Si no llega a tiempo, el escenario falla y
se dice en que paso y que fue lo ultimo que llego.

Uso:
    py -3 tools/bot_pruebas.py                    # contra el servidor local (127.0.0.1:16768)
    py -3 tools/bot_pruebas.py --aislado          # arranca un servidor propio en puertos libres
                                                  # con una base temporal, y lo para al final
    py -3 tools/bot_pruebas.py --aislado --bots 8 # prueba de carga: 8 bots a la vez
    py -3 tools/bot_pruebas.py -e login,caminar   # solo esos escenarios

Las cuentas son propias (botprueba01, botprueba02...): se crean en la base que
use el servidor (data/cuentas.db, o la temporal con --aislado). No se toca
ninguna cuenta de jugador ni personajes.ROPA_INICIAL.

Al terminar se revisa el log del servidor: si aparece un Traceback desde que
empezo la prueba, falla aunque todos los pasos hayan pasado.

Sale con 0 si todo paso y con 1 si algo fallo.
"""
import argparse
import asyncio
import json
import os
import pathlib
import random
import socket
import struct
import subprocess
import sys
import tempfile
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'proto'))
sys.path.insert(0, str(RAIZ / 'server'))

from framing import HDR, decode_header, build_frame, submessages, pack_submessages  # noqa: E402
from handshake import parse_hello, XorEvolving, SEQ_HELLO  # noqa: E402

PREFIJO_CUENTA = 'botprueba'
CONTRASENA = 'bot1234'


class FalloPaso(Exception):
    pass


# ============================================================ conexion

class Conexion:
    """Una conexion TCP con el servidor (login o mundo), con el cifrado del cliente."""

    def __init__(self, nombre, log):
        self.nombre = nombre
        self.log = log
        self.reader = self.writer = None
        self.cifra = None
        self.seq = 1
        self.recibidos = []          # [(t, opcode, cuerpo)] todo lo que llego
        self._cursor = 0             # lo que ya se miro en esperar()
        self._nuevo = asyncio.Event()
        self._tarea = None
        self.cerrada = False

    async def abrir(self, host, puerto, timeout=10):
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(host, puerto), timeout)
        # Primer frame: el Hello (seq=0xFFFF, en claro) con la clave del C->S.
        buf = b''
        while True:
            buf += await asyncio.wait_for(self.reader.read(4096), timeout)
            if len(buf) >= HDR and len(buf) >= decode_header(buf, 0)['wire']:
                break
        h = decode_header(buf, 0)
        if h['seq'] != SEQ_HELLO:
            raise FalloPaso(f'{self.nombre}: el primer frame no es el Hello (seq={h["seq"]:#x})')
        clave = parse_hello(buf[HDR:HDR + h['length']])['key']
        self.cifra = XorEvolving(clave)
        self._resto = bytearray(buf[h['wire']:])
        self._tarea = asyncio.create_task(self._leer())

    async def _leer(self):
        buf = self._resto
        try:
            while True:
                self._trocear(buf)
                d = await self.reader.read(65536)
                if not d:
                    break
                buf.extend(d)
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            self.cerrada = True
            self._nuevo.set()

    def _trocear(self, buf):
        while len(buf) >= HDR:
            h = decode_header(buf, 0)
            if len(buf) < h['wire']:
                return
            cuerpo = bytes(buf[HDR:h['wire']])
            del buf[:h['wire']]
            if h['encrypted']:
                raise FalloPaso(f'{self.nombre}: el servidor mando un frame cifrado (no se espera)')
            if h['compressed']:
                import lzo
                cuerpo = lzo.descomprimir(cuerpo[:h['length']])
            else:
                cuerpo = cuerpo[:h['length']]
            msgs, _ = submessages(cuerpo)
            ahora = time.monotonic()
            for op, b in msgs:
                self.recibidos.append((ahora, op, b))
            if msgs:
                self._nuevo.set()

    def enviar(self, opcode, cuerpo=b''):
        if self.writer is None or self.writer.is_closing():
            raise FalloPaso(f'{self.nombre}: conexion cerrada al mandar 0x{opcode:04X}')
        payload = pack_submessages([struct.pack('<H', opcode) + bytes(cuerpo)])
        self.seq = self.seq + 1 if self.seq < 0x7FFE else 1
        self.writer.write(build_frame(payload, self.seq, self.cifra))

    def marcar(self):
        """A partir de aqui esperar() solo mira lo que llegue despues."""
        self._cursor = len(self.recibidos)

    async def esperar(self, cond, timeout=5.0, que=''):
        """Espera un sub-mensaje (opcode, cuerpo) que cumpla cond. Devuelve (opcode, cuerpo)."""
        fin = time.monotonic() + timeout
        while True:
            while self._cursor < len(self.recibidos):
                _, op, b = self.recibidos[self._cursor]
                self._cursor += 1
                try:
                    ok = cond(op, b)
                except Exception:
                    ok = False
                if ok:
                    return op, b
            if self.cerrada:
                raise FalloPaso(f'{self.nombre}: el servidor cerro la conexion esperando {que}')
            resto = fin - time.monotonic()
            if resto <= 0:
                ult = ', '.join(f'0x{op:04X}' for _, op, _ in self.recibidos[-12:])
                raise FalloPaso(f'{self.nombre}: no llego {que} en {timeout:.1f}s (ultimos: {ult or "nada"})')
            self._nuevo.clear()
            try:
                await asyncio.wait_for(self._nuevo.wait(), min(resto, 0.25))
            except asyncio.TimeoutError:
                pass

    async def drenar(self):
        if self.writer is not None:
            try:
                await self.writer.drain()
            except (ConnectionError, OSError):
                pass

    async def cerrar(self):
        if self.writer is not None:
            try:
                self.writer.close()
                await asyncio.wait_for(self.writer.wait_closed(), 2)
            except Exception:
                pass
        if self._tarea:
            self._tarea.cancel()


# ============================================================ base de datos

def apuntar_base(datos_dir):
    """Lleva cuentas.py a otra carpeta (la base temporal de --aislado).

    cuentas.py abre data/cuentas.db al importarse (CREATE TABLE IF NOT EXISTS: no cambia nada si ya
    existe); despues se cambian las rutas y se inicializa la nueva."""
    import cuentas
    if datos_dir is None:
        return cuentas
    d = pathlib.Path(datos_dir)
    d.mkdir(parents=True, exist_ok=True)
    cuentas.BASE = d
    cuentas.DB_PATH = d / 'cuentas.db'
    cuentas.BACKUPS_DIR = d / 'backups'
    cuentas.ARCHIVO = d / 'cuentas.json'
    cuentas._init_db()
    return cuentas


def preparar_cuenta(cuentas, usuario):
    """Crea la cuenta de prueba (con contrasena) si no esta. Nunca toca una cuenta que no sea del bot."""
    if not usuario.startswith(PREFIJO_CUENTA):
        raise ValueError(f'{usuario}: el bot solo usa cuentas {PREFIJO_CUENTA}*')
    cuentas.reservar_usuario(usuario, CONTRASENA)
    try:
        cuentas.desbanear(usuario)
    except Exception:
        pass


def ajustar_personaje(cuentas, usuario, char_id, **campos):
    """Cambia campos guardados del personaje de prueba (nivel, mapa, inventario...) antes de entrar."""
    def mutar(p):
        for k, v in campos.items():
            if isinstance(v, dict) and isinstance(p.get(k), dict):
                p[k].update(v)
            else:
                p[k] = v
    cuentas._actualizar_personaje(usuario, char_id, mutar)


# ============================================================ el bot

def auth_login(usuario, contrasena):
    """AUTH de 73 B como el cliente de Windows: usuario en claro y contrasena cifrada (clave_cliente)."""
    import clave_cliente
    a = bytearray(73)
    u = usuario.encode('ascii')[:20]
    a[0:len(u)] = u
    claro = contrasena.encode('ascii') + b'\x00'
    claro += bytes(random.randrange(1, 256) for _ in range(clave_cliente.LARGO - len(claro)))
    a[21:53] = clave_cliente.cifrar(claro)
    a[53:70] = os.urandom(17)
    return bytes(a)


def cuerpo_creacion(ranura, nombre):
    """0x0003 de la seleccion: [ranura][eleccion de apariencia x5][nombre...] (57 B, como el cliente)."""
    c = bytearray(57)
    c[0] = ranura
    c[1:6] = bytes([1, 0x0A, 0, 0, 0])
    n = nombre.encode('ascii')[:16]
    c[6:6 + len(n)] = n
    return bytes(c)


class Bot:
    def __init__(self, n, host, puerto, cuentas, log=print, sufijo='', cerrojo=None):
        self.n = n
        self.host, self.puerto = host, puerto
        self.cuentas = cuentas
        self.cerrojo = cerrojo
        self.usuario = f'{PREFIJO_CUENTA}{n:02d}{sufijo}'
        self.nombre = f'Botp{n:02d}{sufijo}'
        self.log = lambda m: log(f'[{self.usuario}] {m}')
        self.login = None
        self.mundo = None
        self.char_id = None
        self.entity_id = None
        self.pos = None
        self.datos = {}          # lo que van dejando los pasos para los siguientes

    # ---------------------------------------------------------------- login y entrada

    async def entrar_login(self):
        """Hello + AUTH; espera el 0x0000 con la cuenta (codigo de error 0)."""
        preparar_cuenta(self.cuentas, self.usuario)
        self.login = Conexion('login', self.log)
        await self.login.abrir(self.host, self.puerto)
        self.login.marcar()
        self.login.enviar(0x0002, auth_login(self.usuario, CONTRASENA))
        _, b = await self.login.esperar(lambda op, b: op == 0x0000, 10, '0x0000 (lista de personajes)')
        err = struct.unpack_from('<H', b, 0)[0]
        if err:
            raise FalloPaso(f'login rechazado: codigo {err}')
        self.login.enviar(0x0011, struct.pack('<I', 0x0B))       # lo manda el cliente detras del AUTH

    async def recrear_personaje(self, ranura=0):
        """Borra el personaje de prueba de la ranura (0x0004) y lo crea de nuevo (0x0003): asi cada
        corrida empieza igual, sin lo que dejo la anterior."""
        ya = [p for p in self.cuentas.lista_de_personajes(self.usuario) if p.get('ranura') == ranura]
        if ya:
            self.login.marcar()
            self.login.enviar(0x0004, bytes([ranura]) + bytes(33))
            await self.login.esperar(lambda op, b: op == 0x0000, 10, 'la lista tras borrar (0x0000)')
        self.login.marcar()
        self.login.enviar(0x0003, cuerpo_creacion(ranura, self.nombre))
        _, b = await self.login.esperar(lambda op, b: op == 0x0001, 10, 'la ficha nueva (0x0001)')
        err = struct.unpack_from('<H', b, 0)[0]
        if err:
            raise FalloPaso(f'crear personaje rechazado: codigo {err}')
        p = next(p for p in self.cuentas.lista_de_personajes(self.usuario) if p.get('ranura') == ranura)
        self.char_id = p['char_id']
        return p

    async def entrar_mundo(self, ranura=0):
        """0x0006 -> redirect (0x0004) -> conexion de mundo -> 0x0002 -> secuencia -> 0x0003 (mapa cargado).

        El servidor empareja la conexion de mundo con el login por IP (accesos.py): con varios bots
        desde 127.0.0.1 el traspaso va de a uno (cerrojo)."""
        async def traspaso():
            self.login.marcar()
            self.login.enviar(0x0006, bytes([ranura, 0, 0, 0]) + rb'\chr\i920b\1011_Wait.spr' + bytes(1))
            _, b = await self.login.esperar(lambda op, b: op == 0x0004, 10, 'el redirect (0x0004)')
            ip = b[7:23].split(b'\x00')[0].decode('ascii', 'replace')
            puerto = struct.unpack_from('<H', b, 23)[0]
            if ip in ('', '0.0.0.0'):
                ip = self.host
            self.mundo = Conexion('mundo', self.log)
            await self.mundo.abrir(ip, puerto)
            self.mundo.marcar()
            self.mundo.enviar(0x0002, bytes(33))
            _, ficha = await self.mundo.esperar(lambda op, b: op == 0x0002 and len(b) > 100, 15,
                                                'la ficha del personaje (0x0002)')
            return ficha
        if self.cerrojo is not None:
            async with self.cerrojo:
                ficha = await traspaso()
        else:
            ficha = await traspaso()
        # CHARACTER_DATA (proto/messages.py): [u32 entity_id][u32 flags][u32 x][u32 y]...
        self.entity_id, _, x, y = struct.unpack_from('<IIII', ficha, 0)
        self.pos = (x, y)
        await asyncio.sleep(0.3)
        self.mundo.enviar(0x0003)                               # "mapa cargado"
        self.mundo.enviar(0x0016, struct.pack('<BI', 0x1E, 1))  # lo manda el cliente detras
        await self.mundo.drenar()

    # ---------------------------------------------------------------- lo que ve el bot

    def entidades(self):
        """{entity_id: (nombre, x, y)} de lo que hay en el mapa, segun 0x0008 (aparece), 0x0005 (se mueve,
        en pixeles) y 0x0007 (desaparece), en el orden en que llegaron."""
        ents = {}
        for _, op, b in self.mundo.recibidos:
            if op == 0x000C:                                    # cambio de mapa: lo de antes ya no esta
                ents.clear()
            elif op == 0x0008 and len(b) >= 33:
                e, _, x, y = struct.unpack_from('<IIII', b, 0)
                ents[e] = (b[16:33].split(b'\x00')[0].decode('ascii', 'replace'), x, y)
            elif op == 0x0005 and len(b) >= 20:
                e, _, _, dx, dy = struct.unpack_from('<IIIII', b, 0)
                if e in ents:
                    ents[e] = (ents[e][0], dx // 32, dy // 32)
            elif op == 0x0007 and len(b) >= 4:
                ents.pop(struct.unpack_from('<I', b, 0)[0], None)
        return ents

    def muertos(self):
        """Entidades que el servidor dio por muertas (0x000A [muerto][quien] tipo 7)."""
        return {struct.unpack_from('<I', b, 0)[0] for _, op, b in self.mundo.recibidos
                if op == 0x000A and len(b) >= 12 and struct.unpack_from('<I', b, 8)[0] == 7}

    # ---------------------------------------------------------------- acciones (lo que manda el cliente)

    def mandar_mover(self, destino):
        """0x0004 MOVE_REQ: desde donde estoy hasta destino (casillas), una ruta de un tramo, en pixeles."""
        x, y = self.pos
        dx, dy = destino
        c = struct.pack('<HHBH', x * 32 + 16, y * 32 + 16, 1, random.randrange(0x10000))
        self.mundo.enviar(0x0004, c + struct.pack('<HH', dx * 32 + 16, dy * 32 + 16))

    async def mover(self, destino, timeout=5.0):
        """Anda y espera el acuse (0x006D) y el 0x0005 propio que lleva a destino. Devuelve la velocidad."""
        self.mundo.marcar()
        self.mandar_mover(destino)
        await self.mundo.esperar(lambda op, b: op == 0x006D, timeout, 'el acuse del movimiento (0x006D)')
        _, b = await self.mundo.esperar(
            lambda op, b: op == 0x0005 and struct.unpack_from('<I', b, 0)[0] == self.entity_id,
            timeout, 'el 0x0005 de mi personaje')
        _, cx, cy, dx, dy, vel = struct.unpack_from('<IIIIIH', b, 0)
        if (dx // 32, dy // 32) != tuple(destino):
            raise FalloPaso(f'pedi ir a {destino} y el servidor me lleva a {(dx // 32, dy // 32)}')
        # Lo que tarda en llegar: el servidor mide el golpe desde donde vas de verdad (posicion_actual).
        dist = max(abs(cx - dx), abs(cy - dy))
        await asyncio.sleep(dist / max(vel, 1) * 1.1 + 0.15)
        self.pos = tuple(destino)
        return vel

    async def matar(self, nombre_mob, timeout=60.0):
        """Persigue al bicho mas cercano con ese nombre y le pega (0x0016 0x0C + 0x0006 golpe basico) hasta
        que el servidor lo da por muerto. Devuelve su entity_id."""
        import combate
        cadencia = 1.25                     # el servidor rechaza golpes a menos de 1,15 s
        ents = self.entidades()
        vivos = [e for e, (n, _, _) in ents.items() if n == nombre_mob and e not in self.muertos()]
        if not vivos:
            raise FalloPaso(f'no hay ningun {nombre_mob} a la vista ({len(ents)} entidades)')
        x, y = self.pos
        obj = min(vivos, key=lambda e: max(abs(ents[e][1] - x), abs(ents[e][2] - y)))
        self.log(f'objetivo: {nombre_mob} {obj} en {ents[obj][1:]} (yo en {self.pos})')
        fin = time.monotonic() + timeout
        golpes = 0
        while time.monotonic() < fin:
            if obj in self.muertos():
                self.log(f'{nombre_mob} {obj} muerto tras {golpes} golpes')
                return obj
            e = self.entidades().get(obj)
            if e is None:
                raise FalloPaso(f'{nombre_mob} {obj} desaparecio sin morir')
            _, mx, my = e
            if max(abs(mx - self.pos[0]), abs(my - self.pos[1])) > 1:
                await self.mover((mx - 1 if mx > self.pos[0] else mx + 1 if mx < self.pos[0] else mx,
                                  my - 1 if my > self.pos[1] else my + 1 if my < self.pos[1] else my))
                continue
            self.mundo.enviar(0x0016, struct.pack('<BI', 0x0C, obj))      # fijar objetivo
            self.mundo.enviar(0x0006, struct.pack('<HIIIH', combate.ATAQUE_NORMAL, obj, 0, 0, 0))
            golpes += 1
            await asyncio.sleep(cadencia)
        raise FalloPaso(f'{nombre_mob} {obj} sigue vivo tras {timeout:.0f}s y {golpes} golpes')

    def saludo_lua(self):
        """0x002F [160][version][0]: lo que manda el cliente con el parche (subasta_ventana.CMD_SALUDO).
        Con eso el servidor le manda las ventanas Lua, entre ellas la invitacion a la raid con su id."""
        self.mundo.enviar(0x002F, struct.pack('<BII', 160, 1, 0))

    def raid(self, a, b=0):
        """0x002F [171][a][b]: la ventana de la raid (raid.procesar)."""
        self.mundo.enviar(0x002F, struct.pack('<BII', 171, a, b))

    async def cerrar(self):
        for c in (self.mundo, self.login):
            if c is not None:
                await c.cerrar()


# ============================================================ servidor aislado

def puerto_libre(n=3):
    """n puertos TCP consecutivos libres en 127.0.0.1."""
    for _ in range(200):
        base = random.randrange(20000, 60000)
        ok = True
        for p in range(base, base + n):
            s = socket.socket()
            try:
                s.bind(('127.0.0.1', p))
            except OSError:
                ok = False
            finally:
                s.close()
            if not ok:
                break
        if ok:
            return base
    raise RuntimeError('no hay puertos libres')


def servir_aislado(datos_dir, puerto, log_path):
    """Corre el servidor de verdad (app.Servidor) dentro de este proceso, pero:
       - con la base de cuentas en datos_dir (no data/cuentas.db),
       - sin sincronizar el cliente de C:/AO, sin generar el parche y sin el FTP/HTTP del launcher
         (tocan archivos del cliente y puertos fijos que ya usa el servidor local),
       - sin grabar sesiones, y con el log en log_path."""
    import logging
    os.environ['AO_GRABAR'] = '0'
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
    raiz.addHandler(fh)
    apuntar_base(datos_dir)
    import cliente_local
    import parche

    async def _sin_launcher():
        return []
    cliente_local.aplicar_modo_estacion = lambda *a, **k: 'sin tocar (bot)'
    cliente_local.quitar_logo_arranque = lambda *a, **k: False
    cliente_local.quitar_exclusion_ramas = lambda *a, **k: 0
    cliente_local.parchear_launcher = lambda *a, **k: None
    cliente_local.iniciar_servidores_launcher = _sin_launcher
    parche.generar = lambda *a, **k: {}
    import app
    # Los esquemas acotados por servicio (Msg.puertos) traen el puerto de mundo de siempre, 16769: con otro
    # puerto el servidor no parsea el MOVE_REQ y nadie se mueve. Se les suma el del servidor aislado.
    from codec import Msg
    for m in Msg.registry.values():
        if m.puertos and 16769 in m.puertos:
            m.puertos = tuple(m.puertos) + (puerto + 1,)
    try:
        import paks_cliente
        paks_cliente.asegurar_extraidos()
    except Exception:
        logging.getLogger('bot').exception('tablas del cliente')
    srv = app.Servidor('127.0.0.1', puerto, puerto + 2, puerto + 1)

    async def _sin_consola():
        await asyncio.Event().wait()
    srv._consola_gm = _sin_consola
    srv._cola_gm = _sin_consola
    asyncio.run(srv.correr())


class ServidorAislado:
    """Arranca `bot_pruebas.py --servir-aislado` en otro proceso y lo para al salir."""

    def __init__(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix='aobot_'))
        self.puerto = puerto_libre(3)
        self.log_path = self.dir / 'servidor.log'
        self.proc = None

    def arrancar(self, timeout=120):
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        self.proc = subprocess.Popen(
            [sys.executable, str(pathlib.Path(__file__).resolve()), '--servir-aislado',
             '--datos', str(self.dir / 'datos'), '--port', str(self.puerto),
             '--log-servidor', str(self.log_path)],
            cwd=str(RAIZ), env=env, stdout=subprocess.DEVNULL, stderr=open(self.dir / 'stderr.txt', 'wb'))
        fin = time.time() + timeout
        while time.time() < fin:
            if self.proc.poll() is not None:
                raise RuntimeError('el servidor aislado termino al arrancar:\n'
                                   + (self.dir / 'stderr.txt').read_text('utf-8', 'replace')[-3000:])
            try:
                with socket.create_connection(('127.0.0.1', self.puerto + 1), 0.5):
                    return
            except OSError:
                time.sleep(0.3)
        raise RuntimeError(f'el servidor aislado no abrio el puerto {self.puerto + 1} en {timeout}s')

    def parar(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ============================================================ main

def argumentos(argv=None):
    ap = argparse.ArgumentParser(description='Bot de pruebas de punta a punta contra el servidor.')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=16768, help='puerto de LOGIN del servidor')
    ap.add_argument('--aislado', action='store_true',
                    help='arrancar un servidor propio en puertos libres, con base temporal')
    ap.add_argument('--bots', type=int, default=1, help='cuantos bots a la vez (prueba de carga)')
    ap.add_argument('-e', '--escenarios', default='', help='lista separada por comas (por defecto, todos)')
    ap.add_argument('--log-servidor', default=None,
                    help='log del servidor a revisar (por defecto logs/hestia.log, o el del aislado)')
    ap.add_argument('--datos', default=None, help='carpeta de la base (la de cuentas.py si no se da)')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--servir-aislado', action='store_true', help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def main(argv=None):
    a = argumentos(argv)
    if a.servir_aislado:
        servir_aislado(a.datos, a.port, a.log_servidor)
        return 0
    return asyncio.run(correr(a))


if __name__ == '__main__':
    sys.exit(main())
