"""Instala un mapa exportado del editor de mapas: lo deja todo listo, lo guarda en git y lo sube al VPS. Todo, por su NUMERO.

    python tools/subir_mapa.py 900                          # hace TODO: prepara, prueba, commit + push y sube al VPS
    python tools/subir_mapa.py 900 --solo-local             # solo prepara y prueba en tu PC (no toca git ni el VPS)
    python tools/subir_mapa.py 900 --sin-git                # prepara, prueba y sube, sin commit
    python tools/subir_mapa.py 1200 --nombre "Mi Mapa"      # un numero NUEVO necesita nombre (fila de stage.xml)
    python tools/subir_mapa.py 1200 --nombre "Mi Mapa" --instancia    # ademas, una instancia: los bichos no reaparecen

Parte de tools/editor_mapas/salida/MAP<numero>.mpc ("Exportar .mpc" en el editor). Pasos, en orden:

  0. comprueba el mapa: avisa si su original sale de data1.pak (el cliente prefiere ese y no veria el tuyo),
     busca su plantilla de monstruos y avisa de los que el cliente no sabe dibujar (serian invisibles)
  1. copia el mapa a tools/mapas_propios/map<n>.mpc (lo que va a git) y a parches/extras/map
  2. actualiza la colision del servidor (plantillas/transitable.bin)
  3. registra la plantilla en login.PLANTILLAS_POR_STAGE (y en instancias.json con --instancia) si faltaba;
     el 900 ademas pasa por tools/reparar_instancia_oscura.py (sellos, sprites que se ven, -30% de vida, jefe)
  4. pasa los eventos del mapa al servidor (plantillas/eventos.json, solo ese mapa)
  5. si el numero es nuevo, anade su fila a stage.xml; rehace el parche y los paquetes del launcher
  6. pruebas
  7. commit + push (solo los archivos de este mapa; nunca lo demas que tengas cambiado)
  8. sube al VPS lo que cambio (plantilla, colision, eventos, parche, paquetes y, si se registro, login.py e instancias.json),
     reinicia angels.service y compara los hashes
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
PLANTILLAS = RAIZ / 'server' / 'plantillas'


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


def plantilla_registrada(n):
    sys.path.insert(0, str(RAIZ / 'server'))
    import login
    import app
    return {**login.PLANTILLAS_POR_STAGE, **app.MAPAS_APARTE}.get(n)


def plantilla_candidata(n):
    """El json de monstruos que el editor dejo para ese mapa: el mas reciente con 'stage' == n (sin contar los .bak)."""
    c = []
    for f in PLANTILLAS.glob('*.json'):
        try:
            j = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(j, dict) and j.get('stage') == n and isinstance(j.get('spawns'), list):
            c.append(f)
    return max(c, key=lambda f: f.stat().st_mtime).name if c else None


def sprites_que_faltan(plantilla):
    """[(nombre, sprite)] de los monstruos de la plantilla cuyo sprite NO trae el cliente (existirian pero no se verian)."""
    sys.path.insert(0, str(RAIZ / 'server'))
    import cliente_local
    ruta = pathlib.Path(cliente_local.ruta_cliente())
    por = {}
    for nombre in cliente_local.indice_paks(ruta):
        m = re.fullmatch(r'SHAPE[\\/]MON[\\/][^\\/]+[\\/](\d+)_(WAIT|RUN|ATT|HURT|DEAD)\.SPR', nombre.upper())
        if m:
            por.setdefault(int(m.group(1)), set()).add(m.group(2))
    visibles = {s for s, v in por.items() if {'WAIT', 'RUN', 'ATT', 'HURT', 'DEAD'} <= v}
    j = json.loads((PLANTILLAS / plantilla).read_text(encoding='utf-8'))
    falta = {}
    for e in j['spawns']:
        s = int(e.get('sprite') or 0)
        if e.get('klass') == 1 and s and s not in visibles:
            falta.setdefault((e['nombre'], s), 0)
            falta[(e['nombre'], s)] += 1
    return [(k[0], k[1], c) for k, c in falta.items()]


def es_nuevo(n):
    sys.path.insert(0, str(RAIZ / 'server'))
    import cliente_local
    ruta = pathlib.Path(cliente_local.ruta_cliente())
    origen = cliente_local.indice_paks(ruta).get('MAP' + chr(92) + 'MAP%03d.MPC' % n)
    if origen is not None and origen.name.lower() == 'data1.pak':
        print('  AVISO: el mapa %d original sale de data1.pak y el cliente prefiere ese al del parche: NO se vera tu mapa. '
              'Usa un numero nuevo (el 900 sirve de ejemplo).' % n)
    if origen is None or origen.name.lower() == 'update28.pak':      # update28.pak es el pack del editor, no del juego
        print('  mapa nuevo (el cliente no trae un map%03d.mpc)' % n)
        return True
    return False


def registrar_plantilla(n, json_name, nombre, instancia):
    """login.PLANTILLAS_POR_STAGE[n] (y instancias.json con --instancia). Devuelve los archivos que cambio."""
    cambiados = []
    p = RAIZ / 'server' / 'login.py'
    s = p.read_text(encoding='utf-8')
    if json_name and not re.search(r'^PLANTILLAS_POR_STAGE\[%d\]' % n, s, re.M):
        ult = list(re.finditer(r'^PLANTILLAS_POR_STAGE\[\d+\] = .*$', s, re.M))[-1]
        linea = "PLANTILLAS_POR_STAGE[%d] = '%s'      # %s (tools/subir_mapa.py)" % (n, json_name, nombre or 'mapa propio')
        s = s[:ult.end()] + '\n' + linea + s[ult.end():]
        p.write_text(s, encoding='utf-8')
        cambiados.append('server/login.py')
        print('  registrada en login.py: %s' % linea)
    if instancia:
        pi = PLANTILLAS / 'instancias.json'
        d = json.loads(pi.read_text(encoding='utf-8'))
        if str(n) not in d['mapas']:
            d['mapas'][str(n)] = {'nombre': nombre or 'mapa %d' % n, 'copias': 1, 'dinamica': True, 'asignacion': '',
                                  'tope_personas': 0, 'sin_cambio_de_canal': False}
            pi.write_text(json.dumps(d, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
            cambiados.append('server/plantillas/instancias.json')
            print('  registrada como instancia en instancias.json')
    return cambiados


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


def hacer_commit(n, nombre, archivos):
    existentes = [f for f in archivos if (RAIZ / f).exists()]
    correr(['git', 'add'] + existentes)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=RAIZ).returncode == 0:
        print('  nada nuevo que guardar en git')
        return
    msg = 'Mapa %d%s: instalado con tools/subir_mapa.py' % (n, ' (%s)' % nombre if nombre else '')
    correr(['git', 'commit', '-q', '-m', msg] + ['--'] + existentes)
    rama = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    correr(['git', 'push', '-q', 'origin', rama])
    print('  commit + push (%s): %s' % (rama, msg))


def subir(archivos):
    paso(8, 'subir al VPS (%s:%s)' % (VPS, VPS_DIR))
    tgz = RAIZ / 'subida_mapa.tgz'
    try:
        correr(['tar', 'czf', tgz.name] + archivos + ['parches/launcher'])
        correr(['scp', '-q', '-o', 'BatchMode=yes', tgz.name, '%s:/tmp/subida_mapa.tgz' % VPS])
        correr(['ssh', '-o', 'BatchMode=yes', VPS,
                'cd %s && rm -rf parches/launcher.anterior && mv parches/launcher parches/launcher.anterior && '
                'tar xzf /tmp/subida_mapa.tgz && chown -R angels:angels parches server/plantillas server/login.py && rm -f /tmp/subida_mapa.tgz && '
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('numero', type=int, help='numero del mapa (stage), el de map<N>.mpc')
    ap.add_argument('--nombre', help='nombre del mapa (obligatorio si el numero es nuevo: va en stage.xml)')
    ap.add_argument('--instancia', action='store_true', help='registrarlo como instancia (los bichos no reaparecen)')
    ap.add_argument('--solo-local', action='store_true', help='solo prepara y prueba: ni git ni VPS')
    ap.add_argument('--sin-git', action='store_true', help='no hace commit ni push')
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
    nuevo = es_nuevo(n)
    plantilla = plantilla_registrada(n)
    registrada = plantilla is not None
    if plantilla is None:
        plantilla = plantilla_candidata(n)
        if plantilla:
            print('  plantilla de monstruos sin registrar: %s (se registra en el paso 3)' % plantilla)
        else:
            print('  sin plantilla de monstruos: el servidor no pone bichos ahi (colocalos en la pestana NPC/Monstruos AO)')
    else:
        print('  plantilla de monstruos: %s' % plantilla)
    if plantilla:
        for nom, spr, cant in sprites_que_faltan(plantilla):
            print('  AVISO: %d x %s (sprite %d) no esta en el cliente: serian INVISIBLES' % (cant, nom, spr))
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
    codigo_cambiado = []
    if plantilla and not registrada:
        codigo_cambiado = registrar_plantilla(n, plantilla, a.nombre, a.instancia)
    elif a.instancia:
        codigo_cambiado = registrar_plantilla(n, plantilla or '', a.nombre, True)
    if n == 900:
        correr([PY, 'tools/reparar_instancia_oscura.py'])
    elif not codigo_cambiado:
        print('  nada que hacer')

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

    archivos_git = ['tools/mapas_propios/map%d.mpc' % n, 'server/plantillas/transitable.bin', 'server/plantillas/eventos.json'] + codigo_cambiado
    archivos_vps = ['server/plantillas/transitable.bin', 'server/plantillas/eventos.json', 'parches/update27.pak', 'parches/version.json',
                    'parches/extras/map/map%d.mpc' % n] + codigo_cambiado
    if plantilla:
        archivos_git.append('server/plantillas/%s' % plantilla)
        archivos_vps.append('server/plantillas/%s' % plantilla)
    if xml_extras.exists():
        archivos_vps.append('parches/extras/setting/eng/stage.xml')

    if a.solo_local:
        print('\nListo en local. Para guardarlo en git y subirlo al VPS: python tools/subir_mapa.py %d' % n)
        return
    if not a.sin_git:
        paso(7, 'guardar en git')
        hacer_commit(n, a.nombre, [f for f in archivos_git if f not in ('server/plantillas/dark_cavern.json.bak',)])
    subir(archivos_vps)
    print('\nListo: mapa %d en el VPS. Ahora abre el launcher del cliente del VPS y actualiza.' % n)


if __name__ == '__main__':
    main()
