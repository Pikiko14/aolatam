"""El ranking de dano al morir un jefe (contador_dano.py)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))

import contador_dano


class Jefe:
    npc_type = 209                                                     # Dragonkin Moowad (jefe de Dark Cavern)
    nombre = 'Dragonkin Moowad'
    dano_por = {1: 45230, 2: 31100, 3: 20050, 4: 22990}


def test_el_cartel_lleva_el_top_3_con_su_porcentaje():
    t = contador_dano.texto(Jefe(), {1: 'Impacty', 2: 'Baco', 3: 'Nubyx', 4: 'Carolina95'})
    assert t == ('Dragonkin Moowad defeated! 1. Impacty 45,230 (38%)  2. Baco 31,100 (26%)  '
                 '3. Carolina95 22,990 (19%)')


def test_se_manda_a_todos_los_de_la_sala_y_no_por_un_bicho_normal():
    llegan = []

    class P:
        def __init__(self, cid, nombre):
            self.char_id, self.nombre = cid, nombre

    class S:
        def __init__(self, cid, nombre):
            self.personaje = P(cid, nombre)

        def enviar_sin_espejo(self, pkt):
            llegan.append((self.personaje.nombre, pkt))

    sala = [S(1, 'Impacty'), S(2, 'Baco')]
    contador_dano.anunciar(sala, Jefe())
    assert [n for n, _ in llegan] == ['Impacty', 'Baco'] and b'Impacty 45,230' in llegan[0][1]

    class Bicho(Jefe):
        npc_type = 7                                                   # Lily
    llegan.clear()
    contador_dano.anunciar(sala, Bicho())
    assert llegan == []
