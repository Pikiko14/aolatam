"""Teclas de la barra y chat con Enter (07/11/2026): tools/parche_teclas_aof.py, tools/parche_aof_ventana.py y
server/lua/teclas.lua."""
import pathlib
import struct
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'server'))
import parche_aof_ventana  # noqa: E402
import parche_teclas_aof as pt  # noqa: E402
from parche_canal_lua import _off  # noqa: E402

ANGEL = RAIZ / 'parches' / 'juego' / 'angel.dat'


def _sin_parche():
    d = ANGEL.read_bytes()
    if pt.lleva_el_parche(d):
        pytest.skip('parches/juego/angel.dat ya lleva el parche de teclas')
    return d


@pytest.mark.skipif(not ANGEL.exists(), reason='sin parches/juego/angel.dat')
def test_el_parche_pone_los_nativos_y_los_saltos():
    d = _sin_parche()
    nuevo, info = pt.parchear(d)
    assert pt.lleva_el_parche(nuevo)
    # La tabla game nueva: la de antes y los cinco nativos, con su terminador.
    o = _off(nuevo, info['tabla'])
    pares = []
    while True:
        n, f = struct.unpack_from('<II', nuevo, o + 8 * len(pares))
        if n == 0 and f == 0:
            break
        pares.append((n, f))
    assert pares[:-5] == pt._tabla_game(d)
    nombres = [nuevo[_off(nuevo, n):nuevo.index(b'\0', _off(nuevo, n))].decode() for n, _ in pares[-5:]]
    assert nombres == list(pt.NATIVOS)
    assert [f for _, f in pares[-5:]] == [info['f_' + n] for n in pt.NATIVOS]
    # El push de luaI_openlib apunta a la tabla nueva y los tres saltos a sus cuevas.
    assert nuevo[_off(nuevo, pt.P1):_off(nuevo, pt.P1) + 5] == b'\x68' + struct.pack('<I', info['tabla'])
    for va, cueva in ((pt.P2, info['cueva_teclado']), (pt.P4, info['cueva_barra'])):
        o = _off(nuevo, va)
        assert nuevo[o] == 0xE9 and va + 5 + struct.unpack_from('<i', nuevo, o + 1)[0] == cueva
    assert nuevo[_off(nuevo, pt.P3):_off(nuevo, pt.P3) + 2] == b'\x90\x90'
    # Arranca con el modo apagado: sin el Lua, el juego de siempre.
    assert nuevo[_off(nuevo, info['modo'])] == 0
    with pytest.raises(SystemExit):
        pt.parchear(nuevo)                       # dos veces no


def test_la_pestana_aof_entra_en_la_ventana_system():
    import xml.etree.ElementTree as ET
    if not parche_aof_ventana.PAK_ORIGEN.exists():
        pytest.skip('sin el cliente de desarrollo')
    crudo = parche_aof_ventana.original()
    texto = crudo[3:].decode('utf-8') if crudo.startswith(b'\xef\xbb\xbf') else crudo.decode('utf-8')
    if 'id="59100"' in texto:
        pytest.skip('el origen ya lleva la pestana')
    raiz = ET.fromstring(parche_aof_ventana.generar(texto).encode('utf-8'))
    ventanas = {w.get('id'): w for w in raiz.iter('window')}
    hijos = [c.text for c in ventanas['12002'].findall('child')]
    assert hijos[-1:] == ['59101'] and hijos.index('59100') == hijos.index('12005') + 1
    assert 'bsRadioEnd' not in ventanas['12005'].find('style').attrib
    assert 'bsRadioEnd' in ventanas['59100'].find('style').attrib
    assert ventanas['59100'].get('appdata') == '59101'
    assert [c.text for c in ventanas['59110'].findall('child')].count('59131') == 1
    for wid in ('59103', '59105', '59132', '59133', '59120'):
        assert ventanas[wid].find('OnCommand') is not None


def test_el_servidor_manda_teclas_lua_al_saludar():
    from types import SimpleNamespace as NS
    import subasta_ventana
    recibido = []
    ses = NS(personaje=NS(nombre='Aegon'), enviar=lambda *pk: recibido.extend(pk))
    subasta_ventana.procesar(ses, struct.pack('<BII', subasta_ventana.CMD_SALUDO, 1, 0))
    textos = [p[2:-1].decode('latin1') for p in recibido if p[:2] == struct.pack('<H', 0x01A0)]
    assert any('AofAplicar' in t and 'game.aofsetkey' in t for t in textos)
