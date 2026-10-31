"""Publica XML de setting/eng editados a mano (premios de login u online, etc.): servidor, parche y launcher.

    python tools/publicar_setting.py onlinegift.xml
    python tools/publicar_setting.py logingift.xml onlinegift.xml      # varios a la vez
    python tools/publicar_setting.py onlinegift.xml --sin-vps          # todo menos subir al VPS
    python tools/publicar_setting.py onlinegift.xml --sin-git          # sin commit

Se edita el archivo en extracted_paks/update26/setting/eng/ (el que lee el servidor). Pasos:

  1. comprueba que el XML este bien formado (un atributo repetido, como dos 道具2 en la misma fila, lo rompe)
  2. lo copia a parches/extras/setting/eng/, de donde sale el parche de los jugadores
  3. rehace parches/update27.pak (sube la version) y los paquetes del launcher
  4. commit + push de la copia de parches/extras y de tools/pak_launcher.txt
  5. sube al VPS el XML, el parche y los paquetes, reinicia angels.service y compara los hashes

Al abrir el launcher, los jugadores ven la version nueva y bajan update27.pak solo.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
VPS = os.environ.get('AO_VPS', 'root@77.42.52.122')
VPS_DIR = os.environ.get('AO_VPS_DIR', '/opt/angels')
EXTRAS = RAIZ / 'parches' / 'extras' / 'setting' / 'eng'
sys.stdout.reconfigure(encoding='utf-8')


def correr(orden, **kw):
    print('  $', ' '.join(map(str, orden)))
    subprocess.run(orden, cwd=RAIZ, check=True, **kw)


def ssh(orden):
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', VPS, orden], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('fallo en el VPS: %s\n%s%s' % (orden, r.stdout, r.stderr))
    return r.stdout


def origen(nombre):
    """El archivo del update mas nuevo que lo trae (como lo busca el servidor)."""
    mejor = None
    for p in (RAIZ / 'extracted_paks').glob('*/setting/eng/' + nombre):
        m = re.fullmatch(r'update(\d*)', p.parents[2].name.lower())
        if m and (mejor is None or int(m.group(1) or 0) > mejor[0]):
            mejor = (int(m.group(1) or 0), p)
    if not mejor:
        raise SystemExit('no esta %s en extracted_paks/update*/setting/eng/' % nombre)
    return mejor[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archivos', nargs='+', help='nombres de setting/eng, p. ej. onlinegift.xml')
    ap.add_argument('--sin-vps', action='store_true')
    ap.add_argument('--sin-git', action='store_true')
    a = ap.parse_args()

    print('1. comprobando el XML')
    fuentes = {}
    for nombre in a.archivos:
        nombre = pathlib.Path(nombre).name.lower()
        f = origen(nombre)
        try:
            ET.parse(f)
        except ET.ParseError as e:
            raise SystemExit('  %s esta roto: %s (corrigelo y vuelve a correr)' % (f.relative_to(RAIZ), e))
        fuentes[nombre] = f
        print('  ok', f.relative_to(RAIZ))

    print('2. copiando a parches/extras')
    EXTRAS.mkdir(parents=True, exist_ok=True)
    for nombre, f in fuentes.items():
        shutil.copyfile(f, EXTRAS / nombre)

    print('3. parche y paquetes del launcher')
    sys.path.insert(0, str(RAIZ / 'server'))
    sys.path.insert(0, str(RAIZ / 'tools'))
    import parche
    import subir_mapa
    e = parche.generar()
    version = e['version']
    print('  parche', version, e['bytes'], 'bytes')
    pak = subir_mapa.pak_para(version)
    correr([PY, '-I', 'tools/generar_paquetes_launcher.py'],
           env=dict(os.environ, AO_PARCHE_PAK_LAUNCHER=pak, AO_PARCHE_HOST=VPS.split('@')[-1]))

    extras_rel = ['parches/extras/setting/eng/' + n for n in fuentes]
    if not a.sin_git:
        print('4. commit + push')
        correr(['git', 'add', '-f'] + extras_rel)
        correr(['git', 'add', 'tools/pak_launcher.txt'])
        if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=RAIZ).returncode:
            correr(['git', 'commit', '-q', '-m', 'Setting: %s (parche %s)' % (', '.join(fuentes), version)])
            correr(['git', 'push', '-q'])
        else:
            print('  nada nuevo para git')

    if a.sin_vps:
        print('listo (sin VPS)')
        return
    print('5. VPS')
    archivos = [str(f.relative_to(RAIZ)).replace('\\', '/') for f in fuentes.values()] + extras_rel + [
        'parches/update27.pak', 'parches/version.json']
    tgz = RAIZ / 'publicar_setting.tgz'
    try:
        correr(['tar', 'czf', tgz.name] + archivos + ['parches/launcher'])
        correr(['scp', '-q', '-o', 'BatchMode=yes', tgz.name, '%s:/tmp/publicar_setting.tgz' % VPS])
    finally:
        tgz.unlink(missing_ok=True)
    print(ssh('set -e; cd %s && rm -rf parches/launcher.anterior && mv parches/launcher parches/launcher.anterior && '
              'tar xzf /tmp/publicar_setting.tgz && chown -R angels:angels parches %s && rm -f /tmp/publicar_setting.tgz && '
              'systemctl restart angels.service && sleep 10 && systemctl is-active angels.service angels-web-registro.service'
              % (VPS_DIR, ' '.join(archivos[:len(fuentes)]))).strip())
    remoto = {l.split()[1]: l.split()[0] for l in ssh('cd %s && md5sum %s' % (VPS_DIR, ' '.join(archivos))).splitlines()}
    mal = [f for f in archivos if remoto.get(f) != hashlib.md5((RAIZ / f).read_bytes()).hexdigest()]
    print('  hashes iguales: %d de %d' % (len(archivos) - len(mal), len(archivos)))
    if mal:
        raise SystemExit('  NO coinciden: %s' % mal)
    servido = json.loads(ssh("curl -s http://127.0.0.1:2121/launcher.json")).get('version')
    print('  el launcher anuncia la version', servido)
    if servido != version:
        raise SystemExit('  el launcher deberia anunciar %s' % version)
    print('listo: los jugadores bajan la %s al abrir el launcher' % version)


if __name__ == '__main__':
    main()
