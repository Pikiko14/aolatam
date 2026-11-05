"""Santa Clausula, jefe del evento de Navidad (server/santa_clausula.py), 05/11/2026."""
import datetime
import pathlib
import sys
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import app  # noqa: E402
import combate as cb  # noqa: E402
import santa_clausula as sc  # noqa: E402


class Dados:
    def __init__(self, *v):
        self.v = list(v)

    def random(self):
        return self.v.pop(0) if self.v else 0.99

    def choice(self, seq):
        return seq[0]


def _santa():
    sc.asegurar_en_db()
    cb._MON = None
    return cb.Monstruo(1, sc.NPC_TYPE, sc.NOMBRE, [50, 50], sc.SPRITE, stage=37)


def test_stats_y_jefe():
    m = _santa()
    assert (m.hp_max, m.atk, m.matk) == (500000, 450, 600)
    assert cb.es_jefe(sc.NPC_TYPE)


def test_inmune_al_control_pero_no_al_sangrado():
    m = _santa()
    assert m.aplicar_efecto({'dur_ms': 3000, 'estado': 'aturdido'}) is None
    assert m.aplicar_efecto({'dur_ms': 3000, 'estado': 'congelado'}) is None
    assert m.aplicar_efecto({'dur_ms': 3000, 'vel_mov': -30}) is None
    assert m.aplicar_efecto({'dur_ms': 3000, 'hp_tick': -50}) == 'sangrado'


def test_habilidades():
    assert sc.elegir_habilidad(Dados(0.9)) is None
    assert sc.elegir_habilidad(Dados(0.1, 0.1)) == sc.HAB_AREA
    assert sc.elegir_habilidad(Dados(0.1, 0.9)) == sc.HAB_UNO
    m = _santa()
    assert 0 < sc.dano_habilidad(sc.HAB_AREA, m, 100) <= 600
    assert sc.dano_habilidad(sc.HAB_UNO, m, 0) > 0


def test_botin():
    assert sc.botin_para(True, Dados()) == [sc.CAJA]
    todo_h = sc.botin_para(True, Dados(*[0.0] * 7))
    assert todo_h == [sc.CAJA, *sc.TRAJE_H, sc.GACHAS_40[0], 3868, 3869, sc.CAJAS_60[0]]
    todo_m = sc.botin_para(False, Dados(*[0.0] * 6))
    assert todo_m == [sc.CAJA, *sc.TRAJE_M, sc.GACHAS_40[0], 3868, 3869, sc.CAJAS_60[0]]
    # una caja Lv60 (de las 7) con un 20%: con 0.19 sale, con 0.21 no
    assert sc.botin_para(False, Dados(0.5, 0.5, 0.5, 0.5, 0.5, 0.19)) == [sc.CAJA, sc.CAJAS_60[0]]
    assert sc.botin_para(False, Dados(0.5, 0.5, 0.5, 0.5, 0.5, 0.21)) == [sc.CAJA]


def test_botin_una_caja_60_de_cada_cinco():
    import random
    rng = random.Random(3)
    n = sum(1 for _ in range(5000) for it in sc.botin_para(True, rng) if it in sc.CAJAS_60)
    assert 900 < n < 1100


def test_proxima_hora():
    base = datetime.datetime(2026, 12, 1, 19, 59).timestamp()
    assert datetime.datetime.fromtimestamp(sc.proxima_hora(base)).hour == sc.HORA_EVENTO
    despues = datetime.datetime(2026, 12, 1, 21, 0).timestamp()
    assert datetime.datetime.fromtimestamp(sc.proxima_hora(despues)).day == 2


def test_aparece_se_va_y_reparte(monkeypatch):
    carteles, dados = [], []
    monkeypatch.setattr(sc, '_cartel', lambda t: carteles.append(t))
    sc._ACTIVO.clear()
    texto = sc.aparecer(37)
    assert 'Wishing Tear' in texto and sc._ACTIVO['stage'] == 37
    m = sc._ACTIVO['m']
    assert app._SALAS_DEL_MUNDO[37].monstruos[m.entity_id] is m
    assert 'appeared' in carteles[-1]
    # dos jugadores le pegaron: cada uno se lleva su botin
    a = SimpleNamespace(personaje=SimpleNamespace(char_id=11, apariencia=[1, 0, 0, 8, 8]))
    b = SimpleNamespace(personaje=SimpleNamespace(char_id=22, apariencia=[0, 0, 0, 8, 8]))
    monkeypatch.setattr(app, '_tw_sesiones', lambda: [a, b])
    monkeypatch.setattr(app, '_gm_dar_item', lambda s, it, n=1: dados.append((s.personaje.char_id, it)) or 'dado')
    m.dano_por = {11: 5000, 22: 300}
    assert sc.al_morir(a, m)
    assert (11, sc.CAJA) in dados and (22, sc.CAJA) in dados
    assert not sc._ACTIVO and 'defeated' in carteles[-1]
    # y si nadie lo mata, se va
    sc.aparecer(6)
    m2 = sc._ACTIVO['m']
    assert sc.retirar('prueba') == 'retirado'
    assert m2.entity_id not in app._SALAS_DEL_MUNDO[6].monstruos and not m2.vivo


def test_comando_gm():
    assert app._gm_parsear('santa estado')[0] == 'santa'
    assert 'santa' in app.PALABRAS_GM


def test_sprite_no_choca_con_otro_obd():
    """El 119001 era una pieza de equipo de char3.obd y el cliente crasheaba al ver a Santa: su Sequence no puede
    estar en ningun otro .obd del cliente, ni suelto ni dentro de un rango 'Sequence = base, desde, hasta'."""
    import re
    ocupado = []
    for f in (RAIZ / 'extracted_paks').glob('*/setting/*.obd'):
        for bloque in f.read_bytes().split(b'[OBJECT]'):
            if ('\\mon\\%s\\' % sc.CARPETA).encode() in bloque:
                continue                                              # el propio de Santa
            m = re.search(rb'^Sequence = ([\d, ]+)', bloque, re.M)
            if not m:
                continue
            nums = [int(x) for x in m.group(1).split(b',') if x.strip()]
            if sc.SPRITE in nums or (len(nums) == 3 and nums[1] <= sc.SPRITE <= nums[2]):
                ocupado.append(f.name)
    assert ocupado == []
    assert sc.SPRITE != sc.SPRITE_VIEJO
