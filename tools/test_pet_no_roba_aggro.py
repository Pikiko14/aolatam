"""La mascota no le quita al jugador el objetivo que ya tiene.

EL FALLO REPORTADO: "si ataco al mob por detras (a distancia, con la mascota
de escudo delante) este no me ataca a mi". Causa real: el bucle de IA de la
mascota hacia `pet_targ.en_combate_con = pet_eid` SIN CONDICION cada vez que
la mascota pegaba (cada ~1.15-1.55s). El jugador si marca al monstruo en su
contra al golpearlo (`m.en_combate_con = yo`), pero si estaba fuera del
alcance del monstruo este tenia que CAMINAR para alcanzarlo; antes de
llegar, el siguiente golpe de la mascota volvia a poner `en_combate_con` en
la mascota, y el monstruo se giraba a pegarle a ella en vez de perseguir al
jugador. Con la mascota en modo Active (el modo por defecto) esto pasaba
todo el rato.

El arreglo copia el patron que ya usaba el codigo de invocaciones (unas
lineas mas arriba en el mismo archivo): `if targ.en_combate_con is None:
targ.en_combate_con = yo` -- reclama el objetivo solo si esta libre, nunca
se lo quita a quien ya lo tenga.

No hay forma sana de montar una sesion falsa para este bucle (son miles de
lineas con docenas de variables locales), asi que, como ya hacen otras
pruebas de app.py en este repo (ver test_bolsas.py:
test_se_manda_el_icono_del_buff), se verifica el texto fuente alrededor del
punto exacto del fallo.
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))


def test_la_mascota_solo_reclama_un_objetivo_libre():
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    i = fuente.index("f_pet['ultimo_ataque'] = ahora")
    trozo = fuente[i:i + 1200]
    assert "pet_targ.en_combate_con = pet_eid" in trozo, 'la mascota dejo de poder tomar un objetivo'
    assert "if getattr(pet_targ, 'en_combate_con', None) is None:" in trozo,         'la mascota vuelve a robarle el objetivo al jugador en cada golpe'
    # la asignacion debe quedar DENTRO del if (indentada un nivel mas), no suelta antes de el
    linea_if = trozo.index("if getattr(pet_targ, 'en_combate_con', None) is None:")
    linea_asig = trozo.index('pet_targ.en_combate_con = pet_eid')
    assert linea_asig > linea_if, 'la condicion quedo despues de la asignacion: no protege nada'


def test_las_invocaciones_siguen_con_el_mismo_patron():
    """El patron de referencia (no se toco, solo se compara contra el)."""
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert "if getattr(targ, 'en_combate_con', None) is None:\n                                                targ.en_combate_con = yo" in fuente
