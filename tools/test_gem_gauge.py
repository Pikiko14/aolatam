"""El Gem Gauge (29359) saca y pierde la gema del ultimo hueco; el hueco queda libre (06/11/2026: "el gem gauge no
funciona"). Antes su categoria (挖寶石道具) no era de mejora y el uso quedaba "sin accion"."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import mejoras  # noqa: E402

GEM_GAUGE = 29359


def test_es_de_mejora():
    assert mejoras.clase_de(GEM_GAUGE) == 'quitar_gema'


def test_quita_la_ultima_y_deja_el_hueco():
    estado = {3: {'veces': 0, 'gemas': [101, 202], 'extra': {}, 'huecos': 2}}
    ok, _ = mejoras.quitar_gema(estado, 3)
    assert ok and estado[3]['gemas'] == [101] and estado[3]['huecos'] == 2
    mejoras.quitar_gema(estado, 3)
    ok, motivo = mejoras.quitar_gema(estado, 3)
    assert not ok and 'no hay' in motivo


def _ses(gemas):
    enviados = []
    p = NS(char_id=1, mejoras={3: {'veces': 0, 'gemas': list(gemas), 'extra': {}, 'huecos': 2}}, buffs={})
    return NS(personaje=p, inventario={41: GEM_GAUGE, 3: 163}, cantidades={41: 5}, usuario=None,
              enviar=lambda *pk: enviados.extend(pk), enviados=enviados)


def test_usarlo_sobre_la_pieza(monkeypatch):
    monkeypatch.setattr(app, '_refrescar', lambda *a, **k: [])
    monkeypatch.setattr(app, '_stats_ses', lambda ses: b'')
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    s = _ses([101, 202])
    assert app._usar_mejora(s, 't', 41, 3)
    assert s.personaje.mejoras[3]['gemas'] == [101] and s.cantidades[41] == 4
    assert any(b'The gem was removed' in x for x in s.enviados)


def test_sin_gema_no_se_gasta(monkeypatch):
    s = _ses([])
    assert app._usar_mejora(s, 't', 41, 3)
    assert s.cantidades[41] == 5 and any(b'has no gem to remove' in x for x in s.enviados)


def test_gema_sin_hueco_no_se_gasta(monkeypatch):
    # 13/11/2026, "me esta dejando poner gemas a los items sin tener un hueco abierto con piercing hammer": la gema se
    # gastaba con "Failed to intensify". Sin hueco libre no se gasta y se dice que hay que abrirlo antes.
    monkeypatch.setattr(app, '_refrescar', lambda *a, **k: [])
    monkeypatch.setattr(app, '_stats_ses', lambda ses: b'')
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    enviados = []
    p = NS(char_id=1, mejoras={}, buffs={})
    s = NS(personaje=p, inventario={41: 3113, 3: 163}, cantidades={41: 5}, usuario=None,
           enviar=lambda *pk: enviados.extend(pk))
    assert app._usar_mejora(s, 't', 41, 3)
    assert s.cantidades[41] == 5 and s.inventario[41] == 3113
    assert any(b'Piercing Hammer' in x for x in enviados)
    assert not (p.mejoras.get(3) or {}).get('gemas')
