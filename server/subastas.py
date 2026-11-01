"""Casa de subastas con las ventanas NATIVAS del puesto de venta (Stall): venta directa, sin pujas.

Pedido del usuario el 31/10/2026 ("debe ser una pestana nativa", "Nativa, venta directa"). El cliente no trae
subastas, pero si los puestos de jugadores, y esas ventanas se pueden llenar con lo que queramos:

* EL SUBASTADOR es un personaje falso ("Auction House") parado en el Angel Lyceum con el cartel de puesto encima
  (presencia.paquetes_puesto: 0x000A accion 10 + 0x0043). Al pinchar el cartel el cliente manda el 0x0024 de ver un
  puesto y se le contesta con el 0x0032 de siempre, armado con lo que hay en venta (los MAX_VISTA mas nuevos).
* PUBLICAR: abrir tu puesto normal (0x0022, la misma ventana de precios) a DIST_PUBLICAR casillas o menos del
  subastador. En vez de quedarte vendiendo, lo de la pestana Sell pasa a la subasta (con sus mejoras, gemas o la
  ficha de la mascota) y puedes irte. Lo de la pestana Buy no se usa.
* COMPRAR: el 0x0025 de comprar en un puesto. El vendedor cobra el precio menos COMISION aunque este desconectado.
* RETIRAR: comprar algo tuyo te lo devuelve sin pagar.

Lo publicado se guarda en data/subastas.db, asi que sobrevive a los reinicios.
"""
import copy
import json
import logging
import pathlib
import sqlite3
import struct
import threading
import time

log = logging.getLogger('subastas')

STAGE = 41                          # Angel Lyceum
CASILLA = (167, 91)                 # a seis pasos de donde se aparece (app.REVIVIR_LYCEUM = 173, 91)
ENTIDAD = 79_000_001                # fuera de los rangos de presencia (jugadores 2001+, monstruos 50M, objetos 60M)
NOMBRE = 'Auction House'
HAWK = 'Auction House: open your stall here to sell'
ESTILO = 6                          # el cartel mas vistoso (0..6)
DIST_PUBLICAR = 6
MAX_VISTA = 50                      # el 0x0032 lleva el indice 20+i y el cliente solo acepta hasta 94
MAX_POR_VENDEDOR = 20
COMISION = 0.05
ORO_MAX = 2_000_000_000

DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'subastas.db'
_LOCK = threading.RLock()


def _con():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('''CREATE TABLE IF NOT EXISTS subastas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT NOT NULL, char_id INTEGER NOT NULL, vendedor TEXT NOT NULL,
        item_id INTEGER NOT NULL, cantidad INTEGER NOT NULL, precio INTEGER NOT NULL,
        mejoras TEXT, mascota TEXT, creado REAL NOT NULL)''')
    return con


def listado(limite=MAX_VISTA):
    """Lo que hay en venta, lo mas nuevo primero."""
    with _LOCK:
        con = _con()
        try:
            filas = con.execute('SELECT id, usuario, char_id, vendedor, item_id, cantidad, precio, mejoras, mascota '
                                'FROM subastas WHERE cantidad > 0 ORDER BY id DESC LIMIT ?', (int(limite),)).fetchall()
        finally:
            con.close()
    claves = ('id', 'usuario', 'char_id', 'vendedor', 'item_id', 'cantidad', 'precio', 'mejoras', 'mascota')
    salida = []
    for f in filas:
        d = dict(zip(claves, f))
        d['mejoras'] = json.loads(d['mejoras']) if d['mejoras'] else None
        d['mascota'] = json.loads(d['mascota']) if d['mascota'] else None
        salida.append(d)
    return salida


def cuantas_de(char_id) -> int:
    with _LOCK:
        con = _con()
        try:
            return con.execute('SELECT COUNT(*) FROM subastas WHERE char_id = ? AND cantidad > 0',
                               (int(char_id),)).fetchone()[0]
        finally:
            con.close()


