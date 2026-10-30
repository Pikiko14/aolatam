"""NPC y monstruos de Angels Online para el servidor: catalogo del cliente, miniaturas y lectura/escritura de spawns.

Lo usa editor_mapas.py (init(modulo) le pasa el modulo para compartir INDEX, datos, read_spr...).

- Catalogo: setting/eng/monster.xml y npc.xml del cliente (los .pak). Solo entradas con sprite (圖號).
- Miniatura: primer cuadro de shape/(mon|npc)/XXX/<sprite>_wait.spr.
- Spawns: server/plantillas/<mapa>.json, clave "spawns" (el mismo formato que usa el servidor y tools/poblar_mapa.py).
  El numero del .mpc es el stage del servidor (map112.mpc -> stage 112).
"""
import glob
import json
import os
import re
import shutil

E = None                        # editor_mapas
_cat = []
_fotos = {}
_idx_wait = None


def init(modulo):
    global E
    E = modulo


# Tipos de monstruo en las plantillas: (elite, jefe, hp_mult, atk_mult) que pone el editor al
# cambiarlo. Normal no lleva multiplicadores (en Dark Cavern tools/reparar_instancia_oscura.py le
# pone el 0,7 de la instancia).
TIPOS = {'normal': (False, False, None, None), 'elite': (True, False, 2.0, 1.15), 'jefe': (False, True, 10.0, 1.3)}
STATS = ('hp', 'atk', 'def', 'matk', 'mdef', 'exp')


def _raiz():
    return os.path.dirname(os.path.dirname(os.path.abspath(E.PLANTILLAS)))


def _stats_del_cliente():
    """{npc_type: {hp, atk, def, matk, mdef, exp}} de corpus/content.db (lo mismo que usa el servidor)."""
    import sqlite3
    db = os.path.join(_raiz(), 'corpus', 'content.db')
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(db)
    try:
        out = {}
        for i, hp, atk, df, matk, mdef, exp in con.execute(
                "select id, hp, atk_avg, def, matk, mdef, exp_value from monster where id glob '[0-9]*'"):
            num = lambda x: int(float(x)) if str(x or '').replace('.', '', 1).isdigit() else 0
            out[int(i)] = dict(hp=num(hp), atk=num(atk), **{'def': num(df)}, matk=num(matk), mdef=num(mdef), exp=num(exp))
        return out
    finally:
        con.close()


def _propios():
    """Los monstruos propios del servidor (server/plantillas/monstruos_propios.json)."""
    f = os.path.join(E.PLANTILLAS, 'monstruos_propios.json')
    if not os.path.exists(f):
        return []
    mobs = json.load(open(f, encoding='utf-8')).get('mobs', {})
    return [dict(id=int(m['base']), nombre=m['nombre'], sprite=int(m['sprite']), nivel=int(m['nivel']),
                 monstruo=True, fuente='propio', propio=k, **{s: int(m[s]) for s in STATS})
            for k, m in sorted(mobs.items(), key=lambda kv: kv[1]['nivel'])]


def catalogo():
    if _cat:
        return _cat
    stats = _stats_del_cliente()
    for arch, tipo in (('setting/eng/monster.xml', 'monstruo'), ('setting/eng/npc.xml', 'npc')):
        if arch not in E.INDEX:
            continue
        t = E.datos(arch).decode('utf-8', errors='replace')
        for m in re.finditer(r'<npc([^>]*?)/>', t):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', m.group(1)))
            if not (a.get('編號', '').isdigit() and a.get('圖號', '').isdigit() and a.get('名稱')):
                continue
            mob = tipo == 'monstruo' and a.get('陣營') == '怪物陣營'
            c = dict(id=int(a['編號']), nombre=a['名稱'], sprite=int(a['圖號']),
                     nivel=int(a['等級']) if a.get('等級', '').isdigit() else 0,
                     monstruo=bool(mob), fuente=tipo)
            if mob:
                c.update(stats.get(c['id'], {}))
            _cat.append(c)
    _cat.sort(key=lambda c: (not c['monstruo'], c['nivel'], c['id']))
    # Los propios primero: son los que se ponen a mano en las instancias propias.
    _cat[:0] = _propios()
    return _cat


_items = []


