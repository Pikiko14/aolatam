"""Player combat: timed wars, competitions and permanent Outpost faction PvP."""
import logging
import random
import struct
import cuentas

log = logging.getLogger('pvp')


def objetivo(ses, eid):
    import presencia
    p = getattr(ses, 'personaje', None)
    if not p:
        return None
    for otro in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
        if otro is not ses and presencia.entidad_de(otro) == int(eid):
            return otro
    return None


def mascota_objetivo(ses, eid):
    """(dueno, ficha) de la mascota fuera de otro jugador del mapa con esa entidad, o None. Para poder fijarla y
    pegarle en PvP ("en pvp no puedo darle target a un pet del enemigo", 05/11/2026)."""
    import presencia
    p = getattr(ses, 'personaje', None)
    if not p:
        return None
    for otro in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
        if otro is ses or getattr(otro, 'pet_entity_id', None) != int(eid):
            continue
        f = getattr(getattr(otro, 'personaje', None), 'mascota', None)
        if isinstance(f, dict) and f.get('fuera'):
            return otro, f
    return None


def atacar_mascota(ses, dueno, f_pet, eid, tipo, mag, arma):
    """El jugador le pega a la mascota del rival (golpe basico o habilidad de ataque). True si pego."""
    import app, combate, skills, transitable, random, mascotas
    if not permitido(ses, dueno):
        return False
    if tipo != combate.ATAQUE_NORMAL and (not mag.get('es_ataque') or estado_de_control(tipo)):
        return False
    p = ses.personaje
    px, py = int(f_pet.get('x', 0)), int(f_pet.get('y', 0))
    alcance = combate.alcance_arma(arma) if tipo == combate.ATAQUE_NORMAL else max(1, mag.get('rango', 1))
    if max(abs(p.tile_x - px), abs(p.tile_y - py)) > alcance + 1:
        return False
    if not transitable.linea_libre(p.stage, (p.tile_x, p.tile_y), (px, py)):
        return False
    mp, sp = int(mag.get('mp') or 0), int(mag.get('cost_sp') or 0)
    if p.mp < mp or int(getattr(ses, 'sp', 0) or 0) < sp:
        return False
    p.mp -= mp
    ses.sp = int(getattr(ses, 'sp', 0) or 0) - sp
    p.sp = ses.sp
    ses.pet_rival = dueno
    magia = tipo != combate.ATAQUE_NORMAL and skills.skill_de_magia(tipo) in (1, 2, 3, 4)
    atk = struct.unpack_from('<I', app._stats_ses(ses), 46 if magia else 26)[0]
    if not magia and tipo != combate.ATAQUE_NORMAL:
        atk += int(round(combate.stance_de(tipo) * combate.PESO_STANCE))
    clave = 'mdef' if magia else 'dfs'
    dfs = int(f_pet.get(clave, 50) or 0) + int(mascotas.bonos_efectivos(f_pet).get(clave, 0))
    mult, var_pct = _multiplicador(ses, tipo, mag, magia)
    if random.random() < _prob_critico(ses):
        mult *= 1.5
    dano = max(1, int(dano_pvp(atk, dfs, mult, var_pct, magia=magia)))
    efecto = combate.efecto_de_ataque(tipo) if tipo != combate.ATAQUE_NORMAL else 0
    app._danar_mascota_rival(ses, None, dueno, f_pet, int(eid), dano,
                             tipo if tipo != combate.ATAQUE_NORMAL else 0, efecto, magia, 0)
    ses.enviar(combate.atributo(p.entity_id, p.mp, combate.KIND_MP),
               combate.atributo(p.entity_id, ses.sp, combate.KIND_SP))
    return True


def permitido(ses, otro):
    motivo = _por_que_no(ses, otro)
    if motivo:
        log.info('PvP rechazado: %s -> %s: %s',
                 getattr(getattr(ses, 'personaje', None), 'nombre', '?'),
                 getattr(getattr(otro, 'personaje', None), 'nombre', '?'), motivo)
    return not motivo


def _por_que_no(ses, otro):
    """'' si `ses` puede pegarle a `otro`; si no, el motivo (para el log)."""
    import presencia, totem_war, gremios
    p, q = getattr(ses, 'personaje', None), getattr(otro, 'personaje', None)
    if not p or not q or ses is otro or p.stage != q.stage:
        return 'no estan en el mismo mapa'
    if presencia.clave_de_mapa(ses, p.stage) != presencia.clave_de_mapa(otro, q.stage):
        return 'salas distintas'
    import competiciones
    competition_reason = competiciones.motivo_pvp(ses, otro)
    if competition_reason is not None:
        return competition_reason
    daily_reason=__import__('daily_events').motivo_pvp(ses,otro)
    if daily_reason is not None:return daily_reason
    gvg_reason=__import__('league_war').motivo_pvp(ses,otro)
    if gvg_reason is not None:return gvg_reason
    trade_reason=__import__('trade_routes').motivo_pvp(ses,otro)      # Trade Routes: thieves contra la carga
    if trade_reason is not None:return trade_reason
    import outpost_pvp
    if not outpost_pvp.es_mapa(p.stage) and (not totem_war.activa() or not totem_war.es_mapa_tw(p.stage)):
        return 'sin Totem War o fuera de la arena'
    if presencia.clave_de_mapa(ses, p.stage) != presencia.clave_de_mapa(otro, q.stage):
        return 'salas distintas'
    if getattr(ses, 'muerto', False) or getattr(otro, 'muerto', False) or p.hp <= 0 or q.hp <= 0:
        return 'alguno esta muerto'
    if totem_war.codigo_faccion(p) == totem_war.codigo_faccion(q):
        return 'misma faccion'
    a, b = gremios.obtener_gremio_de(p.char_id), gremios.obtener_gremio_de(q.char_id)
    if a and b and a['guild_id'] == b['guild_id']:
        return 'misma liga'
    return ''


