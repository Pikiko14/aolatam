"""Sin la ventana del acuerdo al abrir el juego (12/11/2026: "que no se vean esos agreement, que pase directo a
iniciar sesion").

Lo que hace el exe (medido con capstone sobre el angel.dat descomprimido, base 0x400000). Hay DOS sitios que abren la
ventana 2951 "Please read the agreement":

1. LOGIN. 0x51a9a0 mira la bandera [0x9590b8] (ya mostrado en esta sesion); si no, lee agreement.txt (el suelto de la
   carpeta o el del pak) y, si existe, abre la ventana y espera a Agree. El parche salta siempre al final:
       0x51a9b3  75 02  jne 0x51a9b7   -->   90 90  nop nop   (cae en el jmp 0x51a9b5 -> 0x51aa21)

2. SELECCION DE PERSONAJE. 0x4bfde0 compara la fecha del acuerdo que manda el servidor ([0x9590b0]) con la del ultimo
   Agree ([0x9590b4], la pone el boton Agree: time(0)) y, si la del servidor es mayor, llama a 0x4c90c0, que vuelve a
   crear la ventana 2951 sobre la seleccion. Sin el acuerdo del login [0x9590b4] se queda en 0, la condicion se cumple
   y el juego se cerraba al entrar a la seleccion de personaje ("en el vps me esta crasheando", 12/11/2026). El parche
   no la abre nunca:
       0x4bfdec  76 0b  jbe 0x4bfdf9   -->   eb 0b  jmp 0x4bfdf9

Asi da igual el AGREEMENT.TXT que tenga cada jugador en su carpeta (los de IGG traen el suyo).

    python tools/sin_acuerdo_angel_dat.py <angel.dat>            # lo cambia en su sitio
    python tools/sin_acuerdo_angel_dat.py <angel.dat> --ver      # solo dice si ya lo lleva
"""
import argparse
import pathlib

PARCHES = (  # (offset en el archivo, original, parcheado, que es)
    (0x119db3, bytes.fromhex('7502eb6a'), bytes.fromhex('9090eb6a'), 'acuerdo del login'),
    (0xbf1ec, bytes.fromhex('760b8b8d'), bytes.fromhex('eb0b8b8d'), 'acuerdo de la seleccion de personaje'),
)


def estado(d: bytes, offset, antes, despues) -> str:
    trozo = bytes(d[offset:offset + len(antes)])
    return 'original' if trozo == antes else 'parcheado' if trozo == despues else 'desconocido (%s)' % trozo.hex()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exe')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    ruta = pathlib.Path(a.exe)
    d = bytearray(ruta.read_bytes())
    estados = [estado(d, o, x, y) for o, x, y, _q in PARCHES]
    for (_o, _x, _y, que), e in zip(PARCHES, estados):
        print('%s: %s' % (que, e))
    if a.ver:
        return
    if any(e.startswith('desconocido') for e in estados):
        raise SystemExit('no es el angel.dat esperado (descomprimido): no se toca')
    for (o, _x, despues, _q), e in zip(PARCHES, estados):
        if e == 'original':
            d[o:o + len(despues)] = despues
    ruta.write_bytes(bytes(d))
    print('listo: sin ventanas del acuerdo')


if __name__ == '__main__':
    main()
