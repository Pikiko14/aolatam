"""El BattlefieldAngel de las ciudades saluda con sus opciones de registro (05/11/2026).

"sigue sin funcionar el battlefield angel": en las plantillas de las cuatro ciudades el Angel de registro se llama
'BattlefieldAngel' y caia en la regla generica, que solo manda el 50001 sin opciones.
"""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import dialogos  # noqa: E402


def _cuerpo(stage, registrado):
    lineas = dialogos.propio('BattlefieldAngel', jugador='Pipe', stage=stage, registrado=registrado)
    assert lineas
    return bytes(lineas[0])


def test_breeze_woods_ofrece_registrarse():
    b = _cuerpo(29, False)
    for opcion in (50002, 50003, 50004, 50018, 50005):
        assert struct.pack('<I', opcion) in b


def test_registrado_ya_no_ofrece_registrarse():
    b = _cuerpo(29, True)
    assert struct.pack('<I', 50002) not in b and struct.pack('<I', 50003) in b


def test_las_otras_ciudades_tambien():
    for stage, base in ((3, 20000), (26, 30000), (38, 40000)):
        assert struct.pack('<I', base + 2) in _cuerpo(stage, False)