def rivales_en_area(ses, cx, cy, radio):
    """Los jugadores a los que `ses` puede pegar dentro del area (cx, cy, radio)."""
    import presencia
    p = getattr(ses, 'personaje', None)
    if not p:
        return []
    salida = []
    for otro in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
        q = getattr(otro, 'personaje', None)
        if (otro is not ses and q is not None
                and max(abs(q.tile_x - int(cx)), abs(q.tile_y - int(cy))) <= int(radio)
                and not _por_que_no(ses, otro)):
            salida.append(otro)
    return salida


def _multiplicador(ses, tipo, mag, magia):
    """(mult, var_pct) del golpe, con las MISMAS reglas que el ataque a
    monstruos de app: poder del hechizo, 1.2/1.35 de las fisicas, 傷害係數,
    % del equipo y % de los buffs. Sin el critico."""
    import combate, inventario
    p = ses.personaje
    mult, var_pct = 1.0, 0.03
    if magia:
        base = float(mag.get('dano_base') or 0)
        denom = float(mag.get('base_denom') or 200) or 200.0
        mult = base / denom if base > 0 else 1.0
        var_pct = 0.05
        if mag.get('dano_var'):
            var_pct = min(0.15, max(0.02, float(mag['dano_var']) / denom))
        if mag.get('dano_coef'):
            mult *= float(mag['dano_coef']) / 100.0
    elif tipo != combate.ATAQUE_NORMAL:
        # El poder de la habilidad, como contra monstruos (combate.mult_fisico: 0,76 la formula 15, tope 1,35);
        # aqui seguia el 1,35 fijo y un AoE de hacha mataba de un golpe a nivel 60 (01/11/2026).
        mult = combate.mult_fisico(tipo)
        if mag.get('dano_coef'):
            mult *= float(mag['dano_coef']) / 100.0
    else:
        mult = combate.MULT_GOLPE_BASICO               # el golpe basico, como contra monstruos
    if not magia:
        mult *= combate.FACTOR_DANO_FISICO             # golpe basico y habilidades fisicas, -30%
    mods = inventario.modificadores_porcentuales_equipo(getattr(ses, 'inventario', None) or {})
    pct = mods.get('mag_dmg_pct' if magia else 'phys_dmg_pct', 0)
    if pct > 0:
        mult *= 1.0 + pct / 100.0
    pct_b = combate.pct_dano_buffs(getattr(p, 'buffs', None), magia)
    if pct_b:
        mult *= 1.0 + pct_b / 100.0
    return mult, var_pct


class _Resistencias:
    """Las defensas elementales de un jugador con los nombres de las de un monstruo (combate.dano_elemental_extra)."""

    def __init__(self, ses):
        import app
        d = app.defensas_elementales_jugador(ses)
        self.res_fire, self.res_ice, self.res_lightning = d.get('fire', 0), d.get('ice', 0), d.get('thnd', 0)


def _prob_critico(ses):
    import time, app
    extra = 0
    for b in (getattr(ses.personaje, 'buffs', None) or {}).values():
        if isinstance(b, dict) and b.get('fin', 0) > time.time() and 'crit' in b:
            extra += b['crit']
    return min(0.90, (app.critico_jugador(ses) + extra) / 100.0)


# Ajuste global del dano entre jugadores (1.0 = como contra un monstruo de esa
# defensa). Sin datos del oficial; si en PvP se muere demasiado rapido, bajarlo.
FACTOR_PVP = 1.0


