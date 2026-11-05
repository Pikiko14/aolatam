"""La crianza de mascotas (05/11/2026: "no esta la crianza de mascota, validalo").

El cuadro lo abre el servidor con un 0x001D codigo 17 subtipo 12 y el numero de la escena (petaspect.xml); no se
mandaba nunca. Y la respuesta sumaba cero porque no se sabia que escena habia salido.
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402
import mascotas as ms  # noqa: E402

HUEVO_ELFO = 3085      # Elf Egg: evoluciona por las dos ramas


def _ses():
    p = login.Personaje()
    f = {'fuera': True, 'sprite': HUEVO_ELFO, 'nombre': 'Elf Egg', 'crianza': 0}
    p.mascota = f
    r = []
    return NS(personaje=p, rol='mundo', entity_id=p.entity_id, pet_entity_id=1069600, muerto=False, recibido=r,
              enviar=lambda *pk: r.extend(pk), enviar_inmediato=lambda *pk: r.extend(pk)), f


def test_las_escenas_son_del_tipo_de_la_mascota():
    tipo = ms.tipo_de_reaccion(HUEVO_ELFO)
    assert tipo and ms.puede_criarse({'sprite': HUEVO_ELFO})
    esc = ms.escena_para({'sprite': HUEVO_ELFO})
    assert ms.situaciones()[str(esc)]['tipo'] == tipo


def test_al_subir_de_nivel_sale_el_cuadro_y_la_respuesta_suma_su_valor():
    """"cada que se sube 1 lvl pide seleccionar 1 de esto y dependiendo de la crianza sale x pet"."""
    s, f = _ses()
    f.update({'nivel': 3, 'exp': 0})
    app._crianza_tick(s, 1000.0)
    assert not s.recibido                                          # sin subir de nivel, nada
    assert ms.dar_exp(f, ms.exp_para_subir(3, HUEVO_ELFO)) == 1
    app._crianza_tick(s, 1001.0)
    esc = s.crianza_escena
    assert [x for x in s.recibido if x == struct.pack('<HIBBII', 0x001D, s.personaje.entity_id, 1, 17, 12, esc)]
    valor = ms.situaciones()[str(esc)]['opciones'][0]['valor']
    app.Servidor.__new__(app.Servidor).manejar(s, 0x003E, None, None, 't', bytes([4]))
    assert f['crianza'] == valor and s.crianza_escena is None
    s.recibido.clear()
    app._crianza_tick(s, 1002.0)
    assert not s.recibido                                          # uno por nivel


def test_comando_gm_pide_una_escena_ya():
    import gm
    s, f = _ses()
    s.inventario = {30: 1}
    s.personaje.mascotas = {'30': f}
    f['ranura'] = 30
    msg, pk = gm._pet(s, ['crianza'])
    assert pk and s.crianza_escena and 'scene' in msg
