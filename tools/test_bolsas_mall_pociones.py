"""Las bolsas del Item Mall no dan pociones de vida o mana mejores que la Common
(pedido del usuario: "quita de todas las bag que tenemos en item mall pociones de 2k, de 800...")."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas


def test_que_cuenta_como_pocion_fuerte():
    for low_o_common in (66, 67, 1352, 1353):
        assert not bolsas.pocion_fuerte(low_o_common)
    for fuerte in (1354, 1355, 8101, 8102, 23470, 18955):
        assert bolsas.pocion_fuerte(fuerte)
    assert not bolsas.pocion_fuerte(3805)          # un scroll no es pocion


def test_ninguna_bolsa_del_mall_da_pociones_fuertes():
    probadas = 0
    for b in bolsas.bolsas_del_mall():
        if not any(bolsas.pocion_fuerte(h) for h in bolsas._hijos(b)):
            continue
        probadas += 1
        for _ in range(40):
            premio = bolsas.abrir(b)
            assert not premio or not bolsas.pocion_fuerte(premio[0]), b
        d = bolsas.contenido_descrito(b)
        assert not d or not any(bolsas.pocion_fuerte(i) for i, _ in d[1]), b
    assert probadas, 'alguna bolsa del mall tenia pociones fuertes'