def dano_pvp(atk, defensa, mult, var_pct, magia=False, peso=None):
    """Formula de AO entre jugadores. El golpe FISICO es el medido (combate.PESO_GOLPE_FISICO: 0,2426 x mult x
    (ataque - defensa / 3,52)), el mismo que contra un monstruo y que el de un monstruo a un jugador (03/11/2026).
    La MAGIA sigue con (ATAQUE - DEFENSA) x multiplicador:

    La defensa se resta ANTES de multiplicar por la habilidad. Con la de los
    monstruos (multiplicar y luego restar) una magia de x8 con Spl Atk
    101.435 contra 102.735 de Spl Dfs seguia haciendo ~700.000: se cargaba a
    un Archer de 233.000 de vida de un golpe (20/10/2026). Si la defensa
    supera al ataque queda la mitigacion suave 420/(DEF+420), que es un
    rasguno, como debe ser entre stats parecidas."""
    import random
    defensa = max(0, int(defensa))
    atk = max(0, int(atk))
    mult = float(mult) * FACTOR_PVP
    if not magia:
        import combate
        # `peso` 1 en las habilidades de % del ataque (PK, FS): su % ya es lo que entra.
        peso = combate.PESO_GOLPE_FISICO if peso is None else peso
        base = max(1.0, peso * mult * (atk - defensa / combate.DIVISOR_DEFENSA_FISICA))
        return max(1, int(round(base * (1.0 + random.uniform(-var_pct, var_pct)))))
    resta = (atk - defensa) * mult
    suave = atk * mult * (420.0 / (defensa + 420.0) if defensa > 0 else 1.0)
    base = max(1.0, resta, suave)
    return max(1, int(round(base * (1.0 + random.uniform(-var_pct, var_pct)))))


def mitigacion(otro, magia):
    """Lo que deja pasar la victima (0..1): la mitigacion del equipo
    (phys/mag_mit_mult) y la de sus buffs activos ('mit' / 'mag_mit', el
    物理/魔法傷害抵銷 de magic.xml), igual que cuando le pega un monstruo
    (app, IA de monstruos). En PvP no se miraba ninguna de las dos."""
    import time, inventario
    factor = 1.0
    mods = inventario.modificadores_porcentuales_equipo(getattr(otro, 'inventario', None) or {})
    mult = mods.get('mag_mit_mult' if magia else 'phys_mit_mult', 1.0)
    if 0 < mult < 1.0:
        factor *= mult
    ahora = time.time()
    clave = 'mag_mit' if magia else 'mit'
    for b in (getattr(getattr(otro, 'personaje', None), 'buffs', None) or {}).values():
        if isinstance(b, dict) and b.get('fin', 0) > ahora and b.get(clave):
            factor *= max(0.0, 1.0 - float(b[clave]) / 100.0)
    return factor


