"""Premios del Angel Pass de la temporada (pase.TEMPORADA): parches/extras/setting/battlepassprize.xml.

Pedido del usuario (15/11/2026): "cambia los premios por lucky pestles, hammer y green hammer; free da 30, el premium
da 60 (por nivel); el premium dara tambien ese set PD para male y female su correlativo, pero sin ser enchanted";
version: "6 estrellas para items 60" (los de equipo de nivel < 69).

  * cada nivel da UNO de los tres, por turnos: 6-star Lucky Enhanced Pestle, 6-star Piercing Hammer y el martillo
    verde 6-star Lucky Hammer; x30 el gratis y x60 el de pago;
  * el de pago da ademas el set Hunter PD normal (cliente_local.PD_HUNTER, copias sin Enchanted) en los niveles 15,
    30, 45 y 60: sombrero, chaqueta, munequera y botas. El XML lleva la pieza de hombre; pase.premios_pendientes
    cambia a la de mujer (Cherry Hunter) si el personaje es mujer.

El cliente pinta los premios con este XML (va en el parche) y el servidor los da leyendo el mismo (pase._ultimo mira
primero parches/extras). Solo se tocan las filas del grupo de la temporada; el resto queda como en el original.

    python tools/pase_premios.py
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

ORIGEN = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'battlepassprize.xml'
DESTINO = RAIZ / 'parches' / 'extras' / 'setting' / 'battlepassprize.xml'

PESTLE, HAMMER, GREEN_HAMMER = 6900, 1207, 7088      # los tres de 6 estrellas (equipo de nivel < 69)
TURNO = (PESTLE, HAMMER, GREEN_HAMMER)
GRATIS, PAGO = 30, 60
NIVELES_SET = (15, 30, 45, 60)                       # sombrero, chaqueta, munequera, botas


def piezas_set():
    import cliente_local
    return [p[0] for p in cliente_local.PD_HUNTER[:4]]   # las de hombre, en ese orden


def fila(original, set_por_nivel):
    a = dict(re.findall(r'(\S+)="([^"]*)"', original))
    nv = int(a['等級'])
    item = TURNO[(nv - 1) % len(TURNO)]
    partes = ['編號="%s"' % a['編號'], '群組編號="%s"' % a['群組編號']]
    if a.get('大獎'):
        partes.append('大獎="%s"' % a['大獎'])
    partes += ['等級="%d"' % nv, '經驗值="%s"' % a['經驗值'],
               '免費獎勵1道具ID="%d"' % item, '免費獎勵1道具數量="%d"' % GRATIS,
               '付費獎勵1道具ID="%d"' % item, '付費獎勵1道具數量="%d"' % PAGO]
    if nv in set_por_nivel:
        partes += ['付費獎勵2道具ID="%d"' % set_por_nivel[nv], '付費獎勵2道具數量="1"']
    return '<battlepassprize %s/>' % ' '.join(partes)


def generar():
    import pase
    grupo = pase._n(pase.temporada().get('獎勵群組ID'))
    set_por_nivel = dict(zip(NIVELES_SET, piezas_set()))
    texto = ORIGEN.read_bytes().decode('utf-8')          # con sus CRLF, como el original

    def cambiar(m):
        g = re.search(r'群組編號="(\d+)"', m.group(0))
        return fila(m.group(0), set_por_nivel) if g and int(g.group(1)) == grupo else m.group(0)

    nuevo = re.sub(r'<battlepassprize [^>]*/>', cambiar, texto)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_bytes(nuevo.encode('utf-8'))
    return grupo


if __name__ == '__main__':
    g = generar()
    print('battlepassprize.xml: grupo %d -> %s' % (g, DESTINO))
