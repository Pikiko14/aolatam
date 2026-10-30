"""Aprendido el rango II de un hechizo, el I seguia saliendo aparte: al entrar se mandaban
todos los rangos y el cliente pone un icono por cada uno. Reportado por el usuario: "los
spell lvl 1 si aprendo el lvl 2 no se stakea en el arbol"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import clases
import gm
import skills

SLICING_I, SLICING_II, SWIFTNESS_I = 601, 612, 602


def _ids(paquetes):
    out = []
    for pk in paquetes:
        n = pk[6]
        for k in range(n):
            out.append(struct.unpack_from('<BII', pk, 7 + 9 * k)[1])
    return out


def test_el_rango_alto_tapa_al_bajo_de_su_linea():
    assert _ids(clases.otorgar_hechizos(1, [SLICING_I, SWIFTNESS_I, SLICING_II])) == [SWIFTNESS_I, SLICING_II]


def test_cada_linea_queda_con_lo_suyo():
    assert sorted(skills.rango_mayor_por_linea([SLICING_I, SWIFTNESS_I])) == [SLICING_I, SWIFTNESS_I]


def test_gm_hechizo_manda_el_paquete_tal_cual():
    enviados = []
    s = NS(personaje=NS(entity_id=77, nombre='GM'), enviar=lambda *pk: enviados.extend(pk))
    gm.aplicar(s, gm.parsear('hechizo 601 0'))
    pk = next(p for p in enviados if p[:2] == struct.pack('<H', 0x001D))
    assert struct.unpack_from('<IBBII', pk, 2) == (77, 1, clases.KIND_HECHIZO, SLICING_I, 0)
