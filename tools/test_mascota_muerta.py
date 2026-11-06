"""La mascota que llega a 0 queda MUERTA hasta revivirla en el Pet Expert (05/11/2026: "llega a 0 tiene la animacion
de muerte pero sigue vivo, debe estar death para revivirlo en el pet expert").

El cliente lista en la ventana "Pet revival" las mascotas con vida < 1 (Angel.exe 0x664e30) y pide revivirlas con el
c2s 0x004A [u8 n][u16 ranura]*n (0x621820).
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402
import mascotas as ms  # noqa: E402
import presencia  # noqa: E402

ITEM_HUEVO = 3049


def _ses(monkeypatch):
    monkeypatch.setattr(app, '_refrescar', lambda *x, **k: [])
    presencia._POR_MAPA.clear()
    p = login.Personaje(hp=5000, hp_max=5000, mp=50, mp_max=50)
    p.nombre, p.stage, p.tile_x, p.tile_y, p.buffs = 'Baco', 47, 100, 100, {}
    f = {'fuera': True, 'nombre': 'Egg', 'hp': 0, 'hp_max': 100, 'mp': 10, 'mp_max': 105, 'saciedad': 100,
         'intimidad': 50, 'nivel': 1, 'sprite': 0, 'ranura': 30, 'entidad': 1069500}
    p.mascota, p.mascotas = f, {'30': f}
    recibido = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={30: ITEM_HUEVO}, cantidades={30: 1},
           usuario=None, recibido=recibido, pet_entity_id=1069500, pet_objetivo=None,
           enviar=lambda *pk, r=recibido: r.extend(pk), enviar_inmediato=lambda *pk, r=recibido: r.extend(pk))
    presencia._POR_MAPA[47] = [s]
    return s, f


def _hp_0065(f):
    return struct.unpack_from('<I', ms.armar(f), 2 + 59)[0]


def test_al_morir_queda_muerta_con_vida_0(monkeypatch):
    s, f = _ses(monkeypatch)
    app._mascota_muere(s, f, 1069500, lambda v: 0)
    assert f['muerta'] and f['hp'] == 0 and not f['fuera']
    assert _hp_0065(f) == 0
    entrada = ms.entrada(bytes(ms.TAM_ENTRADA), f)
    assert struct.unpack_from('<I', entrada, ms.OFF_ENTRADA['hp'])[0] == 0


def test_muerta_no_se_puede_sacar(monkeypatch):
    s, f = _ses(monkeypatch)
    f.update(fuera=False, muerta=True, entidad=0)
    monkeypatch.setattr(app, '_pet_ficha', lambda ses, r: f)
    app._pet_alternar(s, 't', 30)
    assert not f['fuera']
    assert any(b'Pet Expert' in x for x in s.recibido)


def test_el_pet_expert_la_revive(monkeypatch):
    s, f = _ses(monkeypatch)
    f.update(fuera=False, muerta=True, entidad=0)
    app._revivir_mascotas(s, 't', struct.pack('<BHH', 2, 30, 30))
    assert not f['muerta'] and f['hp'] == 100 and f['mp'] == 105
    assert _hp_0065(f) == 100
    assert any(b'has revived' in x for x in s.recibido)


def test_revivir_una_viva_no_hace_nada(monkeypatch):
    s, f = _ses(monkeypatch)
    f.update(fuera=False, hp=50, entidad=0)
    app._revivir_mascotas(s, 't', struct.pack('<BH', 1, 30))
    assert f['hp'] == 50
    assert any(b'no dead pet' in x for x in s.recibido)