def instancia(fila_id) -> bytes:
    """La instancia de 8 bytes con que la ventana del puesto identifica cada publicacion."""
    return struct.pack('<Q', 0x5A00000000000000 | int(fila_id))


def id_de_instancia(inst8):
    v = struct.unpack('<Q', inst8)[0]
    return v & 0xFFFFFFFF if (v >> 56) == 0x5A else None


# ------------------------------------------------------------------ el subastador en el mapa

def en_su_mapa(stage) -> bool:
    return stage == STAGE


def presentacion(stage):
    """Los paquetes que dibujan al subastador y su cartel; [] fuera de su mapa."""
    if not en_su_mapa(stage):
        return []
    import presencia
    b = bytearray(presencia.PLANTILLA)
    struct.pack_into('<I', b, presencia.OFF_ENTIDAD, ENTIDAD)
    struct.pack_into('<I', b, 4, 0)
    struct.pack_into('<I', b, presencia.OFF_X, CASILLA[0])
    struct.pack_into('<I', b, presencia.OFF_Y, CASILLA[1])
    n = NOMBRE.encode('ascii')[:presencia.TAM_NOMBRE - 1]
    b[presencia.OFF_NOMBRE:presencia.OFF_NOMBRE + presencia.TAM_NOMBRE] = n + bytes(presencia.TAM_NOMBRE - len(n))
    b[61] = 0
    spawn = struct.pack('<H', presencia.APARECE) + bytes(b)
    hawk = HAWK.encode('latin-1')[:48]
    return [spawn,
            struct.pack('<HIIBBH', 0x000A, ENTIDAD, 0, 10, ESTILO, 0),
            struct.pack('<HIB', 0x0043, ENTIDAD, 0) + hawk + b'\x00']


def cerca(ses) -> bool:
    p = getattr(ses, 'personaje', None)
    if p is None or not en_su_mapa(getattr(p, 'stage', None)):
        return False
    return max(abs(int(p.tile_x) - CASILLA[0]), abs(int(p.tile_y) - CASILLA[1])) <= DIST_PUBLICAR


# ------------------------------------------------------------------ la ventana (0x0032)

class _Personaje:
    def __init__(self):
        self.nombre, self.char_id, self.entity_id = NOMBRE, 1, ENTIDAD
        self.mejoras, self.mascotas, self.mascota = {}, {}, None
        self._instancias = {}


class _Vendedor:
    """Lo que app._paquete_vista_puesto necesita de una sesion, armado con lo publicado."""

    def __init__(self, filas):
        self.personaje = _Personaje()
        self.inventario, self.cantidades, self.usuario = {}, {}, None
        ventas = []
        for i, f in enumerate(filas):
            r = 20 + i
            self.inventario[r] = int(f['item_id'])
            self.cantidades[r] = int(f['cantidad'])
            self.personaje._instancias[r] = instancia(f['id'])
            if f.get('mejoras'):
                self.personaje.mejoras[r] = copy.deepcopy(f['mejoras'])
            if f.get('mascota'):
                self.personaje.mascotas[str(r)] = dict(f['mascota'], ranura=r)
            ventas.append({'instancia': instancia(f['id']), 'ranura': r, 'item_id': int(f['item_id']),
                           'cantidad': int(f['cantidad']), 'precio': int(f['precio'])})
        self.puesto = {'hawk': HAWK, 'ventas': ventas, 'compras': []}
        self.instancias = self.personaje._instancias
        self._instancias_personaje = self.personaje


def vista():
    """El 0x0032 con lo que hay en venta."""
    import app
    return app._paquete_vista_puesto(_Vendedor(listado()))


# ------------------------------------------------------------------ publicar

