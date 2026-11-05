"""Las tarjetas de expresion desbloquean la POSICION del emote en la ventana, no su numero (05/11/2026).

"revisa los emojis, algunos no estan funcionando": Yawn (numero 13) marcaba la posicion 13, que la ventana pinta como
el emote 9 (Knarl); y Yawn no salia. La tabla posicion -> numero es la de angel.dat (getemotbyindex).
"""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import inventario as inv  # noqa: E402
import presencia  # noqa: E402


def test_numero_a_posicion():
    assert inv.posicion_de_emote(inv.emote_de_tarjeta(3275)) == 8        # Laugh (11): basico, posicion 8
    assert inv.posicion_de_emote(inv.emote_de_tarjeta(3277)) == 15       # Yawn (13)
    assert inv.posicion_de_emote(inv.emote_de_tarjeta(3262)) == 0        # Wait (0)
    assert inv.posicion_de_emote(inv.emote_de_tarjeta(3270)) == 12       # Make faces (8): la primera comprada
    assert inv.posicion_de_emote(41) is None                              # no esta en la ventana


def test_la_ventana_marca_la_posicion_y_se_puede_usar():
    pos = inv.posicion_de_emote(13)                                        # Yawn
    flags = presencia.paquete_emotes_desbloqueados({pos})[2:]
    assert flags[pos - 12] == 1 and sum(flags) == 1
    assert inv.puede_usar_emocion(NS(emotes={pos}), pos)
    assert not inv.puede_usar_emocion(NS(emotes=set()), pos)
