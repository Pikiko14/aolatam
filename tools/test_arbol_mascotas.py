"""El arbol de evolucion de la mascota (server/arbol_mascotas.py), 10/11/2026: "podemos hacer algo asi?? ... hazlo"."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import arbol_mascotas as am  # noqa: E402
import mascotas as m  # noqa: E402

FUZZ = [3339, 3340, 3341, 3342, 3343, 3344, 3345, 3346, 3347, 3348, 3347, 3348, 3349, 3349, 3350]


def test_el_arbol_es_el_de_pet_xml_en_orden_de_monton():
    assert am.arbol(am.raiz(3346)) == FUZZ               # desde cualquier forma se llega a su huevo
    assert am.arbol(am.raiz(3990))[:8] == [3990, 3991, None, 3992, None, None, None, 3993]   # Abyss: una rama


def test_camino_solo_hacia_abajo():
    assert am.camino(1, 7) == [3, 7]
    assert am.camino(0, 14) == [2, 6, 14]
    assert am.camino(2, 7) is None and am.camino(3, 3) is None


def test_la_ficha_trae_lo_de_la_ventana():
    d = am.ficha_de(3346, 3342)
    assert d['nombre'] == 'Hell Spawn' and d['nivel'] == 55 and d['clase'] == 'DPS'
    assert 'Swamp Devil' in d['texto'] and len(d['habilidades']) == 3 and d['retrato']


def test_la_ruta_elegida_manda_sobre_la_crianza():
    f = {'sprite': 3340, 'nivel': 40, 'crianza': -100, 'ruta': [3343, 3348]}
    assert m.rama_por_crianza(f) == 'nice'               # 3343 es la rama 2 de 3340, aunque la crianza diga la 1
    f['ruta'] = []
    assert m.rama_por_crianza(f) == 'mean'


def _ses(ficha, monkeypatch, inventario=None):
    enviados = []
    monkeypatch.setattr(app, '_pet_tras_evolucion', lambda ses, f, msg, ranura_gastada=None:
                        enviados.append(('evolucion', ranura_gastada)))
    import cuentas
    monkeypatch.setattr(cuentas, 'guardar_mascota', lambda *a, **k: None)
    p = NS(mascota=ficha, mascotas={}, char_id=1)
    return NS(personaje=p, inventario=inventario or {}, usuario='u', enviar=lambda *a: None), enviados


def test_el_huevo_con_nivel_evoluciona_a_la_forma_elegida(monkeypatch):
    f = {'sprite': 3339, 'nivel': 16, 'nombre': 'Fuzz Ball Egg'}
    ses, env = _ses(f, monkeypatch)
    aviso = am.evolucionar(ses, 13)                      # Celestial... la hoja 13 cuelga de la rama 2
    assert f['sprite'] == 3341 and env == [('evolucion', None)] and 'evolved' in aviso
    assert f['ruta'] == [3341, 3345, FUZZ[13]]


def test_sin_certificado_guarda_el_camino_y_lo_dice(monkeypatch):
    f = {'sprite': 3340, 'nivel': 40, 'nombre': 'Purple Fuzz Ball', 'crianza': -100}
    ses, env = _ses(f, monkeypatch)
    aviso = am.evolucionar(ses, 4)
    assert f['sprite'] == 3340 and not env and 'Medium Blood Certificate' in aviso and f['ruta'] == [3343]
    assert m.rama_por_crianza(f) == 'nice'


def test_con_certificado_lo_gasta_y_evoluciona(monkeypatch):
    f = {'sprite': 3340, 'nivel': 40, 'nombre': 'Purple Fuzz Ball'}
    ses, env = _ses(f, monkeypatch, inventario={25: 3377})
    am.evolucionar(ses, 4)
    assert f['sprite'] == 3343 and env == [('evolucion', 25)]


def test_no_deja_saltar_a_otra_rama(monkeypatch):
    f = {'sprite': 3340, 'nivel': 60, 'nombre': 'Purple Fuzz Ball'}
    ses, env = _ses(f, monkeypatch, inventario={25: 3377})
    assert 'cannot' in am.evolucionar(ses, 5) and f['sprite'] == 3340 and not env


def test_cada_forma_trae_su_imagen_y_su_tipo_en_ingles():
    # 10/11/2026: "algunos se ven el mismo icono", "pudiese salir la imagen al lado de cada cuadrito" y los ????.
    nodos = am.arbol(am.raiz(3099))                      # la linea del Heady Dragon
    fichas = [am.ficha_de(p) for p in nodos if p]
    assert all(f['icono'] >= am.PRIMER_PEQUENO and f['retrato'] >= am.PRIMER_ICONO for f in fichas)
    distintas = {f['retrato'] for f in fichas}
    assert len(distintas) == len({p for p in nodos if p})   # una imagen por forma, no las de pet.xml repetidas
    assert all(f['clase'] and all(ord(c) < 128 for c in f['clase']) for f in fichas)
    assert all(ord(c) < 128 for v in am.CLASE.values() for c in v)
