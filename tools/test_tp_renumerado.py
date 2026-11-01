"""El selector del Ctrl+T (Angels GO!) sin huecos: el cliente usa el 編號 como posicion en la lista."""
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))

import parche_tp_expansiones as tp


def test_categorias_y_destinos_van_seguidos_y_cada_destino_sabe_su_original():
    jm, jc, _n, _fuera, original = tp.generar()
    cats = [int(x) for x in re.findall('<跳地圖類別 編號="([0-9]+)"', jc)]
    dest = [int(x) for x in re.findall('<跳地圖 編號="([0-9]+)"', jm)]
    assert cats == list(range(1, len(cats) + 1)) and dest == list(range(1, len(dest) + 1))
    assert {int(x) for x in re.findall('類別[0-9]="([0-9]+)"', jm)} <= set(cats)
    assert sorted(original) == dest and len(set(original.values())) == len(dest)


def test_el_servidor_traduce_el_numero_nuevo_al_original():
    import app
    mapa = json.loads((RAIZ / 'server' / 'plantillas' / 'angels_go_renumerado.json').read_text(encoding='utf-8'))
    nuevo, viejo = max(mapa.items(), key=lambda kv: int(kv[0]))
    assert app._angels_go_original(int(nuevo)) == viejo and str(viejo) in app._angels_go()
