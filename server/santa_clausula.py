"""Santa Clausula, jefe troll del evento de Navidad (05/11/2026).

Un monstruo nuevo: el Wham Ogre del juego (sprite 110668) recoloreado con piel de troll, taparrabos de Santa, garrote
de baston de caramelo, el gorro de Navidad del juego y barba blanca (los .spr salen de tools/santa_clausula_datos.py).

  monster 23901, sprite 119001 (npc.obd: carpeta \\mon\\M9001\\)
  nivel 60, vida 500.000, ataque 450 / defensa 880, ataque magico 600 / defensa magica 450, critico 20 %
  habilidades: Cross Chop I (605, a uno) y Revolving Swords I (5706, en area); el dano sale de sus stats
  inmune a aturdir, congelar, inmovilizar, ralentizar y encantar
  evento: cada 24 h en un mapa al azar junto a las ciudades, con cartel arriba; se va a los 60 minutos
  botin: a cada jugador que le hizo dano, tirando sus propias probabilidades
"""
import logging
import pathlib
import sqlite3

log = logging.getLogger('santa_clausula')

NPC_TYPE = 23901
SPRITE = 119001
CARPETA = 'M9001'
NOMBRE = 'Santa Clausula'

# Las columnas de content.db (tabla monster) y su equivalente en monster.xml del cliente.
STATS = {
    'name': NOMBRE, 'sprite_id': str(SPRITE), 'level': '60', 'element': '人型', 'faction': '怪物陣營',
    'hp': '500000', 'atk_avg': '450', 'atk_var': '45', 'def': '880', 'matk': '600', 'mdef': '450',
    'accuracy': '420', 'agility': '260', 'res_body': '50', 'res_mind': '50',
    'move_speed': '80', 'move_range': '8', 'atk_speed': '70', 'atk_range': '1', 'crit_rate': '20',
    'exp_value': '25000', 'snd_idle': 'M01801', 'snd_atk': 'M01802', 'snd_die': 'M01803',
    'drop_id': str(NPC_TYPE), 'dura_dmg': '2', '主動': '6', '王': '是', '追目標到死': '是',
    '攻擊法術1': '605', '攻擊法術2': '5706', '施展機率': '35',
    '免疫暈眩': '是', '免疫冰凍': '是', '免疫媚惑': '是', '免疫震退': '是', '免疫定身': '是',
    '免疫移動緩慢': '是', '免疫綑綁': '是', '免疫麻痺': '是',
}
# content.db -> atributo de monster.xml
A_XML = {
    'name': '名稱', 'sprite_id': '圖號', 'level': '等級', 'element': '系別', 'faction': '陣營', 'hp': 'HP',
    'atk_avg': '平均攻擊', 'atk_var': '攻擊變數', 'def': '防禦', 'matk': '魔攻', 'mdef': '魔防', 'accuracy': '精準',
    'agility': '靈敏', 'res_body': '體質抵抗', 'res_mind': '心靈抵抗', 'move_speed': '移動速度',
    'move_range': '移動範圍', 'atk_speed': '攻擊速度', 'atk_range': '攻擊範圍', 'crit_rate': '重擊機率',
    'exp_value': '經驗價值', 'snd_idle': '平時音效', 'snd_atk': '攻擊音效', 'snd_die': '陣亡音效',
    'drop_id': '掉寶編號', 'dura_dmg': '耐久破壞',
}

DB = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'


def fila_monster_xml() -> str:
    """La linea <npc .../> para setting/eng/monster.xml del cliente."""
    attrs = ['編號="%d"' % NPC_TYPE]
    for col, val in STATS.items():
        attrs.append('%s="%s"' % (A_XML.get(col, col), val))
    return '    <npc %s />' % ' '.join(attrs)