def atacar(ses, otro, tipo, mag, arma, en_area=False, golpes=None, separacion=None):
    """Llamar despues de validar la cadencia/cooldown general en app.

    Con `en_area` es un golpe de habilidad de AREA: el alcance y el coste ya
    los cobro la habilidad (el rival esta dentro del radio), asi que no se
    miran ni se cobran otra vez, y la animacion ya la puso la habilidad.

    LOS COMBOS PEGAN TODOS SUS GOLPES (combate.combo_de), cada uno con su
    critico, como contra monstruos; antes en PvP solo salia el primero.
    `golpes` y `separacion` los fija quien llama (las AoE de combo)."""
    import asyncio, random
    import app, combate, skills, transitable
    if not permitido(ses, otro):
        return False
    ses.pet_rival = otro          # la mascota del que ataca va a por el (app._pet_contra_rival)
    p, q = ses.personaje, otro.personaje
    if tipo != combate.ATAQUE_NORMAL and not mag.get('es_ataque') and not en_area:
        return False
    if tipo != combate.ATAQUE_NORMAL and mag.get('no_jugadores'):
        return False          # 不能對玩家施放 de magic.xml
    if not en_area:
        alcance = combate.alcance_arma(arma) if tipo == combate.ATAQUE_NORMAL else max(1, mag.get('rango', 1))
        alcance += combate.bono_alcance(p.buffs, tipo, mag)        # Extended Shot, Sword Requiem...
        if max(abs(p.tile_x-q.tile_x), abs(p.tile_y-q.tile_y)) > alcance+1:
            return False
        if not transitable.linea_libre(p.stage, (p.tile_x,p.tile_y), (q.tile_x,q.tile_y)):
            return False
        mp, sp = int(mag.get('mp') or 0), int(mag.get('cost_sp') or 0)
        if p.mp < mp or int(getattr(ses, 'sp', 0) or 0) < sp:
            return False
        p.mp -= mp
        ses.sp = int(getattr(ses, 'sp', 0) or 0) - sp
        p.sp = ses.sp
    if tipo != combate.ATAQUE_NORMAL and estado_de_control(tipo):
        _aplicar_control(ses, otro, tipo, mag, estado_de_control(tipo))
        if not en_area:
            ses.enviar(combate.atributo(p.entity_id, p.mp, combate.KIND_MP),
                       combate.atributo(p.entity_id, ses.sp, combate.KIND_SP))
        return True
    magia = tipo != combate.ATAQUE_NORMAL and skills.skill_de_magia(tipo) in (1,2,3,4)
    atk = struct.unpack_from('<I', app._stats_ses(ses), 46 if magia else 26)[0]
    dfs = struct.unpack_from('<I', app._stats_ses(otro), 54 if magia else 38)[0]
    if not magia and tipo != combate.ATAQUE_NORMAL:
        atk += int(round(combate.stance_de(tipo) * combate.PESO_STANCE))
    if tipo == combate.ATAQUE_NORMAL:
        atk += combate.golpe_extra_buffs(p.buffs)                  # Hooked Arrow, Barb Strike
    mult, var_pct = _multiplicador(ses, tipo, mag, magia)
    # LAS DE % DEL ATAQUE (HP定義 = 百分比: Panther Killing V, Frozen Snipe V al 100%) pegan ese % del ataque, con
    # peso 1 (dano_pvp ya lo preveia y no se usaba). Con el peso medido de los basicos (0,2426) y su 2,69 de
    # multiplicador, PK V pegaba ~0,65 del ataque: "FinalBoss tiene 1.4k de ataque y nos pega 800-900, deberia
    # pegar el 100%" (05/11/2026). Se conservan los % de equipo y buffs que trae `mult`.
    peso = None
    pct = combate.pct_del_arma(tipo) if (tipo != combate.ATAQUE_NORMAL and not magia) else 0
    if pct:
        base_m = combate.mult_fisico(tipo) * combate.FACTOR_DANO_FISICO
        mult = (pct / 100.0) * (mult / base_m if base_m else 1.0)
        peso = 1.0
    crit = _prob_critico(ses)
    if magia:
        crit = min(0.90, crit + combate.crit_magico_buffs(p.buffs) / 100.0)     # Cloud Burst, Lava Charm
    combo = combate.combo_de(tipo) if tipo != combate.ATAQUE_NORMAL else None
    n = max(1, int(golpes)) if golpes is not None else (combo['golpes'] if combo else 1)
    sep = separacion if separacion is not None else max(0.05, (combo or {}).get('intervalo_ms', 200) / 1000.0)
    efecto = combate.efecto_de_ataque(tipo) if tipo != combate.ATAQUE_NORMAL else 0

    vida_objetivo = getattr(otro, 'competicion_vida', 0)
    def _golpe(primero=False):
        if getattr(otro, 'competicion_vida', 0) != vida_objetivo:
            return  # No transferir el resto del combo a su nueva vida/respawn.
        if not permitido(ses, otro):
            return
        es_crit = random.random() < crit
        dano = dano_pvp(atk, dfs, mult * (1.5 if es_crit else 1.0), var_pct, magia=magia, peso=peso)
        dano = max(1, int(round(dano * mitigacion(otro, magia))))
        if magia:
            # Arcane Fire / Ice Age / Lightning Seal, contra las defensas elementales del rival.
            dano += combate.dano_elemental_extra(dano, p.buffs, _Resistencias(otro))
        _aplicar(ses, otro, dano, es_crit, primero and not en_area, tipo, efecto, magia)

    _golpe(primero=True)
    # Lo que la habilidad encadena (轉嫁法術) con su probabilidad, igual que contra monstruos: controles (Silence,
    # Binding, aturdir, congelar, inmovilizar), ralentizar y dano por tiempo (quemadura, veneno, sangrado).
    # "en pvp tambien debe aplicar los efectos en base a su configuracion" (07/11/2026).
    if tipo != combate.ATAQUE_NORMAL and q.hp > 0:
        aplicar_secundario(ses, otro, tipo, mag)
    if n > 1:
        try:
            bucle = asyncio.get_event_loop()
            for k in range(1, n):
                bucle.call_later(sep * k, _golpe)
        except RuntimeError:
            pass
    if not en_area:
        ses.enviar(combate.atributo(p.entity_id, p.mp, combate.KIND_MP),
                   combate.atributo(p.entity_id, ses.sp, combate.KIND_SP))
        if getattr(ses, 'usuario', None):
            cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp, p.hp, p.mp, sp=ses.sp)
    return True


# CONTROL EN PVP (05/11/2026: "Binding y Silence no funcionan"). Las dos son solo de jugadores (不能對NPC施放) y no
# hacen dano: su efecto es el 魔法狀態. pvp_liga solo sabia hacer dano, asi que no hacian nada.
#   捆綁 Binding: "Slows the speed of a target" -> un buff en el rival con move_speed_bonus negativo, que es lo que
#                 app._velocidad_de suma al 0x0005 con el que se le devuelve cada paso.
#   沉默 Silence: "cannot use spells" -> el 0x0006 del rival rechaza sus habilidades mientras dure (app.esta_silenciado).
CONTROLES = {'捆綁': 'atado', '沉默': 'silenciado',
             # 封招 = "unable to use the spell": el Silence de los magos (Action Sealed, rama Life) y el de Silencing
             # Chop. Hacia dano en vez de silenciar ("silence de magos no silencia pero baja dano", 05/11/2026).
             '封招': 'silenciado'}
ESTADO_ENCADENADO = {'silenciado': 'silenciado', 'sellado': 'silenciado', 'atado': 'atado'}
LENTITUD_BINDING = -50          # % de velocidad mientras dura


# Estados de magic.xml que paran al jugador: aturdido / congelado / paralizado / miedo no dejan ni moverse ni atacar;
# inmovilizado solo no deja moverse.
ESTADOS_QUIETO = {'aturdido': 'aturdido', 'congelado': 'aturdido', 'paralizado': 'aturdido', 'miedo': 'aturdido',
                  'inmovilizado': 'inmovil'}


