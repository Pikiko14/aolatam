"""Entrar a un mapa donde alguien lleva un monstruo encantado reventaba presencia.entrar ('Monstruo' no tiene
`tipo`, tiene npc_type) antes de apuntar al jugador en el mapa: desde entonces no veia a nadie irse y los dejaba
como fantasmas. Reportado el 11/11/2026: "entramos a la raid y queda aca el personaje, el ya esta dentro"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate
import login
import presencia

STAGE = 41


class _Ses:
    def __init__(self, cid, nombre):
        self.personaje = login.Personaje(char_id=cid, entity_id=1000 + cid, nombre=nombre,
                                         stage=STAGE, hp=1000, hp_max=1000)
        self.inventario = {}
        self.writer = object()
        self.sent = []

    def enviar(self, *packets):
        self.sent.extend(packets)


def test_con_un_monstruo_encantado_en_el_mapa_el_que_entra_queda_apuntado_y_lo_ve():
    dueno, nuevo = _Ses(1, 'Baco'), _Ses(2, 'Zetha')
    m = combate.Monstruo(9001, 1, 'Slarm', (10, 10))
    m.vivo = True
    dueno.monstruo_encantado = m
    old = list(presencia._POR_MAPA.get(STAGE, []))
    try:
        presencia._POR_MAPA[STAGE] = [dueno]
        dueno._mapa_presencia = STAGE
        presencia.entrar(nuevo, STAGE)
        assert nuevo in presencia._POR_MAPA[STAGE] and nuevo._mapa_presencia == STAGE
        assert presencia._paquetes_encantado(dueno)[0] in nuevo.sent
    finally:
        presencia._POR_MAPA[STAGE] = old
