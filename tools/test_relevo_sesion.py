"""Un login con la contrasena buena cierra la sesion anterior de esa cuenta (05/11/2026).

"que no desconecte al 1 min": el tiempo sin datos vuelve a 15 min, y para no esperar a que caiga una sesion colgada,
el segundo intento la cierra; el siguiente entra.
"""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import limites  # noqa: E402
from accesos import Accesos  # noqa: E402


class Escritor:
    cerrado = False

    def close(self):
        self.cerrado = True


def test_el_segundo_login_cierra_la_sesion_colgada(monkeypatch):
    monkeypatch.setattr(app.login_server, 'usuario_de_auth', lambda c: 'Baco01')
    monkeypatch.setattr(app.cuentas, 'guardar_muestra_auth', lambda *a: None)
    monkeypatch.setattr(app.cuentas, 'validar', lambda u, c: ({'personajes': []}, 'ok'))
    srv = app.Servidor.__new__(app.Servidor)
    srv.accesos = Accesos()
    srv.freno_login = limites.FrenoLogin()
    vieja = NS(usuario='baco01', desconectado=False, writer=Escritor(), addr=('1.1.1.1', 1))
    assert srv.accesos.login(vieja, 'baco01')
    enviado = []
    nueva = NS(rol='login', personaje=None, usuario=None, enviar_crudo=enviado.append, enviar=lambda *a: None)
    srv.manejar(nueva, 0x0002, None, None, ('2.2.2.2', 2), b'x')
    assert vieja.writer.cerrado
