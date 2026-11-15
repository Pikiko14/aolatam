"""Angel Pass con Lucky Pestle, Piercing Hammer y Lucky Hammer verde de 6 estrellas (30 gratis / 60 de pago por nivel)
y el set Hunter PD normal en el de pago (tools/pase_premios.py, 15/11/2026)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import cliente_local
import inventario
import pase
import pase_premios

cliente_local.registrar_medalla_en_servidor()


class _Est:
    def __init__(self, nivel, pase_pago=True):
        self.nivel, self.gratis, self.pago, self.pase = nivel, 0, 0, pase_pago


def test_el_servidor_lee_los_premios_del_parche():
    assert pase._ultimo('battlepassprize.xml') == pase_premios.DESTINO


def test_cada_nivel_da_uno_de_los_tres_x30_y_x60():
    p = pase.premios()
    assert len(p) == 60
    for nv, f in p.items():
        item = pase_premios.TURNO[(nv - 1) % 3]
        assert (int(f['免費獎勵1道具ID']), int(f['免費獎勵1道具數量'])) == (item, 30)
        assert (int(f['付費獎勵1道具ID']), int(f['付費獎勵1道具數量'])) == (item, 60)


def test_el_pago_da_el_set_de_hombre_o_su_pareja_de_mujer():
    hombre = [it for it, c in pase.premios_pendientes(_Est(60)) if it in cliente_local.HUNTER_MUJER]
    mujer = [it for it, c in pase.premios_pendientes(_Est(60), mujer=True)
             if it in cliente_local.HUNTER_MUJER.values()]
    assert hombre == [p[0] for p in cliente_local.PD_HUNTER[:4]]
    assert mujer == [p[0] for p in cliente_local.PD_HUNTER[4:]]
    gratis = pase.premios_pendientes(_Est(60, pase_pago=False))
    assert not any(it in cliente_local.HUNTER_MUJER for it, _ in gratis) and len(gratis) == 60


def test_el_set_hunter_es_solo_estetico_y_va_en_su_ranura():
    base = inventario.stats({}, None)
    for iid, gemelo, *_ in cliente_local.PD_HUNTER:
        r = inventario.ranura_equipo_de(iid)
        assert r == inventario.ranura_equipo_de(gemelo)
        assert inventario.stats({r: iid}, None) == base, iid
