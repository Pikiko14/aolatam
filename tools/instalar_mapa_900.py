"""Instala en el servidor el mapa 900 (Dark Cavern) que acabas de exportar en el editor de mapas.

Uso, despues de "Exportar .mpc" en el editor:

    python tools/instalar_mapa_900.py                 # prepara todo en tu PC y pasa las pruebas
    python tools/instalar_mapa_900.py --subir         # ademas lo sube al VPS, lo reinicia y comprueba los hashes

Que hace, en orden (cada paso falla en voz alta si algo sale mal):

  1. copia salida/MAP900.mpc a tools/mapas_propios/map900.mpc (lo que se guarda en git) y a parches/extras/map
  2. actualiza la colision del servidor (transitable.bin) con el mapa nuevo
  3. repara la plantilla de monstruos (sellos, sprites que se ven, -30% de vida, jefe): tools/reparar_instancia_oscura.py
  4. pasa los eventos del mapa al servidor (plantillas/eventos.json, solo el mapa 900)
  5. deja la fila del mapa en stage.xml y rehace el parche (parches/update27.pak) y los paquetes del launcher
  6. corre las pruebas de la instancia
  7. con --subir: sube plantilla, colision, eventos, parche y paquetes al VPS, reinicia angels.service y compara hashes

El commit en git NO lo hace: revisalo y hazlo tu (o pidemelo).
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
STAGE = 900
EXPORTADO = RAIZ / 'tools' / 'editor_mapas' / 'salida' / ('MAP%d.mpc' % STAGE)
GUARDADO = RAIZ / 'tools' / 'mapas_propios' / ('map%d.mpc' % STAGE)
EXTRAS = RAIZ / 'parches' / 'extras' / 'map' / ('map%d.mpc' % STAGE)
VPS = os.environ.get('AO_VPS', 'root@77.42.52.122')
VPS_DIR = os.environ.get('AO_VPS_DIR', '/opt/angels')


def paso(n, texto):
    print('\n[%s] %s' % (n, texto), flush=True)


def correr(args, env=None, **kw):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run(args, cwd=RAIZ, env=e, **kw)
    if r.returncode:
        raise SystemExit('FALLO: %s (codigo %d)' % (' '.join(map(str, args)), r.returncode))
    return r


def codigo(texto, env=None):
    """Corre un trozo de python aparte (server/ y tools/ tienen un transitable.py cada uno: no se mezclan en un proceso)."""
    correr([PY, '-c', texto], env=env)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--subir', action='store_true', help='sube al VPS y lo reinicia')
    ap.add_argument('--pak', default=os.environ.get('AO_PARCHE_PAK_LAUNCHER', 'update28'),
                    help='pak donde el launcher instala el parche (por defecto update28; ver configuracion.PARCHE_PAK_LAUNCHER)')
    ap.add_argument('--sin-pruebas', action='store_true')
    a = ap.parse_args()

    paso(1, 'copiar el mapa exportado')
    if not EXPORTADO.exists():
        raise SystemExit('No esta %s: exporta el mapa 900 desde el editor ("Exportar .mpc").' % EXPORTADO)
    GUARDADO.parent.mkdir(parents=True, exist_ok=True)
    EXTRAS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXPORTADO, GUARDADO)
    shutil.copyfile(EXPORTADO, EXTRAS)
    print('  %s (%d bytes)' % (GUARDADO.relative_to(RAIZ), GUARDADO.stat().st_size))

    paso(2, 'colision del servidor (transitable.bin)')
    codigo("import sys,pathlib; sys.path.insert(0,'server'); sys.path.insert(0,'tools'); import instalar_mapa as im;"
           "d=pathlib.Path(r'%s').read_bytes(); print('  mapa', im.comprobar_mpc(d)); im.actualizar_transitable(%d,d)" % (GUARDADO, STAGE))

    paso(3, 'reparar la plantilla de monstruos')
    correr([PY, 'tools/reparar_instancia_oscura.py'])

    paso(4, 'eventos del mapa -> servidor')
    codigo("import sys,json,pathlib; sys.path.insert(0,'server'); sys.path.insert(0,'tools'); import propagar_eventos as pe;"
           "d=pe._del_mapa(%d,pathlib.Path(r'%s')); p=pathlib.Path('server/plantillas/eventos.json'); j=json.loads(p.read_text(encoding='utf-8'));"
           "hay=any(d[k] for k in ('disparadores','objetos','generadores','monstruos','temporizadores'));"
           "(j['stages'].__setitem__('%d',d) if hay else j['stages'].pop('%d',None));"
           "p.write_text(json.dumps(j,ensure_ascii=False,separators=(',',':')),encoding='utf-8');"
           "print('  eventos del mapa %d:', len(d['disparadores']), 'disparadores,', len(d['objetos']), 'objetos enlazados')"
           % (STAGE, GUARDADO, STAGE, STAGE, STAGE))

    paso(5, 'stage.xml, parche y paquetes del launcher')
    codigo("import sys,pathlib; sys.path.insert(0,'tools'); sys.path.insert(0,'server'); import generar_instancia_oscura as g;"
           "g.registrar_stage(pathlib.Path('parches/extras')); print('  fila del stage %d en stage.xml')" % STAGE)
    codigo("import sys; sys.path.insert(0,'server'); import parche; e=parche.generar(); print('  parche', e['version'], e['bytes'], 'bytes')")
    correr([PY, '-I', 'tools/generar_paquetes_launcher.py'],
           env={'AO_PARCHE_PAK_LAUNCHER': a.pak, 'AO_PARCHE_HOST': '77.42.52.122'})

    if not a.sin_pruebas:
        paso(6, 'pruebas')
        correr([PY, '-m', 'pytest', 'tools/test_instancia_oscura.py', 'tools/test_eventos.py', '-q', '-p', 'no:cacheprovider'])

    if a.subir:
        paso(7, 'subir al VPS (%s:%s)' % (VPS, VPS_DIR))
        archivos = ['server/plantillas/dark_cavern.json', 'server/plantillas/transitable.bin', 'server/plantillas/eventos.json',
                    'parches/update27.pak', 'parches/version.json', 'parches/extras/map/map%d.mpc' % STAGE,
                    'parches/extras/setting/eng/stage.xml']
        tgz = RAIZ / 'subida_mapa_900.tgz'
        try:
            correr(['tar', 'czf', tgz.name] + archivos + ['parches/launcher'])
            correr(['scp', '-q', '-o', 'BatchMode=yes', tgz.name, '%s:/tmp/subida_mapa_900.tgz' % VPS])
            correr(['ssh', '-o', 'BatchMode=yes', VPS,
                    'cd %s && rm -rf parches/launcher.anterior && mv parches/launcher parches/launcher.anterior && '
                    'tar xzf /tmp/subida_mapa_900.tgz && chown -R angels:angels parches server/plantillas && rm -f /tmp/subida_mapa_900.tgz && '
                    'systemctl restart angels.service && sleep 5 && systemctl is-active angels.service' % VPS_DIR])
        finally:
            if tgz.exists():
                tgz.unlink()
        # comprobacion: hash de cada archivo, aqui y alla
        local = {f: hashlib.md5((RAIZ / f).read_bytes()).hexdigest() for f in archivos}
        r = subprocess.run(['ssh', '-o', 'BatchMode=yes', VPS, 'cd %s && md5sum %s' % (VPS_DIR, ' '.join(archivos))],
                           cwd=RAIZ, capture_output=True, text=True)
        remoto = {l.split()[1]: l.split()[0] for l in r.stdout.splitlines() if l.strip()}
        mal = [f for f in archivos if remoto.get(f) != local[f]]
        print('  hashes iguales: %d de %d' % (len(archivos) - len(mal), len(archivos)))
        if mal:
            raise SystemExit('NO coinciden: %s' % mal)

    print('\nListo. %s' % ('Subido al VPS.' if a.subir else 'Falta subirlo: vuelve a correr con --subir (o pidemelo).'))
    print('Despues: abre el launcher del cliente del VPS y actualiza.')


if __name__ == '__main__':
    main()