def aplicar_secundario(ses, otro, tipo, mag):
    """El efecto secundario de la habilidad `tipo` sobre el jugador `otro`, con su probabilidad, duracion e intervalo."""
    import combate
    if mag.get('debuff_al_pegar') and random.random() * 100 < mag['debuff_al_pegar']:
        aplicar_debuff(ses, otro, tipo, combate.mods_de_debuff(tipo), mag.get('dur_ms'), mag.get('nombre', ''),
                       con_efecto=False)
    sec = combate.efecto_secundario(tipo) or {}
    prob = sec.get('prob')
    if not sec or random.random() * 100 >= float(100 if prob is None else prob):
        return
    sub = int(sec.get('magia') or tipo)
    dur = int(sec.get('dur_ms') or 0) or 3000
    nombre = mag.get('nombre', '')
    est = ESTADO_ENCADENADO.get(sec.get('estado')) or ESTADOS_QUIETO.get(sec.get('estado'))
    if est:
        _aplicar_control(ses, otro, sub, {'nombre': nombre, 'dur_ms': dur}, est)
    elif int(sec.get('vel_mov') or 0) < 0:
        # Ralentiza: el 移動速度 del hechizo hijo, en el mismo tanto por ciento que usa app._velocidad_de.
        _aplicar_control(ses, otro, sub, {'nombre': nombre, 'dur_ms': dur,
                                          'lentitud': max(-90, int(sec['vel_mov']))}, 'lento')
    if int(sec.get('hp_tick') or 0) < 0 and int(sec.get('intervalo') or 0) > 0:
        aplicar_dot(ses, otro, sub, -int(sec['hp_tick']), int(sec['intervalo']), dur, nombre)
    if sec.get('mods'):
        aplicar_debuff(ses, otro, sub, sec['mods'], dur, nombre, con_efecto=False)


# Las claves de combate.mods_de_debuff a las que lee inventario.stats (sumas directas) y mitigacion() ('mit').
_DEBUFF_A_BUFF = {'def_mod': 'def', 'atk_mod': 'atk', 'matk_mod': 'matk', 'mdef_mod': 'mdef',
                  'phys_mit_pct': 'mit', 'mag_mit_pct': 'mag_mit'}


def aplicar_debuff(ses, otro, tipo, mods, dur_ms, nombre='', con_efecto=True):
    """Un debuff de stats al rival (13/11/2026, "todos los poderes deben dar el efecto que dicen"): -defensa,
    -ataque, -mitigacion... como entrada de sus buffs (la leen sus stats y mitigacion()), con su icono y su fin."""
    import time
    import asyncio
    import app, combate, presencia
    p, q = ses.personaje, otro.personaje
    entrada = {_DEBUFF_A_BUFF[k]: int(v) for k, v in (mods or {}).items() if k in _DEBUFF_A_BUFF and v}
    if not entrada:
        return False
    if combate.resiste_debuff(q.buffs):
        log.info('%s resiste el debuff %s (Exorshield / Barrier of Justice)', q.nombre, nombre)
        return False
    dur_ms = int(dur_ms or 0) or 10000
    entrada.update({'fin': time.time() + dur_ms / 1000.0, 'debuff_pvp': True, 'mag': {'nombre': nombre}})
    if q.buffs is None:
        q.buffs = {}
    q.buffs[int(tipo)] = entrada
    pkts = [struct.pack('<HIBBII', 0x001D, q.entity_id, 1, 4, int(tipo), dur_ms)]
    try:
        pkts.append(app._stats_ses(otro))
    except Exception:
        pass
    if con_efecto:
        efecto = combate.efecto_de_ataque(tipo)
        apub, bpub = presencia.entidad_de(ses), presencia.entidad_de(otro)
        for visor in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
            a = p.entity_id if visor is ses else apub
            b = q.entity_id if visor is otro else bpub
            try:
                (getattr(visor, 'enviar_sin_espejo', None) or visor.enviar)(
                    combate.numero_de_dano(a, b, 0, tipo, efecto=efecto, cast_time=0, es_magia=True),
                    combate.cierre_de_dano(a, b, tipo, efecto=efecto, es_magia=True))
            except Exception:
                pass
    try:
        otro.enviar(*pkts)
    except Exception:
        pass
    log.info('%s debuff %s a %s: %s (%d ms)', p.nombre, nombre, q.nombre, entrada, dur_ms)

    def _expira():
        if (q.buffs or {}).get(int(tipo)) is entrada:
            q.buffs.pop(int(tipo), None)
            try:
                otro.enviar(struct.pack('<HIBBII', 0x001D, q.entity_id, 1, 4, int(tipo), 0), app._stats_ses(otro))
            except Exception:
                pass
    try:
        asyncio.get_event_loop().call_later(dur_ms / 1000.0, _expira)
    except RuntimeError:
        pass
    return True