def bloque_npc_obd() -> str:
    """El [OBJECT] de setting/npc.obd: copia del Wham Ogre (110668) con su numero, carpeta y archivos."""
    s = SPRITE
    return '\r\n'.join((
        '[OBJECT]',
        'Name = %s - Santa Clausula' % CARPETA,
        'Sequence = %d' % s,
        'Space = 25, 80, 0',
        'Flags = SP_ATTRIB_DISTURB, SP_ATTRIB_HITTEST, SP_ATTRIB_SHADOW',
        'Process = SERV_CLASS_NPCOBJ',
        'Directory = \\mon\\%s\\' % CARPETA,
        'Sprite = Wait, w013*, #8, !SoundWait, w023*, w033*, w023*',
        'Sprite = Run, r013*, #7, r023*, r033*, r043*, r053*, r063*',
        'Sprite = Att, a013*, #6, !SoundAttack, a023*, a033*, a043*, !WeaponShoot, a043*, @SP_EVENT_ACT_WAIT, SCROVER',
        'Sprite = Cast, a013*, #6, a023*, a033*, a043*, a043*',
        'Sprite = Hurt, h013*, #4, h023*, h023*, @SP_EVENT_ACT_WAIT, SCROVER',
        'Sprite = Dead, d013*, #6, !SoundDie, d023*, d033*, d043*, d053*, d063*, SCROVER',
        'SpriteFile = Wait, %d_Wait.spr' % s,
        'SpriteFile = Run, %d_Run.spr' % s,
        'SpriteFile = Att, %d_Att.spr' % s,
        'SpriteFile = Cast, %d_Att.spr' % s,
        'SpriteFile = Hurt, %d_Hurt.spr' % s,
        'SpriteFile = Dead, %d_Dead.spr' % s,
        '', ''))


def asegurar_en_db(db: pathlib.Path = DB) -> bool:
    """Su fila en content.db (tabla monster), que es de donde el servidor saca los stats. Se llama al arrancar,
    antes de que combate cargue la tabla. True si la escribio o la actualizo."""
    if not db.exists():
        return False
    con = sqlite3.connect(db)
    try:
        cols = {c[1] for c in con.execute('pragma table_info(monster)')}
        datos = {k: v for k, v in STATS.items() if k in cols}
        datos['id'] = str(NPC_TYPE)
        if '_pak' in cols:
            datos['_pak'] = 'santa_clausula'
        actual = con.execute('select * from monster where id=?', (str(NPC_TYPE),)).fetchone()
        if actual:
            nombres = [c[1] for c in con.execute('pragma table_info(monster)')]
            if all(str(dict(zip(nombres, actual)).get(k) or '') == str(v) for k, v in datos.items()):
                return False
            con.execute('delete from monster where id=?', (str(NPC_TYPE),))
        con.execute('insert into monster (%s) values (%s)' % (
            ','.join('"%s"' % k for k in datos), ','.join('?' * len(datos))), tuple(datos.values()))
        con.commit()
        log.info('Santa Clausula (%d) registrado en content.db', NPC_TYPE)
        return True
    finally:
        con.close()


# ------------------------------------------------------------------ habilidades
# Dos de la rama Sword, de las primeras para que el efecto sea el suyo: Cross Chop I a uno y Revolving Swords I
# alrededor (radio 5). El dano no sale del nivel de la habilidad sino de sus stats: asi no pega como una habilidad
# de nivel alto ("que pueda usar 2 poderes de sword, bajales el ataque si son lvl alto, 1 aoe preferiblemente").
HAB_UNO = 605             # Cross Chop I
HAB_AREA = 5706           # Revolving Swords I
RADIO_AREA = 5
PROB_HABILIDAD = 0.35
PROB_AREA = 0.45          # de las habilidades que usa, cuantas son la de area


def es_santa(m) -> bool:
    return int(getattr(m, 'npc_type', 0) or 0) == NPC_TYPE


def elegir_habilidad(rng=None):
    """La habilidad de este golpe, o None (golpe normal)."""
    import random
    rng = rng or random
    if rng.random() >= PROB_HABILIDAD:
        return None
    return HAB_AREA if rng.random() < PROB_AREA else HAB_UNO


