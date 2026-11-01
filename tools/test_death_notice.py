"""Death Notice (4296) y el tiempo de los buffs de vencimiento (31/10/2026)."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))

import combate
import recovery_notice


def test_death_notice_es_un_notice_con_su_marca_de_24_h():
    assert recovery_notice.MAGIA[4296] == 1896 and recovery_notice.MARCA[1896] == 1927


def test_los_buffs_de_vencimiento_llevan_la_hora_de_fin():
    """"RN si funciona pero no sale el tiempo": el 1897 es 到期時間型."""
    assert abs(combate.tiempo_buff_cliente(1897, 10800000) - (time.time() + 10800)) <= 2
    assert combate.tiempo_buff_cliente(1896, 30000) == 30000


def test_matar_deja_al_objetivo_muerto(monkeypatch):
    enviados = []

    class P:
        char_id, entity_id, hp, nombre = 7, 70, 500, 'X'

    class S:
        personaje, muerto, conectado = P(), False, True

        def enviar_inmediato(self, *p):
            enviados.extend(p)

    s = S()
    import app
    monkeypatch.setattr(app, "_avisar_muerte_a_los_demas", lambda *a: None)
    recovery_notice._matar(s, 7)
    assert s.muerto and s.personaje.hp == 0 and enviados
