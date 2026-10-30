"""Un Bow nuevo recibia los hechizos de ShadowBlade (Stab I, Nimble I, Poisoned Dagger I).
El cliente llama 30 = ShadowBlade y 32 = Mantle, y el Bow elige Mantle; el servidor tenia
los hechizos y la daga de ShadowBlade en la 32. Reportado por el usuario: "en personaje
nuevo cuando salgo del tutorial me coloca poderes de shadowblade".

Las ramas son las que manda el cliente de verdad (log del VPS, "CLASE ELEGIDA")."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import clases
import skills

BOW = [17, 15, 16, 18, 19, 32]            # Longbow, Reserve, Finesse, Snipe, Eagle Eye, Mantle
SHADOWBLADE = [30, 13, 15, 35, 36, 32]    # ShadowBlade, Grapple, Reserve, Avatar, Assault, Mantle
STAB, NIMBLE, POISONED = 5401, 5406, 5411


def test_los_nombres_del_cliente():
    assert clases.nombre(30) == 'ShadowBlade' and clases.nombre(32) == 'Mantle'


def test_bow_solo_recibe_lo_suyo():
    ids = {mid for mid, _ in clases.hechizos_iniciales(BOW)}
    assert ids == {901, 902, 903}


def test_shadowblade_sigue_recibiendo_lo_suyo():
    ids = {mid for mid, _ in clases.hechizos_iniciales(SHADOWBLADE)}
    assert {STAB, NIMBLE, POISONED} <= ids
    assert dict(clases.regalo(SHADOWBLADE))[3] == 19856   # FreshmanSharp Knife


def test_la_daga_y_sus_tecnicas_son_de_la_30():
    assert clases.skill_de_item(19856) == 30
    assert skills.skill_de_magia(STAB) == 30
