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
    """La fila <drop> con las probabilidades de bolsas.probabilidades_bolsa: el principal al 1% y el resto por
    importancia (pestles, hammers y ride feed 7%, cartas de EXP 15%, lo demas a partes iguales)."""
    items = {int(n): int(v) for n, v in re.findall(r'\sitem(\d+)="(\d+)"', tag) if int(v) > 0}
    probs = {int(n): int(v) for n, v in re.findall(r'\sprob(\d+)="(\d+)"', tag) if int(n) in items}
    orden = sorted(probs)
    if not orden or orden[0] != 1:
        return tag
    reparto = bolsas.probabilidades_bolsa([(items[n], 1, probs[n]) for n in orden])
    if not reparto:
        return tag
    # EL CLIENTE NO DIVIDE POR LA SUMA: con factor="100" pinta cada prob como su porcentaje (prob1="10" -> 10%).
    # Asi que cada prob es ya su parte del factor de la fila, en enteros que sumen el factor justo (los restos de
    # redondear van a los que mas decimales perdieron). El factor no se toca.
    escala = int(re.search(r'\sfactor="(\d+)"', tag).group(1)) if re.search(r'\sfactor="(\d+)"', tag) else 100
    exactos = [escala * p for p in reparto]
    enteros = [int(x) for x in exactos]
    for k in sorted(range(len(exactos)), key=lambda k: exactos[k] - enteros[k], reverse=True)[:escala - sum(enteros)]:
        enteros[k] += 1
    nuevos = {n: max(1, v) for n, v in zip(orden, enteros)}

    def cambiar(m):
        n = int(m.group(1))
        return ' prob%d="%d"' % (n, nuevos[n]) if n in nuevos else m.group(0)
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
