"""Al cambiar de mapa, la mascota no se queda sola en el mapa viejo (05/11/2026).

"esos pet que?? no hay nadie y esta ahi": en el 0x0009 la mascota estrenaba entidad, se anunciaba aun en el mapa VIEJO
y luego presencia.salir borraba alli la nueva; la vieja, la que veian los demas, se quedaba para siempre.
"""
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _bloque():
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    i = fuente.find('# Re-spawn de la mascota activa al cambiar de mapa')
    j = fuente.find('_pres.entrar(ses, p.stage)', i)
    assert 0 < i < j
    return fuente[i:j]


def test_se_borra_la_vieja_antes_de_estrenar_entidad():
    b = _bloque()
    assert 0 <= b.find('notificar_mascota_despawn(ses, int(_pet_viejo))') < b.find("f_pet['entidad'] = _pet_siguiente_entidad(ses)")


def test_no_se_anuncia_en_el_mapa_viejo():
    assert '_pr.notificar_mascota_spawn(ses)' not in _bloque()
