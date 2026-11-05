"""La mascota lleva la faccion de su dueno en el 0x0050 (05/11/2026).

"porque al pet en pvp le sale esa faction verde??": el byte 38 del 0x0050 (a2+0x28 -> +0x2e8 en Angel.exe, el mismo
campo que el byte 60 del spawn del jugador) iba a 0 y el cliente la pintaba como aliada.
"""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import login  # noqa: E402
import mascotas  # noqa: E402
import presencia  # noqa: E402


def test_la_mascota_lleva_la_faccion_del_dueno():
    presencia._POR_MAPA.clear()
    p = login.Personaje()
    p.faction = 'Shadow'
    ses = NS(personaje=p, _entidad_publica=2042)
    presencia._POR_MAPA[47] = [ses]
    plantilla = bytes(mascotas.TAM_MUNDO)
    a_otros = mascotas.entidad_mundo(plantilla, {'entidad': 777, 'dueno': 2042})[2:]
    al_dueno = mascotas.entidad_mundo(plantilla, {'entidad': 777, 'dueno': p.entity_id})[2:]
    assert a_otros[38] == login.CODIGO_FACCION['Shadow'] == al_dueno[38]
    assert mascotas.entidad_mundo(plantilla, {'entidad': 777, 'dueno': 99999})[2 + 38] == 0     # dueno desconocido