def maldecir(ses, otro, tipo, mag):
    """Una maldicion (Weak Curse, Exhaustion Curse, Slow Curse...) sobre otro jugador. Antes no se mandaba al PvP:
    solo iban ahi los ataques, y las maldiciones contra jugadores no hacian nada."""
    import combate, transitable
    if not permitido(ses, otro) or mag.get('no_jugadores'):
        return False
    p, q = ses.personaje, otro.personaje
    if max(abs(p.tile_x - q.tile_x), abs(p.tile_y - q.tile_y)) > max(1, mag.get('rango', 1)) + 1:
        return False
    if not transitable.linea_libre(p.stage, (p.tile_x, p.tile_y), (q.tile_x, q.tile_y)):
        return False
    mp, sp = int(mag.get('mp') or 0), int(mag.get('cost_sp') or 0)
    if p.mp < mp or int(getattr(ses, 'sp', 0) or 0) < sp:
        return False
    p.mp -= mp
    ses.sp = int(getattr(ses, 'sp', 0) or 0) - sp
    p.sp = ses.sp
    ses.enviar(combate.atributo(p.entity_id, p.mp, combate.KIND_MP), combate.atributo(p.entity_id, ses.sp, combate.KIND_SP))
    mods = combate.mods_de_debuff(tipo)
    if int(mag.get('vel_mov_mod') or 0) < 0:
        _aplicar_control(ses, otro, tipo, {'nombre': mag.get('nombre', ''), 'dur_ms': mag.get('dur_ms'),
                                           'lentitud': max(-90, int(mag['vel_mov_mod']))}, 'lento')
    hecho = aplicar_debuff(ses, otro, tipo, mods, mag.get('dur_ms'), mag.get('nombre', ''))
    aplicar_secundario(ses, otro, tipo, mag)
    return hecho or int(mag.get('vel_mov_mod') or 0) < 0


def aplicar_dot(ses, otro, sub, dano, intervalo_s, dur_ms, nombre=''):
    """Dano por tiempo a un jugador: `dano` cada `intervalo_s` segundos durante `dur_ms`. Deja 1 de vida (no mata: la
    muerte la decide un golpe). Lleva el icono del hechizo hijo (0x001D kind 4) y se renueva si vuelve a entrar."""
    import asyncio
    import time
    import combate, presencia
    q = otro.personaje
    fin = time.time() + dur_ms / 1000.0
    marca = object()
    dots = otro.__dict__.setdefault('_dots_pvp', {})
    dots[int(sub)] = marca
    try:
        otro.enviar(struct.pack('<HIBBII', 0x001D, q.entity_id, 1, 4, int(sub), int(dur_ms)))
    except Exception:
        pass
    log.info('PvP: %s le pone %s a %s (%d cada %d s, %d ms)', getattr(ses.personaje, 'nombre', '?'), nombre,
             q.nombre, dano, intervalo_s, dur_ms)

    def _tic():
        if dots.get(int(sub)) is not marca:
            return                                  # lo renovo otro golpe: sigue ese
        if time.time() > fin + 0.05 or getattr(otro, 'muerto', False) or not getattr(otro, 'personaje', None):
            dots.pop(int(sub), None)
            return
        if q.hp > 1:
            d = min(int(dano), q.hp - 1)
            q.hp -= d
            pk_yo = [combate.numero_flotante(q.entity_id, d), combate.atributo(q.entity_id, q.hp, combate.KIND_HP)]
            try:
                otro.enviar(*pk_yo)
                pub = presencia.entidad_de(otro)
                stage = presencia.clave_de_mapa(otro, q.stage)
                for s in presencia._vivas(stage):
                    if s is not otro:
                        presencia._mandar(s, combate.numero_flotante(pub, d), presencia._vida_publica(otro))
            except Exception:
                log.debug('tic de dano por tiempo', exc_info=True)
        try:
            asyncio.get_event_loop().call_later(max(1, intervalo_s), _tic)
        except RuntimeError:
            pass
    try:
        asyncio.get_event_loop().call_later(max(1, intervalo_s), _tic)
    except RuntimeError:
        pass


def esta_quieto(ses, ataque=False) -> bool:
    """Aturdido/congelado no se mueve ni ataca; inmovilizado solo no se mueve."""
    return tiene_estado(ses, 'aturdido') or (not ataque and tiene_estado(ses, 'inmovil'))


def estado_de_control(tipo):
    """'atado' / 'silenciado' si la habilidad es un control de jugadores sin dano, o None."""
    import combate
    d = combate._magic_xml().get(int(tipo or 0)) or {}
    if d.get('平均傷害') or (d.get('HP') and d.get('HP') != '0'):
        return None
    return CONTROLES.get(str(d.get('魔法狀態') or ''))


