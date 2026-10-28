"""
Limites de red: conexiones por IP, ritmo de paquetes y freno de intentos de login.

Todo se ajusta con variables de entorno y el trafico local (127.0.0.1 / ::1)
queda exento, asi las pruebas en la PC no cambian. Poner un limite en 0 lo
desactiva.

    AO_MAX_CONEX_IP      conexiones simultaneas por IP        (default 12)
    AO_TIMEOUT_LOGIN     segundos sin datos en el login       (default 120)
    AO_TIMEOUT_MUNDO     segundos sin datos en el mundo       (default 900)
    AO_MAX_MSG_SEG       sub-mensajes por segundo por sesion  (default 300)
    AO_LOGIN_FALLOS      fallos de login antes de bloquear    (default 5)
    AO_LOGIN_VENTANA     ventana de esos fallos, en segundos  (default 300)
    AO_LOGIN_BLOQUEO     segundos de bloqueo                  (default 300)
"""
import os
import time
from collections import defaultdict, deque


def _num(nombre, defecto):
    try:
        return int(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


MAX_CONEX_IP = _num('AO_MAX_CONEX_IP', 12)
TIMEOUT_LOGIN = _num('AO_TIMEOUT_LOGIN', 120)
TIMEOUT_MUNDO = _num('AO_TIMEOUT_MUNDO', 900)
MAX_MSG_SEG = _num('AO_MAX_MSG_SEG', 300)
LOGIN_FALLOS = _num('AO_LOGIN_FALLOS', 5)
LOGIN_VENTANA = _num('AO_LOGIN_VENTANA', 300)
LOGIN_BLOQUEO = _num('AO_LOGIN_BLOQUEO', 300)

_LOCALES = ('127.0.0.1', '::1', 'localhost')


def es_local(ip):
    return str(ip) in _LOCALES


def timeout_de(rol):
    t = TIMEOUT_LOGIN if rol == 'login' else TIMEOUT_MUNDO
    return t if t > 0 else None


class Conexiones:
    """Cuenta las conexiones abiertas por IP."""

    def __init__(self):
        self.abiertas = defaultdict(int)

    def entrar(self, ip):
        """False si la IP ya llego al tope; si es True hay que llamar a salir()."""
        if not es_local(ip) and 0 < MAX_CONEX_IP <= self.abiertas[ip]:
            return False
        self.abiertas[ip] += 1
        return True

    def salir(self, ip):
        self.abiertas[ip] -= 1
        if self.abiertas[ip] <= 0:
            self.abiertas.pop(ip, None)


class Ritmo:
    """Cuenta sub-mensajes por segundo de una sesion."""

    def __init__(self):
        self.seg = 0
        self.n = 0

    def pasa(self, cuantos=1):
        """False si en este segundo ya se paso del maximo."""
        if MAX_MSG_SEG <= 0:
            return True
        ahora = int(time.monotonic())
        if ahora != self.seg:
            self.seg, self.n = ahora, 0
        self.n += cuantos
        return self.n <= MAX_MSG_SEG


class FrenoLogin:
    """Bloquea una IP (y un usuario) tras varios logins fallidos seguidos."""

    def __init__(self):
        self.fallos = defaultdict(deque)
        self.hasta = {}

    def _claves(self, ip, usuario):
        return (('ip', ip), ('u', str(usuario).lower()))

    def bloqueado(self, ip, usuario):
        """Segundos que faltan para que termine el bloqueo (0 = libre)."""
        if LOGIN_FALLOS <= 0 or es_local(ip):
            return 0
        ahora = time.monotonic()
        resto = 0
        for k in self._claves(ip, usuario):
            h = self.hasta.get(k, 0)
            if h > ahora:
                resto = max(resto, int(h - ahora) + 1)
            elif k in self.hasta:
                del self.hasta[k]
        return resto

    def fallo(self, ip, usuario):
        if LOGIN_FALLOS <= 0 or es_local(ip):
            return
        ahora = time.monotonic()
        for k in self._claves(ip, usuario):
            q = self.fallos[k]
            q.append(ahora)
            while q and ahora - q[0] > LOGIN_VENTANA:
                q.popleft()
            if len(q) >= LOGIN_FALLOS:
                self.hasta[k] = ahora + LOGIN_BLOQUEO
                q.clear()

    def acierto(self, ip, usuario):
        self.fallos.pop(('u', str(usuario).lower()), None)
        self.fallos.pop(('ip', ip), None)
