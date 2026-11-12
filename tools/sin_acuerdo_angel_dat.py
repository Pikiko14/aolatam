"""Sin la ventana del acuerdo al abrir el juego (12/11/2026: "que no se vean esos agreement, que pase directo a
iniciar sesion").

Lo que hace el exe (medido con capstone sobre el angel.dat descomprimido, base 0x400000): al llegar a la pantalla de
login, 0x51a9a0 mira la bandera [0x9590b8] (ya mostrado en esta sesion); si no, lee agreement.txt (el suelto de la
carpeta del juego o el del pak) y, si existe, abre la ventana 2951 "Please read the agreement" y espera a Agree. Sin
el archivo pasa de largo y el login sale solo. El parche cambia el salto del principio:

    0x51a9b3  75 02   jne 0x51a9b7   (si no se mostro aun, ir a leerlo)
    -->       90 90   nop nop        (siempre al jmp 0x51a9b5 -> 0x51aa21: salir sin leer nada)

Asi da igual el AGREEMENT.TXT que tenga cada jugador en su carpeta (los de IGG traen el suyo).

    python tools/sin_acuerdo_angel_dat.py <angel.dat>            # lo cambia en su sitio
    python tools/sin_acuerdo_angel_dat.py <angel.dat> --ver      # solo dice si ya lo lleva
"""
import argparse
import pathlib

OFFSET = 0x119db3                       # en el archivo (.text: va 0x51a9b3)
ANTES = bytes.fromhex('7502eb6a')       # jne +2 ; jmp 0x51aa21
DESPUES = bytes.fromhex('9090eb6a')


def estado(d: bytes) -> str:
    trozo = bytes(d[OFFSET:OFFSET + 4])
    return 'original' if trozo == ANTES else 'parcheado' if trozo == DESPUES else 'desconocido (%s)' % trozo.hex()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exe')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    ruta = pathlib.Path(a.exe)
    d = bytearray(ruta.read_bytes())
    e = estado(d)
    print(ruta.name, e)
    if a.ver or e == 'parcheado':
        return
    if e != 'original':
        raise SystemExit('no es el angel.dat esperado (descomprimido): no se toca')
    d[OFFSET:OFFSET + 4] = DESPUES
    ruta.write_bytes(bytes(d))
    print('listo: sin ventana del acuerdo')


if __name__ == '__main__':
    main()