def _aplicar_control(ses, otro, tipo, mag, estado):
    """Le pone el estado al rival: su icono (0x001D kind 4), el efecto para todos y la expiracion."""
    import time
    import asyncio
    import combate, presencia
    p, q = ses.personaje, otro.personaje
    # Power Shield: "Demon Seal and Silence are invalid on you".
    if estado == 'silenciado' and __import__('avatar_clones').escudo_mp_activo(otro)[0] is not None:
        log.info('%s no silencia a %s: tiene Power Shield', p.nombre, q.nombre)
        return
    if combate.resiste_debuff(q.buffs):
        log.info('%s resiste %s (Exorshield / Barrier of Justice)', q.nombre, estado)
        return
    dur_ms = int(mag.get('dur_ms') or 0) or 5000
    fin = time.time() + dur_ms / 1000.0
    lentitud = mag.get('lentitud')
    if lentitud is None:
        lentitud = LENTITUD_BINDING if estado == 'atado' else 0
    entrada = {'fin': fin, 'estado': estado, 'control_pvp': True,
               'mag': {'nombre': mag.get('nombre', ''), 'move_speed_bonus': lentitud}}
    if q.buffs is None:
        q.buffs = {}
    q.buffs[int(tipo)] = entrada
    efecto = combate.efecto_de_ataque(tipo)
    apub, bpub = presencia.entidad_de(ses), presencia.entidad_de(otro)
    for visor in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
        a = p.entity_id if visor is ses else apub
        b = q.entity_id if visor is otro else bpub
        pkts = [combate.numero_de_dano(a, b, 0, tipo, efecto=efecto, cast_time=0, es_magia=False),
                combate.cierre_de_dano(a, b, tipo, efecto=efecto, es_magia=False)]
        if visor is otro:
            pkts.append(struct.pack('<HIBBII', 0x001D, q.entity_id, 1, 4, int(tipo), dur_ms))
        try:
            (getattr(visor, 'enviar_sin_espejo', None) or visor.enviar)(*pkts)
        except Exception:
            pass
    log.info('%s %s a %s con %s (%d ms)', p.nombre, estado, q.nombre, mag.get('nombre'), dur_ms)

    def _expira():
        if (q.buffs or {}).get(int(tipo)) is entrada:
            q.buffs.pop(int(tipo), None)
            try:
                otro.enviar(struct.pack('<HIBBII', 0x001D, q.entity_id, 1, 4, int(tipo), 0))
            except Exception:
                pass
    try:
        asyncio.get_event_loop().call_later(dur_ms / 1000.0, _expira)
    except RuntimeError:
        pass


def tiene_estado(ses, estado) -> bool:
    import time
    ahora = time.time()
    return any(isinstance(b, dict) and b.get('estado') == estado and b.get('fin', 0) > ahora
               for b in (getattr(getattr(ses, 'personaje', None), 'buffs', None) or {}).values())