def dano_habilidad(magia, m, defensa):
    """El dano de su habilidad contra esa defensa: con su ataque (Cross Chop) o su ataque magico (Revolving Swords)."""
    import combate as cb
    if magia == HAB_AREA:
        base = int(getattr(m, 'matk', 0) or m.atk) * 0.9
    else:
        base = m.pegar() * 1.3
    return cb.dano_recibido(int(base), int(defensa))


def area_a_otros(ses, m, magia, efecto):
    """Revolving Swords tambien le da a los demas jugadores a RADIO_AREA casillas (el de ses ya lo pega su IA)."""
    import app
    import combate as cb
    golpeados = 0
    for s in app._tw_sesiones():
        p = getattr(s, 'personaje', None)
        if s is ses or not p or getattr(s, 'muerto', False) or getattr(p, 'stage', None) != getattr(m, 'stage', None):
            continue
        if max(abs(p.tile_x - m.tile_x), abs(p.tile_y - m.tile_y)) > RADIO_AREA:
            continue
        try:
            dano = dano_habilidad(magia, m, app.defensa_jugador(s))
            p.hp = max(0, p.hp - dano)
            yo = p.entity_id
            pk = [cb.numero_de_dano(m.entity_id, yo, dano, ataque=magia, efecto=efecto),
                  cb.numero_flotante(yo, dano), cb.atributo(yo, p.hp, cb.KIND_HP)]
            if p.hp <= 0:
                app._quitar_buffs_al_morir(s)
                pk += [cb.ataque(yo, m.entity_id, 0, cb.TIPO_MUERTE), cb.atributo(yo, 0, cb.KIND_HP)]
                s.muerto = True
                app._avisar_muerte_a_los_demas(s, m.entity_id)
            s.enviar_inmediato(*pk)
            golpeados += 1
        except Exception:
            log.exception('Revolving Swords a otro jugador')
    return golpeados


def inmune_a_control(m) -> bool:
    """Aturdir, congelar, inmovilizar, ralentizar y encantar no le hacen nada."""
    return es_santa(m)


# ------------------------------------------------------------------ evento
# Cada 24 h a la HORA_EVENTO (hora del servidor) sale en uno de los mapas de caza que dan a las ciudades, con el
# cartel de arriba para todos; si nadie lo mata en DURACION se va. Comando GM: santa [aparecer [mapa]|retirar|estado].
MAPAS = {6: 'Spike Farm', 32: 'Shadowy Path', 23: 'Dense Forest', 37: 'Wishing Tear'}   # junto a Aurora, Dark City,
HORA_EVENTO = 20                                                                         # Breeze Woods, Iron Castle
DURACION = 60 * 60
ESTADO = pathlib.Path(__file__).parent.parent / 'data' / 'santa_clausula.json'
_EID = [96_500_000]
_ACTIVO = {}              # {'m': Monstruo, 'stage': int, 'fin': ts}

# botin: a cada jugador que le hizo dano, con sus propias tiradas
CAJA = 3861                                   # Christmas Box (100 %)
TRAJE_H = (3885, 3886, 3887)                  # Christmas Warm Hat / Coat / Boots (M), rojos
TRAJE_M = (3878, 3879)                        # Christmas Soft Hat / Dress (F), rojos
PROB_TRAJE = 0.10
GACHAS_40 = tuple(range(89171, 89178))        # Level 40 Gear Gacha: arma, capa, accesorio, ligera, pesada, tunica, gema
PROB_GACHA = 0.15
CAMPANAS = ((3868, 0.05), (3869, 0.01))       # Gold / Platinum Christmas Bell
# Las cajas Lv60 (05/11/2026): una por clase, una de armas y una de monturas, al 1% CADA UNA (tools/generar_lucky_bags.py,
# cajas_santa): 89200 Swordsman, 89201 Axeman, 89202 Lancer, 89203 Archer, 89204 Mage, 89205 armas, 89206 monturas.
CAJAS_60 = tuple(range(89200, 89207))
PROB_CAJA_60 = 0.01


