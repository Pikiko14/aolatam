"""Reglas "matar X monstruos" del editor (server/eventos_propios.py)."""
import json
import pathlib
import random
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import eventos_propios as evp


def _reglas(tmp_path, monkeypatch, *reglas):
    f = tmp_path / 'eventos_propios.json'
    f.write_text(json.dumps({'reglas': list(reglas)}), encoding='utf-8')
    monkeypatch.setattr(evp, 'ARCHIVO', f)
    monkeypatch.setattr(evp, '_cache', {'mtime': None, 'reglas': []})
    monkeypatch.setattr(evp, '_cuentas', {})
    monkeypatch.setattr(evp, '_hechas', set())
    monkeypatch.setattr(evp, '_portales', {})


def _ses(cid, stage=900):
    return NS(personaje=NS(char_id=cid, stage=stage, nombre='pj%d' % cid, tile_x=10, tile_y=10))


def _mob(npc=8138, propio=None):
    return NS(npc_type=npc, propio=propio, tile_x=5, tile_y=6)


REGLA = dict(id='r', stage=900, matar=dict(mobs=[8138, 'dc50'], cantidad=3, alcance='jugador', repetir=True),
             premios=[dict(tipo='dar', item=89055, cantidad=1)])


def test_cuenta_por_jugador_y_se_repite(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch, REGLA)
    a, b = _ses(1), _ses(2)
    assert not evp.al_morir(a, _mob()) and not evp.al_morir(a, _mob(1, 'dc50'))
    assert not evp.al_morir(b, _mob())                       # b lleva su propia cuenta
    assert evp.al_morir(a, _mob())[0][0]['id'] == 'r'
    assert evp.progreso(a, 'r') == (0, 3) and evp.progreso(b, 'r') == (1, 3)


def test_otros_mobs_u_otro_mapa_no_cuentan(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch, dict(REGLA, matar=dict(REGLA['matar'], cantidad=1)))
    assert not evp.al_morir(_ses(1), _mob(9999))
    assert not evp.al_morir(_ses(1, stage=41), _mob())
    assert evp.al_morir(_ses(1), _mob())


def test_alcance_mapa_y_una_sola_vez(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch, dict(REGLA, matar=dict(mobs=[], cantidad=2, alcance='mapa', repetir=False)))
    assert not evp.al_morir(_ses(1), _mob(1))
    assert evp.al_morir(_ses(2), _mob(2))                    # la segunda baja del mapa, de otro jugador
    assert not evp.al_morir(_ses(1), _mob(1)) and not evp.al_morir(_ses(1), _mob(1))


def test_reglas_invalidas_se_ignoran(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch, dict(REGLA, premios=[]), dict(REGLA, id='', ))
    assert evp.reglas() == []
    assert evp.validar(dict(REGLA, premios=[dict(tipo='portal', destino=41)])) == [
        '"portal" sin mapa o casilla de llegada']


def test_premios_a_efectos():
    efectos, ag, portales = evp.efectos_de([
        dict(tipo='dar', item=5, cantidad=2), dict(tipo='soltar', items=[[7, 1]], prob=100),
        dict(tipo='soltar', items=[[8, 1]], prob=0), dict(tipo='oro', cantidad=500),
        dict(tipo='ag', cantidad=50), dict(tipo='portal', destino=41, llegada=[1, 2])], rnd=random.Random(1))
    assert efectos == [('dar', [(5, 2)]), ('dar', [(7, 1)]), ('oro', 500)]
    assert ag == 50 and portales[0]['destino'] == 41


def test_portal_temporal_se_ve_al_entrar_y_caduca(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch)
    ahora = [1000.0]
    monkeypatch.setattr(evp.time, 'time', lambda: ahora[0])
    eid = evp.abrir_portal(900, (5, 6), 41, (160, 36), 60)
    assert evp.portal(eid)['destino'] == 41
    assert len(evp.poblar(900)) == 1 and evp.poblar(41) == []
    ahora[0] += 61
    assert evp.portal(eid) is None and evp.poblar(900) == []
