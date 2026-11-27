"""Canjes retirados de exchange.xml (pasan al grupo 0: no se borran, el cliente se para en el primer hueco).

* 27/11/2026, Login Rewarder (grupo 526), "quita esos premios de login rewarder": Olympic Heart (18973), Smart
  Blessings Star (18974) y Smart Blessings Bell (18975).

Reescribe extracted_paks/update26/setting/eng (lo lee el servidor) y parches/extras/setting/eng (va en el parche).

    python tools/quitar_canjes.py
"""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CARPETAS = (RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng', RAIZ / 'parches' / 'extras' / 'setting' / 'eng')
RETIRADOS = (18973, 18974, 18975)


def quitar(texto):
    n = 0
    for num in RETIRADOS:
        texto, k = re.subn(r'(<exchange 編號="%d" 群組=")\d+(")' % num, r'\g<1>0\2', texto)
        n += k
    return texto, n


def main():
    for c in CARPETAS:
        f = c / 'exchange.xml'
        texto, n = quitar(f.read_bytes().decode('utf-8'))
        f.write_bytes(texto.encode('utf-8'))
        print(f, n)


if __name__ == '__main__':
    main()
