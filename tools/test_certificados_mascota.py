"""Certificados de sangre de mascota: el Medium (MBC) pide nivel 35, el Advanced (ABC) nivel 55
y solo vale despues del MBC (forma 中階). Cadena del Elf Egg: 3181 -> 3183 -> 3187 -> ..."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import mascotas as m


def _pet(sprite, nivel):
    return {'sprite': sprite, 'nivel': nivel, 'nombre': m.ficha_de_sprite(sprite)['nombre']}


def _etapa(f):
    return m.ficha_de_sprite(f['sprite'])['etapa']


def test_mbc_pide_nivel_35():
    f = _pet(3183, 34)
    ok, msg = m.aplicar_certificado(f, 2)
    assert not ok and '35' in msg and f['sprite'] == 3183
    f['nivel'] = 35
    assert m.aplicar_certificado(f, 2)[0] and _etapa(f) == '中階'


def test_abc_no_sirve_sin_mbc():
    f = _pet(3183, 60)
    ok, msg = m.aplicar_certificado(f, 3)
    assert not ok and 'Medium Blood Certificate' in msg and f['sprite'] == 3183


def test_abc_pide_nivel_55_y_va_tras_el_mbc():
    f = _pet(3183, 54)
    assert m.aplicar_certificado(f, 2)[0]
    medio = f['sprite']
    ok, msg = m.aplicar_certificado(f, 3)
    assert not ok and '55' in msg and f['sprite'] == medio
    f['nivel'] = 55
    assert m.aplicar_certificado(f, 3)[0] and _etapa(f) == '高階'


def test_mbc_sobre_un_huevo_hace_tambien_la_primera_forma():
    f = _pet(3181, 40)
    assert m.aplicar_certificado(f, 2)[0] and _etapa(f) == '中階'