def publicar(ses, ventas):
    """Pasa a la subasta lo de la pestana Sell (las `ventas` ya validadas por el 0x0022). Devuelve cuantas."""
    import app
    import clases
    import inventario as iv
    p = ses.personaje
    libres = MAX_POR_VENDEDOR - cuantas_de(p.char_id)
    hechas, tocadas = 0, []
    for v in ventas:
        if libres <= 0:
            ses.enviar(clases.aviso('You can have at most %d items in the Auction House.' % MAX_POR_VENDEDOR,
                                    tipo=0))
            break
        r, item_id = int(v['ranura']), int(v['item_id'])
        if ses.inventario.get(r) != item_id:
            continue
        cant = min(int(v['cantidad']), app._cant_de(ses, r))
        if cant <= 0:
            continue
        mej = mas = None
        if not iv.es_apilable(item_id):
            mej = copy.deepcopy((getattr(p, 'mejoras', None) or {}).get(r)) or None
            pets = getattr(p, 'mascotas', None) or {}
            mas = copy.deepcopy(pets.get(str(r)) or pets.get(r)) or None
            if mas and mas.get('fuera'):
                ses.enviar(clases.aviso('Unsummon your pet before selling it.', tipo=0))
                continue
        sacadas = app._sacar(ses, r, cant)
        if sacadas <= 0:
            continue
        if r not in ses.inventario:
            (getattr(p, 'mejoras', None) or {}).pop(r, None)
        if mas is not None:
            for k in (str(r), r):
                (getattr(p, 'mascotas', None) or {}).pop(k, None)
            for k in ('fuera', 'entidad', 'ranura', 'instancia'):
                mas.pop(k, None)
        with _LOCK:
            con = _con()
            try:
                con.execute('INSERT INTO subastas (usuario, char_id, vendedor, item_id, cantidad, precio, mejoras, '
                            'mascota, creado) VALUES (?,?,?,?,?,?,?,?,?)',
                            (getattr(ses, 'usuario', '') or '', int(p.char_id), p.nombre, item_id, sacadas,
                             int(v['precio']), json.dumps(mej) if mej else None, json.dumps(mas) if mas else None,
                             time.time()))
                con.commit()
            finally:
                con.close()
        hechas += 1
        libres -= 1
        tocadas.append(r)
        log.info('%s publica %dx %s a %d', p.nombre, sacadas, item_id, int(v['precio']))
    if tocadas:
        ses.enviar(*app._refrescar(ses, tocadas),
                   clases.aviso('%d item(s) placed in the Auction House. You can leave now.' % hechas, tipo=0))
        app._guardar_bolsa(ses, p.char_id)
        if getattr(ses, 'usuario', None):
            import cuentas
            cuentas.guardar_mejoras(ses.usuario, p.char_id, getattr(p, 'mejoras', {}) or {})
    return hechas


# ------------------------------------------------------------------ comprar o retirar

def _pagar_al_vendedor(fila, oro):
    """Le da el oro al vendedor: en memoria si esta conectado, en la base si no."""
    import app
    import clases
    vend = next((s for s in app._tw_sesiones()
                 if getattr(s, 'personaje', None) and int(s.personaje.char_id) == int(fila['char_id'])), None)
    if vend is not None:
        vend.oro = min(ORO_MAX, getattr(vend, 'oro', 0) + oro)
        vend.personaje.oro = vend.oro
        vend.enviar(*app._refrescar(vend, [], con_oro=True),
                    clases.aviso('Auction House: your %s sold. You received %d Gold.'
                                 % (app._nombre_item(fila['item_id']), oro), tipo=0))
        vend.volcar()
        if getattr(vend, 'usuario', None):
            import cuentas
            cuentas.guardar_oro(vend.usuario, vend.personaje.char_id, vend.oro)
        return
    if fila.get('usuario'):
        import cuentas

        def _mut(p):
            p['oro'] = min(ORO_MAX, int(p.get('oro', 0) or 0) + int(oro))
        cuentas._actualizar_personaje(fila['usuario'], int(fila['char_id']), _mut)