def _aplicar(ses, otro, dano, es_crit, con_efecto, tipo, efecto, magia, *, origen_eid=None):
    """Un golpe ya calculado: vida, paquetes a todos los que lo ven y muerte."""
    import combate, presencia
    p, q = ses.personaje, otro.personaje
    if combate.inmune_al_dano(q.buffs):
        dano = 0                                   # Shield Wall: inmune al dano fisico y magico mientras dura
    dano = __import__('avatar_clones').absorber(otro,dano)
    q.hp = max(0, q.hp - dano)
    combate.acumular(q.buffs, 'recibido', dano)               # Rage Armor del que recibe
    combate.acumular(p.buffs, 'hecho', dano)                  # Spear Trap del que pega
    # Hurt Recovery / Agonizing Regen (被爆擊回血): un critico recibido devuelve al momento ese % del dano.
    cura = combate.cura_por_critico(dano, q.buffs) if (es_crit and q.hp) else 0
    if cura:
        import app
        q.hp = min(app._vida_max(q, otro.inventario), q.hp + cura)
    apub, bpub = presencia.entidad_de(ses), presencia.entidad_de(otro)
    visibles = presencia._vivas(presencia.clave_de_mapa(ses, p.stage))
    tipo_num = combate.TIPO_DANO_CRITICO if es_crit else combate.TIPO_DANO
    if not q.hp:
        # Primero se le caen los buffs y la transformacion: transformado no hacia la animacion de muerte.
        __import__('app')._quitar_buffs_al_morir(otro)
    for visor in visibles:
        a = origen_eid if origen_eid is not None else (p.entity_id if visor is ses else apub)
        b = q.entity_id if visor is otro else bpub
        pkts = []
        if con_efecto and efecto:
            # El efecto de la habilidad sobre el rival, UNA vez por uso.
            pkts += [combate.numero_de_dano(a, b, dano, tipo, efecto=efecto, cast_time=0, es_magia=magia),
                     combate.cierre_de_dano(a, b, tipo, efecto=efecto, es_magia=magia)]
        elif con_efecto:
            pkts.append(combate.ataque(a, b))
        # A la victima su vida tal cual; a los demas en porcentaje (presencia._vida_publica), o la barra sale llena.
        pkts += [combate.numero_flotante(b, dano, tipo_num),
                 combate.atributo(b, q.hp, combate.KIND_HP) if visor is otro else presencia._vida_publica(otro)]
        if cura and visor is otro:
            pkts.append(combate.numero_flotante(b, cura, combate.TIPO_CURA_HP))
        if not q.hp:
            if visor is otro:
                # La victima muere como cuando la mata un monstruo (app, IA de
                # monstruos): ataque con TIPO_MUERTE sobre si misma y HP 0.
                # Con el 0x0008 de muerte de monstruo su cliente no pasaba a
                # muerto ni ofrecia revivir.
                pkts += [combate.ataque(b, a, 0, combate.TIPO_MUERTE),
                         combate.atributo(b, 0, combate.KIND_HP)]
            else:
                pkts.append(combate.muerte_monstruo(b, a))
        mandar = getattr(visor, 'enviar_sin_espejo', None) or visor.enviar
        try:
            mandar(*pkts)
            if hasattr(visor, 'volcar'):
                visor.volcar()
        except Exception:
            pass
    if not q.hp:
        # Y a los demas, lo mismo que cuando mata un monstruo (app._avisar_muerte_a_los_demas): la muerte y DESPUES la
        # vida en 0. Aqui la vida iba antes de la muerte y le seguian viendo de pie ("matamos a elias y sigue
        # saliendo vivo", 06/11/2026).
        try:
            __import__('app')._avisar_muerte_a_los_demas(otro, apub)
        except Exception:
            log.debug('aviso de muerte PvP a los demas', exc_info=True)
        otro.muerto = True
        otro.objetivo_actual = None
        import competiciones
        if p.stage in competiciones.MAPAS:
            competiciones.baja(ses, otro)
            return  # no recompensas de Totem War ni penalizacion de EXP
        if p.stage in __import__('daily_events').STAGES:
            __import__('daily_events').baja(ses,otro)
            return
        if p.stage in __import__('league_war').STAGES:
            __import__('league_war').kill(ses,otro)
            return
        import outpost_pvp
        if not outpost_pvp.es_mapa(p.stage):
            _contar_baja(ses, p, q)  # Outpost is not a source of TW credits/round kills.
        try:
            import app as _app_l
            _app_l._logros_contar(otro, 'muertes')
        except Exception:
            log.exception('logros: muerte PvP')
        if getattr(otro, 'usuario', None):
            cuentas._actualizar_personaje(otro.usuario, q.char_id,
                lambda d: d.update(pvp_deaths=int(d.get('pvp_deaths', 0))+1))
    # La vida en el panel del equipo (0x0026): con los monstruos ya se avisaba, en PvP no, y el equipo le seguia
    # viendo vivo ("sigue saliendo vivo en el team").
    try:
        __import__('equipos').notificar_stats(otro)
    except Exception:
        log.debug('vida al equipo en PvP', exc_info=True)
    if getattr(otro, 'usuario', None):
        cuentas.guardar_progreso(otro.usuario, q.char_id, q.nivel, q.exp, q.hp, q.mp)


def _contar_baja(ses, p, victima=None):
    """La baja: marcador K.O. (0x001D codigo 25) y creditos de rango (segun el nivel de la victima, totem_war)."""
    import combate, clases, totem_war
    try:
        creditos = totem_war.creditos_por_baja(victima)
        ronda = totem_war._RONDA.get(p.char_id, 0) + 1
        totem_war._RONDA[p.char_id] = ronda
        total = [int(getattr(p, 'pvp_kills', 0) or 0) + 1]
        if getattr(ses, 'usuario', None):
            def _sumar(d):
                d['pvp_kills'] = int(d.get('pvp_kills', 0) or 0) + 1
                d['tw_kills'] = int(d.get('tw_kills', 0) or 0) + 1
                total[0] = d['pvp_kills']
            cuentas._actualizar_personaje(ses.usuario, p.char_id, _sumar)
        total = total[0]
        p.pvp_kills = total
        p.creditos = int(getattr(p, 'creditos', 0) or 0) + creditos
        nuevo_rango = combate.rango_de_creditos(p.creditos)
        # Debajo del K.O. van los CREDITOS ganados en esta guerra, no las bajas totales ("debajo del 1 K.O. sale los
        # creditos obtenidos, ese numero amarillo", 07/11/2026).
        ganados = totem_war._CREDITOS_GUERRA.get(p.char_id, 0) + creditos
        totem_war._CREDITOS_GUERRA[p.char_id] = ganados
        pkts = [totem_war.kills_ko(p.entity_id, ronda, ganados),
                combate.atributo(p.entity_id, p.creditos, combate.KIND_CREDITO),
                clases.aviso(str(creditos), tipo=0, msg_id=642)]
        if nuevo_rango > int(getattr(p, 'rango', 1) or 1):
            p.rango = nuevo_rango
            pkts += [combate.atributo(p.entity_id, p.rango, combate.KIND_RANGO),
                     combate.efecto_level_up(p.entity_id, es_rango=True)]
        ses.enviar(*pkts)
        if getattr(ses, 'usuario', None):
            cuentas.guardar_rango(ses.usuario, p.char_id, p.rango, p.creditos)
        log.info('PvP: %s lleva %d bajas en la ronda (%d en total), +%d creditos',
                 p.nombre, ronda, total, creditos)
    except Exception:
        log.exception('PvP: no se pudo contar la baja')
