"""Los mobs no sueltan en cuanto te alejas: solo tras GRACIA_AGRO segundos fuera de alcance (11/11/2026)."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'server'))
FUENTE = open(os.path.join(RAIZ, 'server', 'app.py'), encoding='utf-8').read()


def test_radios_mas_largos():
    import combate
    assert combate.RANGO_PERDER_AGRO >= 30
    assert 'CORREA_INSTANCIA = 25' in FUENTE


def test_sueltan_solo_tras_la_gracia():
    assert 'GRACIA_AGRO = 5.0' in FUENTE
    assert 'ahora - m.fuera_de_alcance_desde >= GRACIA_AGRO' in FUENTE
    assert 'm.fuera_de_alcance_desde = None' in FUENTE
