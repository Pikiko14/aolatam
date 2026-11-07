"""Las tarjetas de expresion desbloquean la posicion 12 + su 動態資料1 en la ventana (06/11/2026).

El 動態資料1 de la tarjeta es el indice en la tabla de compradas (0x005C: posiciones 12..48), no el numero del emote:
"Train ... no esta en mi pestana de emotes" -- con la lectura anterior Train (7) caia en las 12 fijas y no hacia nada.
"""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import inventario as inv  # noqa: E402
import presencia  # noqa: E402


def test_tarjeta_a_posicion():
    assert inv.posicion_de_tarjeta(inv.emote_de_tarjeta(3262)) == 12      # Wait (0): la primera comprada
    assert inv.posicion_de_tarjeta(inv.emote_de_tarjeta(3269)) == 19      # Train (7)
    assert inv.posicion_de_tarjeta(inv.emote_de_tarjeta(3275)) == 23      # Laugh (11)
    assert inv.posicion_de_tarjeta(inv.emote_de_tarjeta(3285)) == 33      # Silent (21): la ultima de la ventana
    assert inv.posicion_de_tarjeta(22) is None                            # fuera de la ventana (MaxEmotionIcon 34)


def test_ninguna_tarjeta_inglesa_cae_en_las_fijas():
    for item in range(3262, 3286):
        if inv.es_tarjeta_emocion(item):
            pos = inv.posicion_de_tarjeta(inv.emote_de_tarjeta(item))
            assert pos is not None and pos not in inv.EMOTES_BASICOS, item


def test_la_ventana_marca_la_posicion_y_se_puede_usar():
    pos = inv.posicion_de_tarjeta(7)                                       # Train
    flags = presencia.paquete_emotes_desbloqueados({pos})[2:]
    assert flags[pos - 12] == 1 and sum(flags) == 1
    assert inv.puede_usar_emocion(NS(emotes={pos}), pos)
    assert not inv.puede_usar_emocion(NS(emotes=set()), pos)
