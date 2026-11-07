"""Revival I..V levanta al muerto y el efecto le cae a el; el alma revive junto al totem de su faccion (07/11/2026).

"la persona me esta intentando revivir con el spell revivir y el efecto le sale a el no a mi" y "no me deja
seleccionar el totem para revivir".
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate  # noqa: E402
import login  # noqa: E402
import presencia  # noqa: E402


def _ses(nombre, recibido, x=100):
    p = login.Personaje(hp=1000, hp_max=1000, mp=5000, mp_max=5000)
    p.nombre, p.stage, p.tile_x, p.tile_y = nombre, 41, x, 100
    return NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, cantidades={},
              usuario=None, muerto=False, fantasma=False, monstruos={},
              enviar=lambda *pk: recibido.extend(pk), enviar_inmediato=lambda *pk: recibido.extend(pk))


def _efectos(paquetes):
    return [x for x in paquetes if x[:2] == struct.pack('<H', 0x0011)]


def test_revival_cae_sobre_el_muerto_y_lo_levanta(monkeypatch):
    presencia._POR_MAPA.clear()
    a_ve, b_ve = [], []
    cura, muerto = _ses('Baco', a_ve), _ses('Zetha', b_ve, x=103)
    muerto.muerto = muerto.fantasma = True
    muerto.personaje.hp = 0
    presencia._POR_MAPA[41] = [cura, muerto]
    monkeypatch.setattr(app.asyncio if hasattr(app, 'asyncio') else __import__('asyncio'), 'get_event_loop',
                        lambda: (_ for _ in ()).throw(RuntimeError()))
    mag = combate.datos_magia(78)
    app._revivir_con_hechizo(cura, 't', 78, mag, presencia.entidad_de(muerto))
    # El efecto, en la pantalla del que lo lanza, cae sobre el muerto (+6), no sobre si mismo.
    ef_a = _efectos(a_ve)
    assert ef_a and all(struct.unpack_from('<I', x, 8)[0] == presencia.entidad_de(muerto) for x in ef_a)
    assert not muerto.muerto and not muerto.fantasma
    assert muerto.personaje.hp == 500                       # Revival V: 50 %
    assert cura.personaje.mp == 5000 - mag['mp']


def test_revival_sobre_un_vivo_no_hace_nada():
    presencia._POR_MAPA.clear()
    a_ve, b_ve = [], []
    cura, vivo = _ses('Baco', a_ve), _ses('Zetha', b_ve, x=103)
    presencia._POR_MAPA[41] = [cura, vivo]
    app._revivir_con_hechizo(cura, 't', 78, combate.datos_magia(78), presencia.entidad_de(vivo))
    assert not _efectos(a_ve) and cura.personaje.mp == 5000


def test_alma_junto_al_totem_de_su_faccion_revive(monkeypatch):
    import totem_war
    presencia._POR_MAPA.clear()
    ve = []
    alma = _ses('Zetha', ve)
    alma.muerto = alma.fantasma = True
    alma.personaje.hp = 0
    presencia._POR_MAPA[41] = [alma]
    monkeypatch.setattr(totem_war, 'codigo_faccion', lambda p: 2)
    duena = {'f': 1}
    monkeypatch.setattr(totem_war, 'faccion_duena', lambda st: duena['f'])
    alma.monstruos = {9: NS(es_totem_tw=True, vivo=True, tile_x=102, tile_y=101)}
    app._alma_junto_al_totem(alma, 't')
    assert alma.muerto                                      # totem de otra faccion: nada
    duena['f'] = 2
    alma.monstruos[9].tile_x = 110
    app._alma_junto_al_totem(alma, 't')
    assert alma.muerto                                      # lejos: nada
    alma.monstruos[9].tile_x = 102
    app._alma_junto_al_totem(alma, 't')
    assert not alma.muerto and alma.personaje.hp == 1000
