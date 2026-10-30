"""Instala en el servidor un mapa exportado del editor de mapas, por su NUMERO.

    python tools/subir_mapa.py 900                 # prepara todo en tu PC y pasa las pruebas
    python tools/subir_mapa.py 900 --subir         # ademas lo sube al VPS, lo reinicia y compara hashes
    python tools/subir_mapa.py 1200 --nombre "Mi Mapa" --subir     # un numero NUEVO necesita nombre (fila de stage.xml)

Parte de tools/editor_mapas/salida/MAP<numero>.mpc ("Exportar .mpc" en el editor). Pasos, en orden:

  1. copia el mapa a tools/mapas_propios/map<n>.mpc (lo que va a git) y a parches/extras/map
  2. actualiza la colision del servidor (plantillas/transitable.bin)
  3. el 900 (Dark Cavern): repara la plantilla de monstruos (sellos, sprites que se ven, -30% de vida, jefe)
  4. pasa los eventos del mapa al servidor (plantillas/eventos.json, solo ese mapa)
  5. si el numero es nuevo, anade su fila a stage.xml; rehace el parche y los paquetes del launcher
  6. pruebas (las del 900; para otros numeros solo las de eventos)
  7. con --subir: sube al VPS la plantilla del mapa, colision, eventos, parche y paquetes, reinicia angels.service
     y compara los hashes

AVISOS que da antes de empezar:
  * si el mapa original sale de data1.pak, el cliente prefiere ese y NO vera el tuyo (paso con el 46): usa un numero nuevo.
  * si el mapa tiene plantilla de monstruos pero no esta en login.PLANTILLAS_POR_STAGE, el servidor no la usa.

El commit en git NO lo hace. Si hay mas de una cosa nueva que subir al VPS (codigo), pidemelo.
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

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
VPS = os.environ.get('AO_VPS', 'root@77.42.52.122')
VPS_DIR = os.environ.get('AO_VPS_DIR', '/opt/angels')
SALIDA = RAIZ / 'tools' / 'editor_mapas' / 'salida'


def paso(n, texto):
    print('\n[%s] %s' % (n, texto), flush=True)


def correr(args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run(args, cwd=RAIZ, env=e)
    if r.returncode:
        raise SystemExit('FALLO: %s (codigo %d)' % (' '.join(map(str, args)), r.returncode))


def codigo(texto, *args, env=None):
    """Un trozo de python en un proceso aparte con sys.argv = args (server/ y tools/ tienen cada uno un transitable.py)."""
    correr([PY, '-c', texto] + [str(x) for x in args], env=env)


def exportado(n):
    for f in SALIDA.glob('*.mpc'):
        if f.stem.lower() == 'map%d' % n:
            return f
    return None


def plantilla_de(n):
    """Nombre del json de monstruos del mapa (server/plantillas/<x>.json) o None."""
    sys.path.insert(0, str(RAIZ / 'server'))
    import login
    import app
    return {**login.PLANTILLAS_POR_STAGE, **app.MAPAS_APARTE}.get(n)


def avisos(n):
    sys.path.insert(0, str(RAIZ / 'server'))
    import cliente_local
    ruta = pathlib.Path(cliente_local.ruta_cliente())
    origen = cliente_local.indice_paks(ruta).get('MAP' + chr(92) + 'MAP%03d.MPC' % n)
    if origen is not None and origen.name.lower() == 'data1.pak':
        print('  AVISO: el mapa %d original sale de data1.pak y el cliente prefiere ese al del parche: NO se vera tu mapa. '
              'Usa un numero nuevo (el 900 sirve de ejemplo).' % n)
    elif origen is None or origen.name.lower() == 'update28.pak':      # update28.pak es el pack del editor, no del juego
        print('  mapa nuevo (el cliente no trae un map%03d.mpc): hace falta su fila en stage.xml' % n)
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('numero', type=int, help='numero del mapa (stage), el de map<N>.mpc')
    ap.add_argument('--subir', action='store_true', help='sube al VPS y lo reinicia')
    ap.add_argument('--nombre', help='nombre del mapa si el numero es nuevo (va en stage.xml)')
    ap.add_argument('--pak', default=os.environ.get('AO_PARCHE_PAK_LAUNCHER', 'update28'),
                    help='pak donde el launcher instala el parche (por defecto update28)')
    ap.add_argument('--sin-pruebas', action='store_true')
    a = ap.parse_args()
    n = a.numero
    guardado = RAIZ / 'tools' / 'mapas_propios' / ('map%d.mpc' % n)
    extras = RAIZ / 'parches' / 'extras' / 'map' / ('map%d.mpc' % n)

    paso(0, 'comprobar el mapa %d' % n)
    origen = exportado(n)
    if origen is None:
        raise SystemExit('No hay MAP%d.mpc en %s: exporta el mapa %d desde el editor ("Exportar .mpc").' % (n, SALIDA, n))
    nuevo = avisos(n)
    plantilla = plantilla_de(n)
    if plantilla is None:
        print('  sin plantilla de monstruos registrada (login.PLANTILLAS_POR_STAGE[%d]): el servidor no pone bichos ahi' % n)
    elif not (RAIZ / 'server' / 'plantillas' / plantilla).exists():
        raise SystemExit('login.PLANTILLAS_POR_STAGE[%d] apunta a %s, que no existe.' % (n, plantilla))
    else:
        print('  plantilla de monstruos: %s' % plantilla)
    fila_hecha = False
    xml_extras = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml'
    if xml_extras.exists():
        fila_hecha = ('編號="%d"' % n) in xml_extras.read_text(encoding='utf-8')
    if nuevo and not a.nombre and not fila_hecha:
        raise SystemExit('El %d es un numero nuevo: dime su nombre con --nombre "Nombre del mapa".' % n)

    paso(1, 'copiar el mapa exportado')
    guardado.parent.mkdir(parents=True, exist_ok=True)
    extras.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origen, guardado)
    shutil.copyfile(origen, extras)
    print('  %s (%d bytes)' % (guardado.relative_to(RAIZ), guardado.stat().st_size))

    paso(2, 'colision del servidor (transitable.bin)')
    codigo("import sys,pathlib; sys.path.insert(0,'server'); sys.path.insert(0,'tools'); import instalar_mapa as im;"
           "n=int(sys.argv[1]); d=pathlib.Path(sys.argv[2]).read_bytes(); print('  mapa', im.comprobar_mpc(d)); im.actualizar_transitable(n,d)",
           n, guardado)

    paso(3, 'plantilla de monstruos')
    if n == 900:
        correr([PY, 'tools/reparar_instancia_oscura.py'])
    else:
        print('  nada que reparar (solo el 900 tiene reparador)')

    paso(4, 'eventos del mapa -> servidor')
    codigo("import sys,json,pathlib; sys.path.insert(0,'server'); sys.path.insert(0,'tools'); import propagar_eventos as pe;"
           "n=int(sys.argv[1]); d=pe._del_mapa(n,pathlib.Path(sys.argv[2])); p=pathlib.Path('server/plantillas/eventos.json');"
           "j=json.loads(p.read_text(encoding='utf-8'));"
           "hay=any(d[k] for k in ('disparadores','objetos','generadores','monstruos','temporizadores'));"
           "(j['stages'].__setitem__(str(n),d) if hay else j['stages'].pop(str(n),None));"
           "p.write_text(json.dumps(j,ensure_ascii=False,separators=(',',':')),encoding='utf-8');"
           "print('  eventos del mapa',n,':',len(d['disparadores']),'disparadores,',len(d['objetos']),'objetos enlazados')",
           n, guardado)

    paso(5, 'stage.xml, parche y paquetes del launcher')
    if nuevo and (a.nombre or not fila_hecha):
        registrar_stage(n, a.nombre)
    elif nuevo:
        print('  stage.xml ya trae la fila del mapa %d' % n)
    else:
        print('  el mapa ya existe en el cliente: stage.xml no cambia')
    codigo("import sys; sys.path.insert(0,'server'); import parche; e=parche.generar(); print('  parche', e['version'], e['bytes'], 'bytes')")
    correr([PY, '-I', 'tools/generar_paquetes_launcher.py'],
           env={'AO_PARCHE_PAK_LAUNCHER': a.pak, 'AO_PARCHE_HOST': VPS.split('@')[-1]})

    if not a.sin_pruebas:
        paso(6, 'pruebas')
        pruebas = ['tools/test_eventos.py'] + (['tools/test_instancia_oscura.py'] if n == 900 else [])
        correr([PY, '-m', 'pytest'] + pruebas + ['-q', '-p', 'no:cacheprovider'])

    if a.subir:
        subir(n, plantilla)

    print('\nListo. %s' % ('Subido al VPS.' if a.subir else 'Falta subirlo: vuelve a correr con --subir (o pidemelo).'))
    print('Despues: abre el launcher del cliente del VPS y actualiza.')


def registrar_stage(n, nombre):
    """Anade a parches/extras/setting/eng/stage.xml la fila del mapa nuevo (oscuro y sin flags, como la del 46)."""
    sys.path.insert(0, str(RAIZ / 'server'))
    import parche
    bs = chr(92)
    extras = RAIZ / 'parches' / 'extras' / 'setting' / 'eng'
    destino = extras / 'stage.xml'
    if destino.exists():
        base = destino.read_text(encoding='utf-8')
    else:
        raw = (RAIZ / 'parches' / 'update27.pak').read_bytes()
        base = {k: parche._leer(raw, e) for k, e in parche._directorio(raw).items()}['SETTING' + bs + 'ENG' + bs + 'STAGE.XML'].decode('utf-8')
    if '編號="%d"' % n in base:
        print('  stage.xml ya tiene el mapa %d' % n)
        return
    fila = ('    <場景 編號="%d" 名稱="%s" 地圖檔="map' + bs + 'map%03d.mpc" 筆刷檔="brush' + bs + 'brush.gic" '
            '雷達圖="smap' + bs + '046" 配樂檔1="music' + bs + '11.ogg" 亮度="160" 天氣="0" 不懲罰="是" />\r\n') % (n, nombre, n)
    fin = base.rindex('<DEFINE')
    base = base[:fin].rstrip(' ') + fila + '    ' + base[fin:]
    extras.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(base.encode('utf-8'))
    print('  fila del stage %d (%s) en stage.xml' % (n, nombre))


def subir(n, plantilla):
    paso(7, 'subir al VPS (%s:%s)' % (VPS, VPS_DIR))
    archivos = ['server/plantillas/transitable.bin', 'server/plantillas/eventos.json', 'parches/update27.pak', 'parches/version.json',
                'parches/extras/map/map%d.mpc' % n]
    if plantilla:
        archivos.append('server/plantillas/%s' % plantilla)
    if (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml').exists():
        archivos.append('parches/extras/setting/eng/stage.xml')
    tgz = RAIZ / 'subida_mapa.tgz'
    try:
        correr(['tar', 'czf', tgz.name] + archivos + ['parches/launcher'])
        correr(['scp', '-q', '-o', 'BatchMode=yes', tgz.name, '%s:/tmp/subida_mapa.tgz' % VPS])
        correr(['ssh', '-o', 'BatchMode=yes', VPS,
                'cd %s && rm -rf parches/launcher.anterior && mv parches/launcher parches/launcher.anterior && '
                'tar xzf /tmp/subida_mapa.tgz && chown -R angels:angels parches server/plantillas && rm -f /tmp/subida_mapa.tgz && '
                'systemctl restart angels.service && sleep 5 && systemctl is-active angels.service' % VPS_DIR])
    finally:
        if tgz.exists():
            tgz.unlink()
    local = {f: hashlib.md5((RAIZ / f).read_bytes()).hexdigest() for f in archivos}
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', VPS, 'cd %s && md5sum %s' % (VPS_DIR, ' '.join(archivos))],
                       cwd=RAIZ, capture_output=True, text=True)
    remoto = {l.split()[1]: l.split()[0] for l in r.stdout.splitlines() if l.strip()}
    mal = [f for f in archivos if remoto.get(f) != local[f]]
    print('  hashes iguales: %d de %d' % (len(archivos) - len(mal), len(archivos)))
    if mal:
        raise SystemExit('NO coinciden: %s' % mal)


if __name__ == '__main__':
    main()
