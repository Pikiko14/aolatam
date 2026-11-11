"""Los monstruos de la raid no sueltan nada que pida mas nivel que la raid (11/11/2026: "me dropiaron 1 80")."""
import os
import sqlite3
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'server'))

import combate  # noqa: E402


def test_los_clones_de_la_raid_tienen_su_nivel():
    assert combate.nivel_botin_raid(23910) == 60
    assert combate.nivel_botin_raid(23942) == 60
    assert combate.nivel_botin_raid(1) is None


def test_nada_por_encima_del_nivel_de_la_raid():
    cand = combate._candidatos_raid(60)
    assert cand
    con = sqlite3.connect(os.path.join(RAIZ, 'corpus', 'content.db'))
    ids = ','.join(str(i) for i, _c in cand)
    tope = con.execute('select max(cast(coalesce(等級限制, 物品等級) as int)) from item where id in (%s)' % ids).fetchone()[0]
    assert tope <= 60
    for npc in (23910, 23930, 23940, 23942):
        for _ in range(30):
            for it, _c in combate.botin_items(npc):
                assert it in {i for i, _c in cand}
