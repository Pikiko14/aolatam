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


def test_sale_el_cuadro_y_la_respuesta_suma_su_valor():
    s, f = _ses()
    app._crianza_tick(s, 1000.0)                                  # arranca el reloj
    assert not s.recibido
    app._crianza_tick(s, 1000.0 + ms.CADA_ESCENA)
    esc = s.crianza_escena
    assert [x for x in s.recibido if x == struct.pack('<HIBBII', 0x001D, s.personaje.entity_id, 1, 17, 12, esc)]
    valor = ms.situaciones()[str(esc)]['opciones'][0]['valor']
    app.Servidor.__new__(app.Servidor).manejar(s, 0x003E, None, None, 't', bytes([4]))
    assert f['crianza'] == valor and s.crianza_escena is None