def items():
    """[{id, nombre, nivel, clase}] de las tablas item..item9 de corpus/content.db, para los
    selectores del creador de eventos (en vez de escribir el numero a mano)."""
    if _items:
        return _items
    import sqlite3
    db = os.path.join(_raiz(), 'corpus', 'content.db')
    if not os.path.exists(db):
        return _items
    con = sqlite3.connect(db)
    try:
        for t in ['item'] + ['item%d' % i for i in range(2, 10)]:
            try:
                filas = con.execute('select id, 基本名稱, 物品等級, 物品類別 from %s' % t).fetchall()
            except sqlite3.Error:
                continue
            vistos = {x['id'] for x in _items}
            for i, nom, nv, cl in filas:
                # El mismo id sale en varias tablas (lo repiten los .pak): vale el primero.
                if str(i).isdigit() and nom and int(i) not in vistos:
                    vistos.add(int(i))
                    _items.append(dict(id=int(i), nombre=nom, nivel=int(nv) if str(nv or '').isdigit() else 0,
                                       clase=cl or ''))
    finally:
        con.close()
    _items.sort(key=lambda x: x['id'])
    return _items


def buscar_items(q, limite=60):
    q = (q or '').strip().lower()
    if not q:
        return []
    if q.isdigit():
        return [x for x in items() if str(x['id']).startswith(q)][:limite]
    return [x for x in items() if q in x['nombre'].lower()][:limite]


def nombres_items(ids):
    por_id = {x['id']: x['nombre'] for x in items()}
    return {str(i): por_id.get(int(i), '') for i in ids if str(i).isdigit()}


# ------------------------------------------------------------- reglas del servidor (matar X)
def _archivo_reglas():
    return os.path.join(E.PLANTILLAS, 'eventos_propios.json')


def _validar_regla(r):
    import importlib.util
    f = os.path.join(_raiz(), 'server', 'eventos_propios.py')
    spec = importlib.util.spec_from_file_location('eventos_propios_editor', f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.validar(r)


def reglas():
    f = _archivo_reglas()
    if not os.path.exists(f):
        return dict(reglas=[])
    return json.load(open(f, encoding='utf-8'))


def guardar_reglas(lista):
    """Valida y escribe server/plantillas/eventos_propios.json (con .bak). Devuelve los errores
    por regla sin escribir si alguna esta mal."""
    errores = {}
    ids = set()
    for i, r in enumerate(lista):
        mal = _validar_regla(r)
        if r.get('id') in ids:
            mal.append('id repetido')
        ids.add(r.get('id'))
        if mal:
            errores[r.get('id') or '#%d' % (i + 1)] = mal
    if errores:
        return dict(ok=False, errores=errores)
    f = _archivo_reglas()
    j = reglas() if os.path.exists(f) else {}
    if os.path.exists(f):
        shutil.copyfile(f, f + '.bak')
    j.setdefault('_nota', 'Reglas "matar X monstruos" del servidor; ver server/eventos_propios.py. '
                          'Se editan con tools/editor_mapas (pestana Eventos).')
    j['reglas'] = lista
    tmp = f + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False, indent=1) + '\n')
    os.replace(tmp, f)
    return dict(ok=True, total=len(lista))


def foto(sid):
    """PNG de un sprite de NPC o monstruo, o None."""
    global _idx_wait
    if _idx_wait is None:
        _idx_wait = {}
        for k in E.INDEX:
            m = re.match(r'shape/(?:mon|npc)/[^/]+/(\d+)_wait\.spr$', k)
            if m:
                _idx_wait[int(m.group(1))] = k
    if sid in _fotos:
        return _fotos[sid]
    k = _idx_wait.get(sid)
    if not k:
        # Variantes: el sprite comparte modelo con otro (40112 -> carpeta npc/n002 -> 40002_wait.spr). Se busca por la carpeta de la definicion.
        d = E.DEFS.get(sid)
        if d:
            carpeta = 'shape/%s/' % d['directorio'].replace(chr(92), '/').strip('/')
            k = next((c for c in E.INDEX if c.startswith(carpeta) and c.endswith('_wait.spr')), None)
    res = None
    if k:
        sp = E.read_spr(E.datos(k))
        if sp and sp[1]:
            r = E.decode_shp(sp[1][0][1], sp[0])
            if r:
                res = E.png(r[0])
    _fotos[sid] = res
    return res


