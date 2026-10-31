"""Publica la web de comunidad en el VPS (nginx sirve /var/www/angels-web; ver tools/deploy_web/angels-sitio.conf).

    python tools/publicar_web.py                  # web + launcher + API de cuentas, reinicia y compara hashes
    python tools/publicar_web.py --solo-web       # solo los archivos de la web (sin tocar el servidor del juego)

Sube tools/web_sitio/ tal cual y pone el launcher (parches/launcher_propio/AngelsLauncher.exe, el mismo que se
actualiza solo) en descargas/AngelsLauncher.exe, que es el boton "Descargar launcher" (config.js: launcherUrl).
Sin --solo-web sube tambien server/cuentas.py y server/web_registro.py y reinicia angels.service (la API de cuentas,
angels-web-registro.service, va con el: PartOf). Van juntas porque el juego ya no crea cuentas al entrar: sin la web
nueva nadie podria crear una.
"""
import argparse
import hashlib
import os
import pathlib
import subprocess
import tarfile
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
WEB = RAIZ / 'tools' / 'web_sitio'
LAUNCHER = RAIZ / 'parches' / 'launcher_propio' / 'AngelsLauncher.exe'
VPS = os.environ.get('AO_VPS', 'root@77.42.52.122')
DESTINO_WEB = '/var/www/angels-web'
DESTINO_JUEGO = os.environ.get('AO_VPS_DIR', '/opt/angels')
CODIGO = ['server/cuentas.py', 'server/web_registro.py']


def ssh(orden, entrada=None):
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', VPS, orden], input=entrada, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('fallo en el VPS: %s\n%s%s' % (orden, r.stdout, r.stderr))
    return r.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--solo-web', action='store_true')
    a = ap.parse_args()
    archivos = {str(f.relative_to(WEB)).replace('\\', '/'): f for f in WEB.rglob('*') if f.is_file()}
    if LAUNCHER.is_file():
        archivos['descargas/AngelsLauncher.exe'] = LAUNCHER
    else:
        print('AVISO: no esta %s (tools/compilar_launcher.py): la web no tendra launcher' % LAUNCHER.relative_to(RAIZ))
    with tempfile.TemporaryDirectory() as tmp:
        tgz = pathlib.Path(tmp) / 'web.tgz'
        with tarfile.open(tgz, 'w:gz') as t:
            for nombre, f in archivos.items():
                t.add(f, arcname='web/' + nombre)
            if not a.solo_web:
                for c in CODIGO:
                    t.add(RAIZ / c, arcname='juego/' + c)
        subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', str(tgz), VPS + ':/tmp/publicar_web.tgz'], check=True)
    # La web se reemplaza entera (asi desaparece lo que ya no esta, como las PNG viejas) y queda de www-data.
    orden = ('set -e; rm -rf /tmp/publicar_web && mkdir /tmp/publicar_web && tar xzf /tmp/publicar_web.tgz -C /tmp/publicar_web; '
             'rm -rf %(w)s.anterior; cp -a %(w)s %(w)s.anterior; rm -rf %(w)s/*; cp -a /tmp/publicar_web/web/. %(w)s/; '
             'chown -R www-data:www-data %(w)s' % {'w': DESTINO_WEB})
    if not a.solo_web:
        orden += ('; cp /tmp/publicar_web/juego/server/*.py %(j)s/server/ && chown angels:angels %(j)s/server/cuentas.py '
                  '%(j)s/server/web_registro.py && systemctl restart angels.service && sleep 8 && systemctl is-active '
                  'angels.service angels-web-registro.service' % {'j': DESTINO_JUEGO})
    print(ssh(orden + '; rm -rf /tmp/publicar_web /tmp/publicar_web.tgz').strip())
    comprobar = {DESTINO_WEB + '/' + n: f for n, f in archivos.items()}
    if not a.solo_web:
        comprobar.update({DESTINO_JUEGO + '/' + c: RAIZ / c for c in CODIGO})
    remoto = {l.split()[1]: l.split()[0] for l in ssh('md5sum ' + ' '.join(comprobar)).splitlines() if l.strip()}
    mal = [r for r, f in comprobar.items() if remoto.get(r) != hashlib.md5(f.read_bytes()).hexdigest()]
    print('hashes iguales: %d de %d' % (len(comprobar) - len(mal), len(comprobar)))
    if mal:
        raise SystemExit('NO coinciden: %s' % mal)


if __name__ == '__main__':
    main()
