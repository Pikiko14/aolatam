"""Comandos GM del chat solo para configuracion.USUARIOS_GM."""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import configuracion


class Ses:
    def __init__(self, usuario):
        self.usuario = usuario
        self.packets = []

    def enviar(self, *paquetes):
        self.packets.extend(paquetes)


@pytest.fixture(autouse=True)
def gms(monkeypatch):
    monkeypatch.setattr(configuracion, 'USUARIOS_GM', frozenset({'Admin'}))


@pytest.mark.parametrize('texto', [b'/item 25832 10', b'/level 200', b'/notice hola',
                                   b'/twstart 5', b'/item abc', b'/emote unlockall'])
def test_un_jugador_normal_no_ejecuta_comandos_gm(texto):
    s = Ses('test')
    assert app._gm_sin_permiso(s, texto, 'test')
    assert len(s.packets) == 1


@pytest.mark.parametrize('usuario', ['Admin', 'admin', 'ADMIN'])
def test_la_cuenta_gm_pasa_sin_distinguir_mayusculas(usuario):
    s = Ses(usuario)
    assert not app._gm_sin_permiso(s, b'/item 25832 10', 'test')
    assert not s.packets


@pytest.mark.parametrize('texto', [b'/emote 3', b'/emote list', b'/guild hola a todos',
                                   b'/sb hola', b'hola que tal'])
def test_comandos_de_jugador_y_chat_normal_siguen_abiertos(texto):
    s = Ses('test')
    assert not app._gm_sin_permiso(s, texto, 'test')
    assert not s.packets


def test_sin_cuenta_no_hay_gm():
    assert not configuracion.es_gm(None) and not configuracion.es_gm('')
