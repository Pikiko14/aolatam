"""El Undead Lion King (13/11/2026): stats de nivel 70, se usa desde el 60, velocidad 80, igual para fisicos y magos,
y se canjea por 1000 Mount Coin en Event Overview > Exchange > Ride and Robots (receta 19261, grupo 538)."""
import pathlib
import sqlite3
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))

import montura_abismo as mb  # noqa: E402

LEON = 83306


def test_datos_de_la_montura():
    m = next(x for x in mb.MONTURAS if x['item'] == LEON)
    assert (m['nivel'], m['nivel_uso'], m['stats']['移動速度']) == (70, 60, 80)
    assert m['stats']['平均攻擊'] == m['stats']['魔攻']
    fila = mb.fila_item(m)
    assert '物品等級="70"' in fila and '等級限制="60"' in fila and '移動速度="80"' in fila


def test_content_db():
    con = sqlite3.connect(RAIZ / 'corpus' / 'content.db')
    nivel, uso, vel = con.execute('select "物品等級", "等級限制", move_speed from item where id=?', (str(LEON),)).fetchone()
    assert (int(nivel), int(uso), int(vel)) == (70, 60, 80)


def test_se_canjea_por_1000_mount_coin():
    import app
    from house_services import xml_rows
    assert str(xml_rows('exchange.xml')[19261]['群組']) == '538'
    assert app._obtener_receta_exchange(19261) == {'id': 19261, 'materiales': [(89073, 1000)], 'premios': [(LEON, 1)]}
