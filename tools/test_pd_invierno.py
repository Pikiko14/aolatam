"""Winter Holiday PD normal: "deja solo eso que esta en rojo y eso que dice winter holiday pd, pero es la enchanted
hay una version de esa pd no enchanted?? si no la hay creala ... el server de momento no tendra enchanted pd"."""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import bolsas
import cliente_local
import inventario

cliente_local.registrar_medalla_en_servidor()


def test_las_maletas_dan_una_pieza_normal_de_su_sexo():
    for iid, _, _, piezas in cliente_local.MALETAS_INVIERNO:
        sale = {bolsas.abrir(iid)[0] for _ in range(80)}
        assert sale == set(piezas)


def test_el_exchange_de_winter_holiday_da_las_normales():
    for receta in range(22490, 22502):
        premios = app._obtener_receta_exchange(receta)['premios']
        assert all(p in cliente_local.GEMELOS_INVIERNO.values() for p, _ in premios), (receta, premios)


def test_las_piezas_van_en_la_misma_ranura_y_no_dan_stats():
    base = inventario.stats({}, None)
    for iid, gemelo, *_ in cliente_local.PD_INVIERNO:
        r = inventario.ranura_equipo_de(iid)
        assert r == inventario.ranura_equipo_de(gemelo)
        assert inventario.stats({r: iid}, None) == base, iid


def test_en_exchange_solo_quedan_tres_tiendas():
    from house_services import xml_rows
    grupos = {int(r['群組']) for r in xml_rows('exchangegroup.xml').values() if r.get('群組')}
    assert grupos == {622, 538, 595}
