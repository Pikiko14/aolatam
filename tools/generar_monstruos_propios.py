"""Genera server/plantillas/monstruos_propios.json: los 15 monstruos propios de Dark Cavern (Lv45-60).

Cada uno usa un npc_type real de nivel 150+ del cliente -- sus habilidades (攻擊法術1..4), su IA y un
dibujo que el cliente tiene -- pero con stats, exp y oro de su nivel. Los stats se interpolan por nivel
entre monstruos normales reales de ese rango, asi quedan a la par de lo que ya hay de 45 a 60.

Al matarlos (combate.botin_propio y app._premiar): 50 de Angel Gold para quien se lleva el botin, la
caja de nivel 55 (cliente_local.ITEM_CAJA_55) y, mas raro, una piedra de Holy Battlefield.

    python tools/generar_monstruos_propios.py
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cliente_local
import combate

SALIDA = RAIZ / 'server' / 'plantillas' / 'monstruos_propios.json'

# Monstruos normales de referencia (npc_type, nivel): sus stats marcan la curva.
REFERENCIAS = ((187, 45), (192, 48), (193, 50), (204, 53), (205, 55), (843, 60))

# (nivel, npc_type base de nivel alto, sprite que el cliente dibuja)
MOBS = (
    (45, 8138, 43106),   # Iron Can Snail
    (46, 8137, 43043),   # Crystal Dragon Turtle
    (47, 8140, 43088),   # Clawed Swift Dragon
    (48, 8139, 43061),   # Adventure Chair Ralon
    (49, 8142, 43097),   # Blade Thorny Dragon
    (50, 8145, 43064),   # Thunder Dragon
    (51, 8144, 43079),   # Silverhelm Dragon
    (52, 8153, 43073),   # Steel Armor Tiger
    (53, 8156, 43100),   # Bloody Thorn Dragon
    (54, 8757, 43192),   # Royal Army Bees
    (55, 8640, 43193),   # Toxic Hornet Soldiers
    (56, 8754, 43189),   # Messengers of Styx
    (57, 8759, 43198),   # Desert Blob
    (58, 8755, 43190),   # Ghostly Warrior
    (60, 8756, 43191),   # Pharaoh's Holy Guard
)

CAMPOS = ('hp', 'atk', 'var', 'def', 'mdef', 'matk', 'exp')

BOTIN = {
    'ag': 50,
    'caja': cliente_local.ITEM_CAJA_55,
    'prob_caja': 0.04,
    # (item, probabilidad): se tira en orden y sale como mucho una. Mismo orden que las del jefe.
    'piedras_holy': [[8537, 0.010], [8770, 0.005], [24882, 0.003], [28866, 0.0014], [40921, 0.0006]],
}


def curva(nivel):
    puntos = [(lv, combate._datos(npc)) for npc, lv in REFERENCIAS]
    for (l0, d0), (l1, d1) in zip(puntos, puntos[1:]):
        if l0 <= nivel <= l1:
            t = (nivel - l0) / (l1 - l0)
            return {c: int(round(d0[c] + (d1[c] - d0[c]) * t)) for c in CAMPOS}
    raise ValueError('nivel fuera de las referencias: %d' % nivel)


def main():
    mobs = {}
    for nivel, base, sprite in MOBS:
        d = combate._datos(base)
        mobs['dc%d' % nivel] = dict(nombre=d['nombre'], base=base, sprite=sprite, nivel=nivel, **curva(nivel))
    datos = {'_nota': 'Generado por tools/generar_monstruos_propios.py; no editar a mano.',
             'mobs': mobs, 'botin': BOTIN}
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for k, m in mobs.items():
        print('%s  Lv%d  %-24s base %d  hp %d atk %d def %d exp %d' % (k, m['nivel'], m['nombre'], m['base'],
                                                                       m['hp'], m['atk'], m['def'], m['exp']))
    print('escrito', SALIDA)


if __name__ == '__main__':
    main()
