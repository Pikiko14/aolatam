r"""Prepara el launcher y el reg.ini que reciben los JUGADORES para actualizarse desde el VPS.

El START.EXE que deja el servidor local en tu cliente esta parcheado para NO actualizar nunca (da por hecho que tiene la ultima version) y apunta a
127.0.0.1. Para un jugador hay que partir del original (START.EXE.bak) y cambiar solo a donde mira: IP y puerto del FTP de actualizaciones y la
pagina del panel (la de noticias del VPS). El resto de la logica del actualizador queda como la de IGG.

Uso: python tools/preparar_launcher_vps.py --ip <IP-del-VPS> [--cliente "C:\AO\Angels Online"] [--puerto 2121] [--http 8280] [--salida dist/launcher_vps]
(sin --ip se usa la variable de entorno AO_PARCHE_HOST; la IP del servidor no se guarda en el repositorio)
Deja en la salida START.EXE y reg.ini: se copian sobre un cliente limpio (con LOADER.INI, update*.pak, etc.)."""
import argparse
import os
import pathlib
import struct

ap = argparse.ArgumentParser()
ap.add_argument('--cliente', default=r'C:\AO\Angels Online')
ap.add_argument('--ip', default=os.environ.get('AO_PARCHE_HOST'), required=not os.environ.get('AO_PARCHE_HOST'))
ap.add_argument('--puerto', type=int, default=2121)
ap.add_argument('--http', type=int, default=8280)
ap.add_argument('--salida', default='dist/launcher_vps')
a = ap.parse_args()

cli = pathlib.Path(a.cliente)
orig = cli / 'START.EXE.bak'
if not orig.exists():
    raise SystemExit('No esta %s: es el START.EXE original que guarda el servidor local.' % orig)
raw = bytearray(orig.read_bytes())
assert raw[0x07E008:0x07E008 + 19] == b'aoupdate1.iggcn.com', 'START.EXE.bak no es el original de IGG'
ip = a.ip.encode('ascii').ljust(20, b'\0')
assert len(a.ip) < 20
struct.pack_into('<I', raw, 0x07E004, a.puerto)           # puerto FTP por defecto
raw[0x07E008:0x07E008 + 20] = ip                          # IP por defecto
raw[0x0686E4:0x0686E4 + 20] = ip                          # IP de reserva
url = ('http://%s:%d/' % (a.ip, a.http)).encode('ascii')
assert len(url) < 28, 'la URL del panel no cabe en 28 bytes'
raw[0x0688C8:0x0688C8 + 28] = url.ljust(28, b'\0')        # panel embebido: noticias del VPS
# El launcher reescribe el reg.ini con fopen(ruta, "w"): en modo texto el CRT escribe CRLF, y con CRLF su propio instalador de parches
# falla la vez siguiente ("Error installing update pack"). Con "wb" lo escribe con LF y las actualizaciones siguientes funcionan.
assert raw[0x068A5C:0x068A60] == b'w\0\0\0', 'no es el modo "w" del reg.ini que se esperaba'
raw[0x068A5D] = ord('b')
salida = pathlib.Path(a.salida)
salida.mkdir(parents=True, exist_ok=True)
(salida / 'START.EXE').write_bytes(bytes(raw))
# Saltos de linea LF, NO CRLF: con CRLF el START.EXE de IGG lee mal el reg.ini y su instalador de parches falla siempre con
# "Error installing update pack" (medido 28/10/2026: mismo servidor y mismos paquetes, actualiza con LF y falla con CRLF).
(salida / 'reg.ini').write_bytes(
    ('[PROFILE]\nGameName = Angels Online\nVersion = 8.5.1.0\nGameDir = ./\nLoaderVer = 1.7\nPassiveMode = 1\n'
     'UpdateIP = %s\nUpdatePort = %d\n' % (a.ip, a.puerto)).encode('ascii'))
print('Listo en %s: START.EXE (%d bytes) y reg.ini -> %s:%d, panel %s' % (salida, len(raw), a.ip, a.puerto, url.decode()))