def comprar(ses, cuerpo):
    """El 0x0025 sobre el subastador: <II eid, n> + n x <8sI instancia, cantidad>."""
    import app
    import clases
    import inventario as iv
    n = struct.unpack_from('<I', cuerpo, 4)[0]
    p = ses.personaje
    tocadas, avisos, pagado = [], [], 0
    off = 8
    for _ in range(min(int(n), MAX_VISTA)):
        if off + 12 > len(cuerpo):
            break
        inst8, pedida = struct.unpack_from('<8sI', cuerpo, off)
        off += 12
        fid = id_de_instancia(inst8)
        if fid is None or pedida <= 0:
            continue
        with _LOCK:
            con = _con()
            try:
                f = con.execute('SELECT id, usuario, char_id, vendedor, item_id, cantidad, precio, mejoras, mascota '
                                'FROM subastas WHERE id = ? AND cantidad > 0', (fid,)).fetchone()
                if not f:
                    avisos.append(clases.aviso('That item is no longer for sale.', tipo=0))
                    continue
                fila = dict(zip(('id', 'usuario', 'char_id', 'vendedor', 'item_id', 'cantidad', 'precio',
                                 'mejoras', 'mascota'), f))
                propio = int(fila['char_id']) == int(p.char_id)
                cant = min(int(pedida), int(fila['cantidad']))
                costo = 0 if propio else cant * int(fila['precio'])
                if getattr(ses, 'oro', 0) < costo:
                    avisos.append(clases.aviso('Not enough Gold.', tipo=0))
                    break
                item_id = int(fila['item_id'])
                if not (iv.es_apilable(item_id) and any(
                        int(it) == item_id and int(rk) != iv.RANURA_ORO and not iv.es_equipo(int(rk))
                        for rk, it in ses.inventario.items())) and app._ranura_libre(ses.inventario) is None:
                    avisos.append(clases.aviso('Your backpack is full.', tipo=0))
                    break
                r = app._meter(ses, item_id, cant)
                if r is None:
                    avisos.append(clases.aviso('Your backpack is full.', tipo=0))
                    break
                con.execute('UPDATE subastas SET cantidad = cantidad - ? WHERE id = ?', (cant, fid))
                con.execute('DELETE FROM subastas WHERE cantidad <= 0')
                con.commit()
            finally:
                con.close()
        if fila['mejoras']:
            if getattr(p, 'mejoras', None) is None:
                p.mejoras = {}
            p.mejoras[int(r)] = json.loads(fila['mejoras'])
        if fila['mascota']:
            if not isinstance(getattr(p, 'mascotas', None), dict):
                p.mascotas = {}
            pet = json.loads(fila['mascota'])
            pet.update(ranura=int(r), item=item_id, instancia=1000 + int(r), fuera=False, entidad=None)
            p.mascotas[str(r)] = pet
        tocadas.append(int(r))
        nom = app._nombre_item(item_id)
        if propio:
            avisos.append(clases.aviso('Withdrawn from the Auction House: %s' % nom, tipo=0))
        else:
            ses.oro = max(0, getattr(ses, 'oro', 0) - costo)
            p.oro = ses.oro
            pagado += costo
            avisos.append(clases.aviso(nom if cant == 1 else '%dx %s' % (cant, nom), tipo=0, msg_id=clases.MSG_ITEM))
            _pagar_al_vendedor(fila, int(costo * (1.0 - COMISION)))
        log.info('%s %s %dx %s (subasta %d) por %d', p.nombre, 'retira' if propio else 'compra', cant, item_id,
                 fid, costo)
    if not tocadas:
        if avisos:
            ses.enviar(*avisos)
        return
    salida = list(app._refrescar(ses, tocadas, con_oro=True))
    if pagado:
        salida.append(clases.aviso('%d Gold' % pagado, tipo=0, msg_id=clases.MSG_PAGO))
    ses.enviar(*salida, *avisos, vista())
    app._guardar_bolsa(ses, p.char_id)
    if getattr(ses, 'usuario', None):
        import cuentas
        cuentas.guardar_oro(ses.usuario, p.char_id, ses.oro)
        cuentas.guardar_mejoras(ses.usuario, p.char_id, getattr(p, 'mejoras', {}) or {})
