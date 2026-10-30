"""Editor de mapas: los monstruos se marcan normal / elite / jefe, se cambian de tipo desde el
panel y los propios (server/plantillas/monstruos_propios.json) se pueden colocar. Lo prueba la
exportacion a la plantilla del servidor (ao_servidor.exportar)."""
import json
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
import ao_servidor as ao


def _editor(tmp_path, spawns):
    (tmp_path / 'mapa.json').write_text(json.dumps({'stage': 900, 'spawns': spawns}), encoding='utf-8')
    ao.init(NS(PLANTILLAS=str(tmp_path), stage_nombres=lambda: {900: 'Dark Cavern'}))


def _leer(tmp_path):
    return {e['entity_id']: e for e in json.loads((tmp_path / 'mapa.json').read_text(encoding='utf-8'))['spawns']}


def test_cambiar_el_tipo_conserva_lo_demas(tmp_path):
    _editor(tmp_path, [{'entity_id': 1, 'nombre': 'Seal', 'npc_type': 208, 'sprite': 1, 'monstruo': True,
                        'tile': [1, 1], 'elite': True, 'sello': 2, 'hp_mult': 1.4},
                       {'entity_id': 2, 'nombre': 'Lobo', 'npc_type': 5068, 'sprite': 1, 'monstruo': True,
                        'tile': [2, 2], 'hp_mult': 0.7}])
    ao.exportar('map900', [dict(entity_id=1, tile=[1, 1], tipo='elite'),
                           dict(entity_id=2, tile=[2, 2], tipo='jefe')])
    d = _leer(tmp_path)
    assert d[1]['hp_mult'] == 1.4 and d[1]['sello'] == 2            # sin cambio de tipo: intacto
    assert d[2]['jefe'] and d[2]['hp_mult'] == 10.0 and d[2]['atk_mult'] == 1.3 and 'elite' not in d[2]


def test_volver_a_normal_quita_marcas_y_multiplicadores(tmp_path):
    _editor(tmp_path, [{'entity_id': 1, 'nombre': 'X', 'npc_type': 1, 'sprite': 1, 'monstruo': True,
                        'tile': [1, 1], 'elite': True, 'hp_mult': 2.0, 'atk_mult': 1.15}])
    ao.exportar('map900', [dict(entity_id=1, tile=[1, 1], tipo='normal')])
    e = _leer(tmp_path)[1]
    assert not any(k in e for k in ('elite', 'jefe', 'hp_mult', 'atk_mult'))


def test_un_propio_nuevo_lleva_su_id_y_su_tipo(tmp_path):
    _editor(tmp_path, [])
    ao.exportar('map900', [dict(entity_id=None, nombre='Thunder Dragon', npc_type=8145, sprite=43064,
                                monstruo=True, nivel=50, tile=[5, 5], propio='dc50', tipo='elite')])
    (e,) = _leer(tmp_path).values()
    assert e['propio'] == 'dc50' and e['npc_type'] == 8145 and e['nivel'] == 50
    assert e['elite'] and e['hp_mult'] == 2.0
