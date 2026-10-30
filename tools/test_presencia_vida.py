"""Al entrar a un mapa a veces se veia muertos a jugadores vivos: al presentar a un jugador no
se mandaba su vida, y el cliente se quedaba con el "muerto" de antes (la muerte de PvP se
manda como muerte de monstruo, y entidad_de reutiliza los ids publicos). Reportado: "a veces
que entro veo a los personajes muertos cuando no lo estan"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate
import login
import presencia

STAGE = 41


class _Ses:
    def __init__(self, cid, nombre, hp):
        self.personaje = login.Personaje(char_id=cid, entity_id=1000 + cid, nombre=nombre,
                                         stage=STAGE, hp=hp, hp_max=5000)
        self.inventario = {}
        self.writer = object()
        self.sent = []

    def enviar(self, *packets):
        self.sent.extend(packets)


def test_al_entrar_cada_uno_recibe_la_vida_del_otro():
    vivo, nuevo = _Ses(1, 'Vivo', 4321), _Ses(2, 'Nuevo', 1234)
    old = list(presencia._POR_MAPA.get(STAGE, []))
    try:
        presencia._POR_MAPA[STAGE] = [vivo]
        vivo._mapa_presencia = STAGE
        presencia.entrar(nuevo, STAGE)
        assert combate.atributo(presencia.entidad_de(vivo), 4321, combate.KIND_HP) in nuevo.sent
        assert combate.atributo(presencia.entidad_de(nuevo), 1234, combate.KIND_HP) in vivo.sent
    finally:
        presencia._POR_MAPA[STAGE] = old
        for s in (vivo, nuevo):
            presencia.liberar_entidad(s)


def test_un_muerto_se_presenta_con_vida_cero():
    muerto = _Ses(3, 'Muerto', 4000)
    muerto.muerto = True
    assert presencia._vida_publica(muerto) == combate.atributo(
        presencia.entidad_de(muerto), 0, combate.KIND_HP)
    presencia.liberar_entidad(muerto)
