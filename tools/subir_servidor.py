"""Sube al VPS los archivos del servidor que cambiaron, reinicia y comprueba que quedaron iguales.

    python tools/subir_servidor.py                         # lo que difiere del VPS en server/ (te lo muestra y pregunta)
    python tools/subir_servidor.py server/app.py server/plantillas/item_mall.json   # solo esos
    python tools/subir_servidor.py --ver                   # solo dice que difiere, sin subir nada
    python tools/subir_servidor.py -y                      # sin preguntar

Compara por hash cada archivo de server/ que este en git (codigo .py y plantillas .json/.bin) con el del VPS, sube los distintos,
les pone de dueno a angels, reinicia angels.service (la API de la web va con el), espera a que arranque y vuelve
a comparar los hashes. Antes de subir avisa si hay cambios sin commit: lo que va al VPS deberia estar en git.

No toca la web (tools/publicar_web.py) ni el parche de los jugadores (tools/publicar_setting.py, tools/subir_mapa.py).
"""
import argparse
import hashlib
import os
import pathlib
import shlex
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VPS = os.environ.get('AO_VPS', 'root@77.42.52.122')
VPS_DIR = os.environ.get('AO_VPS_DIR', '/opt/angels')
# Lo que cambia en el VPS por su cuenta y no se pisa nunca.
NUNCA = {'server/configuracion_local.py'}
EXTENSIONES = {'.py', '.json', '.bin', '.txt'}


def ssh(orden, entrada=None):
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', VPS, orden], input=entrada, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('fallo en el VPS: %s\n%s%s' % (orden, r.stdout, r.stderr))
    return r.stdout


def md5(f):
    return hashlib.md5((RAIZ / f).read_bytes()).hexdigest()


def remotos(archivos):
    if not archivos:
        return {}
    # La lista va por la entrada (separada por NUL): son cientos de archivos y alguno lleva espacios.
    salida = ssh('cd %s && xargs -0 md5sum 2>/dev/null; true' % VPS_DIR, entrada=chr(0).join(archivos))
    return {l.split(None, 1)[1]: l.split(None, 1)[0] for l in salida.splitlines() if l.strip()}


def candidatos():
    """Los archivos de server/ que estan en git: lo que no esta (pruebas sueltas, .bak) no se sube solo."""
    rels = subprocess.run(['git', 'ls-files', '-z', 'server'], cwd=RAIZ, capture_output=True, text=True,
                          check=True).stdout.split(chr(0))
    return sorted(r for r in rels if r and pathlib.PurePosixPath(r).suffix in EXTENSIONES
                  and r not in NUNCA and (RAIZ / r).is_file())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archivos', nargs='*', help='rutas relativas al repo (por defecto: todo server/ que difiera)')
    ap.add_argument('--ver', action='store_true', help='solo mostrar lo que difiere')
    ap.add_argument('-y', action='store_true', help='no preguntar')
    a = ap.parse_args()

    lista = [pathlib.Path(x).as_posix() for x in a.archivos] or candidatos()
    for f in lista:
        if not (RAIZ / f).is_file():
            raise SystemExit('no existe %s' % f)
    rem = remotos(lista)
    distintos = [f for f in lista if rem.get(f) != md5(f)]
    if not distintos:
        print('El VPS ya tiene todo igual (%d archivos comparados).' % len(lista))
        return
    print('Distintos del VPS (%d):' % len(distintos))
    for f in distintos:
        print('  %s %s' % ('NUEVO ' if f not in rem else '      ', f))
    if a.ver:
        return
    sucios = subprocess.run(['git', 'status', '--porcelain', '--'] + distintos, cwd=RAIZ,
                            capture_output=True, text=True).stdout.strip()
    if sucios:
        print('\nAVISO: estos tienen cambios sin commit:\n' + sucios)
    if not a.y and input('\n¿Subir y reiniciar el servidor? [s/N] ').strip().lower() not in ('s', 'si', 'sí', 'y'):
        print('Cancelado.')
        return

    tgz = RAIZ / 'subir_servidor.tgz'
    try:
        subprocess.run(['tar', 'czf', tgz.name] + distintos, cwd=RAIZ, check=True)
        subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', tgz.name, VPS + ':/tmp/subir_servidor.tgz'],
                       cwd=RAIZ, check=True)
    finally:
        tgz.unlink(missing_ok=True)
    print(ssh('set -e; cd %s && tar xzf /tmp/subir_servidor.tgz && chown angels:angels %s && rm -f /tmp/subir_servidor.tgz && '
              'systemctl restart angels.service && sleep 10 && systemctl is-active angels.service angels-web-registro.service'
              % (VPS_DIR, ' '.join(shlex.quote(f) for f in distintos))).strip())
    rem = remotos(distintos)
    mal = [f for f in distintos if rem.get(f) != md5(f)]
    print('hashes iguales: %d de %d' % (len(distintos) - len(mal), len(distintos)))
    if mal:
        raise SystemExit('NO coinciden: %s' % mal)
    print('listo.')


if __name__ == '__main__':
    main()