def _cartel(texto):
    import app
    import totem_war
    app._tw_difundir(totem_war.cartel_deslizante(texto))


def _leer_estado():
    import json
    try:
        return json.loads(ESTADO.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _guardar_estado(d):
    import json
    try:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(d), encoding='utf-8')
    except Exception:
        log.exception('guardar estado de Santa Clausula')


def proxima_hora(ahora):
    """El proximo HORA_EVENTO:00 (hora local del servidor) despues de `ahora`."""
    import datetime
    t = datetime.datetime.fromtimestamp(ahora)
    h = t.replace(hour=HORA_EVENTO, minute=0, second=0, microsecond=0)
    if h <= t:
        h += datetime.timedelta(days=1)
    return h.timestamp()


def botin_para(hombre: bool, rng=None):
    """Lo que le toca a un jugador: [item_id]."""
    import random
    rng = rng or random
    sale = [CAJA]
    for it in (TRAJE_H if hombre else TRAJE_M):
        if rng.random() < PROB_TRAJE:
            sale.append(it)
    if rng.random() < PROB_GACHA:
        sale.append(rng.choice(GACHAS_40))
    for it, p in CAMPANAS:
        if rng.random() < p:
            sale.append(it)
    for it in CAJAS_60:
        if rng.random() < PROB_CAJA_60:
            sale.append(it)
    return sale


def _tile_de_aparicion(stage, monstruos):
    """Una casilla donde sale algun monstruo del mapa (asi se pisa seguro)."""
    import random
    import transitable
    sitios = [(getattr(m, 'spawn_x', m.tile_x), getattr(m, 'spawn_y', m.tile_y)) for m in (monstruos or {}).values()]
    random.shuffle(sitios)
    for x, y in sitios:
        if transitable.se_pisa(stage, x, y):
            return x, y
    return sitios[0] if sitios else (100, 100)


def aparecer(stage=None):
    """Lo saca en ese mapa (o uno al azar de MAPAS). Devuelve un texto para el log/GM."""
    import random
    import time
    import app
    import combate as cb
    import login as lg
    if _ACTIVO.get('m') is not None and getattr(_ACTIVO['m'], 'vivo', False):
        return 'Santa Clausula ya esta en %s' % MAPAS.get(_ACTIVO['stage'], _ACTIVO['stage'])
    asegurar_en_db()
    stage = int(stage) if stage else random.choice(list(MAPAS))
    sala = app._SALAS_DEL_MUNDO.setdefault(stage, app._SalaDelMundo(stage))
    if sala.monstruos is None:
        sala.monstruos = app._monstruos_de(stage)
    x, y = _tile_de_aparicion(stage, sala.monstruos)
    _EID[0] += 1
    m = cb.Monstruo(_EID[0], NPC_TYPE, NOMBRE, [x, y], SPRITE, stage=stage)
    m.generado = True
    m.spawn_x, m.spawn_y = x, y
    sala.monstruos[m.entity_id] = m
    pkt = lg._npc_spawn(m.entity_id, NPC_TYPE, NOMBRE, (x, y), sprite=SPRITE, klass=1)
    for s in list(getattr(sala, 'sesiones', []) or []):
        try:
            s.enviar_inmediato(pkt)
        except Exception:
            pass
    _ACTIVO.update({'m': m, 'stage': stage, 'fin': time.time() + DURACION})
    nom = MAPAS.get(stage, 'stage %d' % stage)
    _cartel('[Event] Santa Clausula has appeared in %s (%d, %d)! Defeat him within 60 minutes! / '
            'Santa Clausula ha aparecido en %s (%d, %d)!' % (nom, x, y, nom, x, y))
    log.info('Santa Clausula aparece en %s (%d) casilla (%d, %d)', nom, stage, x, y)
    return 'Santa Clausula en %s (%d, %d)' % (nom, x, y)