def stage_de_mapa(nombre):
    m = re.fullmatch(r'(?i)map0*(\d+)', nombre or '')
    return int(m.group(1)) if m else None


def archivo_plantilla(stage):
    """(ruta, existe): la plantilla que declara "stage": N; si no hay, la ruta que tendria una nueva."""
    for f in sorted(glob.glob(os.path.join(E.PLANTILLAS, '*.json'))):
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(j, dict) and j.get('stage') == stage and 'spawns' in j:
            return f, True
    nom = re.sub(r'[^a-z0-9]+', '_', E.stage_nombres().get(stage, 'mapa_%d' % stage).lower()).strip('_') or 'mapa_%d' % stage
    return os.path.join(E.PLANTILLAS, nom + '.json'), False


def spawns(mapa):
    stage = stage_de_mapa(mapa)
    if stage is None:
        return dict(stage=None, archivo=None, existe=False, spawns=[])
    f, existe = archivo_plantilla(stage)
    sp = json.load(open(f, encoding='utf-8')).get('spawns', []) if existe else []
    return dict(stage=stage, archivo=os.path.basename(f), existe=existe, spawns=sp)


def tipo_de(e):
    return 'jefe' if e.get('jefe') else 'elite' if e.get('elite') else 'normal'


def poner_tipo(e, tipo):
    """Cambia un spawn a normal / elite / jefe con los multiplicadores de TIPOS. Lo demas
    (sello, propio, zona...) se queda."""
    elite, jefe, hp, atk = TIPOS[tipo]
    for k, v in (('elite', elite), ('jefe', jefe), ('hp_mult', hp), ('atk_mult', atk)):
        if v:
            e[k] = v
        else:
            e.pop(k, None)


def exportar(mapa, nuevos):
    """Escribe los spawns editados en la plantilla del servidor.

    Las entidades que ya estaban conservan todos sus campos; solo cambian tile y direccion.
    Las nuevas reciben un entity_id libre (900001 en adelante). Las que faltan se borran.
    Copia .bak antes de escribir."""
    stage = stage_de_mapa(mapa)
    if stage is None:
        raise ValueError('el mapa debe llamarse mapNNN para saber a que stage del servidor pertenece')
    f, existe = archivo_plantilla(stage)
    if existe:
        j = json.load(open(f, encoding='utf-8'))
        shutil.copyfile(f, f + '.bak')
    else:
        j = dict(_nota='%s (stage %d), creada con tools/editor_mapas.' % (E.stage_nombres().get(stage, 'mapa'), stage),
                 stage=stage, spawns=[], recursos=[])
    viejos = {int(e['entity_id']): e for e in j.get('spawns', [])}
    usados = set(viejos)
    final, nuevos_n = [], 0
    for e in nuevos:
        tile = [int(e['tile'][0]), int(e['tile'][1])]
        eid = e.get('entity_id')
        if eid is not None and int(eid) in viejos:
            v = dict(viejos[int(eid)])
            v.update(tile=tile, direccion=int(e.get('direccion', v.get('direccion', 0))))
            if v.get('monstruo') and e.get('tipo') in TIPOS and e['tipo'] != tipo_de(v):
                poner_tipo(v, e['tipo'])
            final.append(v)
            continue
        eid = max(usados | {900000}) + 1
        usados.add(eid)
        nuevos_n += 1
        mob = bool(e.get('monstruo'))
        d = dict(entity_id=eid, nombre=e['nombre'], npc_type=int(e['npc_type']), sprite=int(e['sprite']),
                 klass=1 if mob else 200, monstruo=mob, tile=tile, direccion=int(e.get('direccion', 0)), visible=0)
        if mob:
            d['nivel'] = int(e.get('nivel') or 1)
            if e.get('propio'):
                d['propio'] = str(e['propio'])
            if e.get('tipo') in TIPOS and e['tipo'] != 'normal':
                poner_tipo(d, e['tipo'])
        final.append(d)
    quedan = {int(e['entity_id']) for e in final}
    j['spawns'] = final
    os.makedirs(E.PLANTILLAS, exist_ok=True)
    tmp = f + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False, indent=1) + '\n')
    os.replace(tmp, f)
    return dict(ok=True, stage=stage, archivo=os.path.basename(f), nuevos=nuevos_n,
                borrados=len(set(viejos) - quedan), total=len(final), creada=not existe)
