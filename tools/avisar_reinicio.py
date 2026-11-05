"""Avisa a los jugadores del VPS de que el servidor se va a reiniciar (server/aviso_reinicio.py).

    python tools/avisar_reinicio.py 5                 # cuenta atras de 5 minutos (avisa a los 5, 3, 2, 1 min y 30 s)
    python tools/avisar_reinicio.py cancelar          # corta la cuenta atras
    python tools/avisar_reinicio.py aviso Texto libre # un mensaje cualquiera a todos

Escribe el comando en data/gm.txt del VPS, que el servidor lee cada medio segundo. Solo avisa: el reinicio lo hacen
tools/subir_servidor.py y tools/publicar_setting.py, que con --avisar N llaman a avisar() y esperan los N minutos
antes de reiniciar.
"""
import os
import shlex
import subprocess
import sys
import time

VPS = os.environ.get('AO_VPS', 'root@179.66.132.19')
VPS_DIR = os.environ.get('AO_VPS_DIR', '/opt/angels')


def _gm(linea):
    orden = 'printf "%%s\\n" %s >> %s/data/gm.txt' % (shlex.quote(linea), VPS_DIR)
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', VPS, orden], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('no se pudo escribir en el gm.txt del VPS: %s%s' % (r.stdout, r.stderr))


def avisar(minutos, esperar=True):
    """Lanza la cuenta atras en el VPS y, con esperar, no vuelve hasta que se acaba."""
    minutos = float(minutos)
    if minutos <= 0:
        return
    _gm('reinicio %g' % minutos)
    print('  aviso de reinicio enviado: %g min' % minutos)
    if not esperar:
        return
    fin = time.time() + minutos * 60
    while True:
        queda = int(fin - time.time())
        if queda <= 0:
            break
        print('  reinicio en %d:%02d' % divmod(queda, 60), end='\r', flush=True)
        time.sleep(min(5, queda))
    print('  fin de la cuenta atras, reiniciando        ')


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    if args[0].lower() in ('cancelar', 'cancel'):
        _gm('reinicio cancelar')
        print('cuenta atras cancelada')
    elif args[0].lower() == 'aviso':
        _gm('notice ' + ' '.join(args[1:]))      # el /notice de siempre (hace falta alguien dentro)
        print('aviso enviado')
    else:
        avisar(args[0], esperar=False)
        print('(solo avisa: el reinicio lo hace el script de subida)')


if __name__ == '__main__':
    main()