def retirar(motivo='se fue'):
    import app
    import combate as cb
    m = _ACTIVO.get('m')
    if m is None:
        return 'no esta'
    stage = _ACTIVO.get('stage')
    _ACTIVO.clear()
    sala = app._SALAS_DEL_MUNDO.get(stage)
    if getattr(m, 'vivo', False):
        m.vivo = False
        if sala is not None and sala.monstruos is not None:
            sala.monstruos.pop(m.entity_id, None)
        for s in (list(getattr(sala, 'sesiones', []) or []) if sala else []):
            try:
                s.enviar_inmediato(cb.despawn_monstruo(m.entity_id))
            except Exception:
                pass
        _cartel('[Event] Santa Clausula escaped with the stolen gifts... / Santa Clausula escapo con los regalos robados...')
    log.info('Santa Clausula retirado: %s', motivo)
    return 'retirado'


def al_morir(ses, m):
    """Botin para cada jugador que le hizo dano (antes de que _repartir_muerte vacie dano_por)."""
    import app
    if not es_santa(m):
        return False
    dano = {int(c): int(d) for c, d in (getattr(m, 'dano_por', None) or {}).items() if int(d) > 0}
    por_cid = {int(s.personaje.char_id): s for s in app._tw_sesiones() if getattr(s, 'personaje', None)}
    premiados = 0
    for cid in dano:
        s = por_cid.get(cid)
        if s is None:
            continue
        ap = list(getattr(s.personaje, 'apariencia', None) or [0])
        for it in botin_para(bool(int(ap[0]) & 1)):
            try:
                app._gm_dar_item(s, it, 1)
            except Exception:
                log.exception('botin de Santa Clausula')
        premiados += 1
    _ACTIVO.clear()
    _cartel('[Event] Santa Clausula has been defeated! %d heroes recovered the gifts. / Santa Clausula fue derrotado!'
            % premiados)
    log.info('Santa Clausula muerto: botin a %d jugadores', premiados)
    return True


async def vigilar(cada=20.0):
    """El reloj del evento: lo saca a su hora y lo retira a los 60 minutos."""
    import asyncio
    import time
    est = _leer_estado()
    if not est.get('proximo'):
        est['proximo'] = proxima_hora(time.time())
        _guardar_estado(est)
    while True:
        await asyncio.sleep(cada)
        try:
            ahora = time.time()
            if _ACTIVO.get('m') is not None and ahora >= _ACTIVO.get('fin', 0):
                retirar('60 minutos')
            if not _ACTIVO and ahora >= float(est.get('proximo') or 0):
                aparecer()
                est['proximo'] = proxima_hora(ahora + 60)
                _guardar_estado(est)
        except Exception:
            log.exception('evento de Santa Clausula')


def comando(partes) -> str:
    """GM: santa aparecer [stage] | santa retirar | santa estado"""
    import time
    sub = (partes[1].lower() if len(partes) > 1 else 'estado')
    if sub in ('aparecer', 'spawn', 'ya'):
        return aparecer(partes[2] if len(partes) > 2 else None)
    if sub in ('retirar', 'quitar', 'despawn'):
        return retirar('GM')
    est = _leer_estado()
    prox = time.strftime('%d/%m %H:%M', time.localtime(float(est.get('proximo') or 0))) if est.get('proximo') else '?'
    if _ACTIVO.get('m') is not None:
        m = _ACTIVO['m']
        return 'en %s, vida %d/%d, se va en %d min; proximo %s' % (
            MAPAS.get(_ACTIVO['stage']), m.hp, m.hp_max, max(0, int((_ACTIVO['fin'] - time.time()) // 60)), prox)
    return 'no esta; proximo %s' % prox
