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


def catalogo():
    if _cat:
        return _cat
    for arch, tipo in (('setting/eng/monster.xml', 'monstruo'), ('setting/eng/npc.xml', 'npc')):
        if arch not in E.INDEX:
            continue
        t = E.datos(arch).decode('utf-8', errors='replace')
        for m in re.finditer(r'<npc([^>]*?)/>', t):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', m.group(1)))
            if not (a.get('編號', '').isdigit() and a.get('圖號', '').isdigit() and a.get('名稱')):
                continue
            mob = tipo == 'monstruo' and a.get('陣營') == '怪物陣營'
            _cat.append(dict(id=int(a['編號']), nombre=a['名稱'], sprite=int(a['圖號']),
                             nivel=int(a['等級']) if a.get('等級', '').isdigit() else 0,
                             monstruo=bool(mob), fuente=tipo))
    _cat.sort(key=lambda c: (not c['monstruo'], c['nivel'], c['id']))
    return _cat


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
        final.append(d)
    quedan = {int(e['entity_id']) for e in final}
    j['spawns'] = final
    os.makedirs(E.PLANTILLAS, exist_ok=True)
    tmp = f + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False, indent=1) + '\n')
    os.replace(tmp, f)
    return dict(ok=True, stage=stage, archivo=os.path.basename(f), nuevos=nuevos_n,
                borrados=len(set(viejos) - quedan), total=len(final), creada=not existe)
