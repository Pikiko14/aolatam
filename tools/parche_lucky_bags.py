"""El 1% del premio principal de las Lucky Bag del mall, tambien en el tooltip del cliente.

El servidor ya sortea el primer premio de las bolsas de Lucky Weapon / Lucky Armor / Ride al 1%
(bolsas.PROB_PREMIO_PRINCIPAL), pero el cliente pinta las probabilidades con su drop.xml ("Rose Sword * 1
10.00000%"). Este script reescribe en una copia de drop.xml las tablas de esas bolsas para que digan lo mismo
(los demas premios x99 y el principal = la suma de los demas: 1%) y la deja en parches/extras/, de donde sale
el parche de los jugadores.

    python tools/parche_lucky_bags.py
    python tools/publicar_setting.py drop.xml --sin-copiar      # parche + VPS
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import bolsas

ORIGEN = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'drop.xml'
SALIDA = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'drop.xml'


def tablas():
    """{tabla de drop: bolsa} de las bolsas del mall con el premio principal al 1%."""
    out = {}
    for iid in bolsas.bolsas_premio_al_1():
        que = bolsas._cargar().get(iid) or bolsas._cargar_extra().get(iid)
        if que and str(que[1]).isdigit():
            out[int(que[1])] = iid
    return out


def ajustar_fila(tag):
    """La fila <drop> con prob1 = suma de las demas y las demas x99 (si el principal pasaba del 1%)."""
    probs = {int(n): int(v) for n, v in re.findall(r'\sprob(\d+)="(\d+)"', tag)}
    items = {int(n) for n, v in re.findall(r'\sitem(\d+)="(\d+)"', tag) if int(v) > 0}
    probs = {n: p for n, p in probs.items() if n in items}
    if 1 not in probs or len(probs) < 2:
        return tag
    resto = sum(p for n, p in probs.items() if n != 1)
    if resto <= 0 or probs[1] / float(probs[1] + resto) <= bolsas.PROB_PREMIO_PRINCIPAL:
        return tag
    factor = round((1 - bolsas.PROB_PREMIO_PRINCIPAL) / bolsas.PROB_PREMIO_PRINCIPAL)      # 99

    def cambiar(m):
        n = int(m.group(1))
        if n not in probs:
            return m.group(0)
        return ' prob%d="%d"' % (n, resto if n == 1 else probs[n] * factor)
    return re.sub(r'\sprob(\d+)="\d+"', cambiar, tag)


def main():
    texto = ORIGEN.read_bytes().decode('utf-8')
    objetivo = tablas()
    cambiadas = []

    def fila(m):
        tag = m.group(0)
        num = re.search(r'編號="(\d+)"', tag)
        if not num or int(num.group(1)) not in objetivo:
            return tag
        nuevo = ajustar_fila(tag)
        if nuevo != tag:
            cambiadas.append(int(num.group(1)))
        return nuevo

    texto = re.sub(r'<drop 編號="\d+"[^>]*>', fila, texto)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(texto.encode('utf-8'))
    print('bolsas del mall: %d tablas; al 1%%: %d -> %s' % (len(objetivo), len(cambiadas), SALIDA.relative_to(RAIZ)))


if __name__ == '__main__':
    main()
