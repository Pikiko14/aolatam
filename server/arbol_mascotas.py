"""El arbol de evolucion de la mascota (10/11/2026: "podemos hacer algo asi?? ... hazlo", con la ventana "Evolution of
Orange Tabby" de otro servidor de ejemplo).

La ventana es la 59400 de wnd03.xml (tools/parche_arbol_mascotas.py) y su logica server/lua/arbol.lua, que el servidor
manda por el canal Lua. El boton Evolve, debajo de la ficha de la mascota (ventana 878 de wnd01.xml), llama a
OnCommandArbol (SALUDO_LUA, se manda al entrar con los demas saludos de subasta_ventana.py).

    c2s 0x002F [u8 170][u32 a][u32 b]: a = 1 abrir; a = 2 evolucionar hacia el nodo b.

EL ARBOL es el de pet.xml: cada etapa tiene sus dos ramas (升階變化1 y 2, la 'mean' y la 'nice') y una mascota normal
hace tres evoluciones, asi que salen 1 + 2 + 4 + 8 formas. Se pinta como un monton binario: los hijos del nodo i son el
2i+1 (rama 1) y el 2i+2 (rama 2). Si las dos ramas llevan a la misma forma (la linea Abyss) solo sale la primera.

ELEGIR: "click a form ... Evolve". Pulsar una forma y Evolve guarda el camino hasta ella en la ficha ('ruta', que
mascotas.rama_por_crianza obedece antes que la crianza) y evoluciona YA si se puede: del huevo a la primera forma con
nivel 15, a la media con nivel 35 y un Medium Blood Certificate, a la final con nivel 55 y un Advanced Blood
Certificate (el certificado se gasta). Si aun no se puede, el camino queda guardado y se sigue solo: la del huevo al
llegar a 15 y las demas al usar el certificado. Sin elegir nada todo va como antes, por la crianza.
"""
import logging

import canal_lua

log = logging.getLogger('app')

CMD_ARBOL = 170
NODOS = 15
NIVEL_ETAPA = {'原型': 1, '初階': 15, '中階': 35, '高階': 55, '頂階': 1}
# El 寵物類型 de pet.xml en ingles: el cliente pintaba ???? con los que faltaban (10/11/2026).
CLASE = {
    '攻擊型': 'DPS', '魔攻型': 'Mage', '輔助回復型': 'Support', '防禦型': 'Tanky', '萬能型': 'All-round',
    '強攻型': 'Striker', '攻防並重型': 'Balanced', '魔力型': 'Magic', '輔助攻擊型': 'Assist', '迅捷型': 'Swift',
    '堅守型': 'Guardian', '大地強壯型': 'Earth', '風雷迅速型': 'Storm', '平均型': 'Average', '硬漢型': 'Tough',
    '火焰攻擊型': 'Flame', '寒冰防禦型': 'Ice Guard', '血牛型': 'Vital', '遠程攻擊型': 'Ranged',
    '火屬性攻擊型': 'Fire', '敏捷型': 'Agile', '雷屬性敏捷型': 'Thunder', '風雷迅捷型': 'Gale',
    '水屬性平均型': 'Water', '監守型': 'Warden',
}
# Las imagenes propias de cada forma (tools/retratos_arbol.py): {sprite: N}, el retrato grande es PRIMER_ICONO + N y
# el pequeno de los cuadros PRIMER_PEQUENO + N. Sin la suya, el retrato de pet.xml y ninguna pequena.
PRIMER_ICONO, PRIMER_PEQUENO = 70000, 72000
_RETRATOS = None


def retratos() -> dict:
    global _RETRATOS
    if _RETRATOS is None:
        import json
        import pathlib
        ruta = pathlib.Path(__file__).parent / 'plantillas' / 'retratos_arbol.json'
        _RETRATOS = {int(k): int(v) for k, v in json.loads(ruta.read_text(encoding='utf-8')).items()} \
            if ruta.is_file() else {}
    return _RETRATOS
# El boton Evolve (59399) solo con el panel de stats desplegado ("el evolve solo salga si esta abierto ese panel",
# 10/11/2026): se envuelven CreatePetInfoWnd y OnClickPetDetail (petinfo.lua, el que pliega el panel 880 y cambia
# SWITCH_PET_INFO) para que lo enseñen u oculten a la vez. AOF_EVOLVE_ENVUELTO evita envolverlas dos veces.
SALUDO_LUA = ('function OnCommandArbol(dwID, dwCmdID, dwParam, pParam) '
              'game.netcommand2(%d, 1, 0) return 1 end '
              'function AofEvolveVisible() '
              'if WND_PET_INFO and WND_PET_INFO ~= 0 and window.isexist(WND_PET_INFO) then '
              'window.show(window.find(WND_PET_INFO, 59399), SWITCH_PET_INFO == 1) end end '
              'if not AOF_EVOLVE_ENVUELTO and CreatePetInfoWnd and OnClickPetDetail then '
              'AOF_EVOLVE_ENVUELTO = true '
              'local c1 = CreatePetInfoWnd '
              'CreatePetInfoWnd = function(...) local r = c1(...) AofEvolveVisible() return r end '
              'local c2 = OnClickPetDetail '
              'OnClickPetDetail = function(...) local r = c2(...) AofEvolveVisible() return r end end '
              'AofEvolveVisible()' % CMD_ARBOL)
_LUA = None
_PADRES = None


def _lua() -> str:
    global _LUA
    if _LUA is None:
        import pathlib
        _LUA = (pathlib.Path(__file__).parent / 'lua' / 'arbol.lua').read_text(encoding='utf-8')
    return _LUA


def _tabla():
    import mascotas
    return mascotas._tabla()


def padres() -> dict:
    """{pet: [pets de los que sale]}."""
    global _PADRES
    if _PADRES is None:
        _PADRES = {}
        for pid, f in _tabla().items():
            for r in (f.get('rama1'), f.get('rama2')):
                if r:
                    _PADRES.setdefault(int(r), []).append(int(pid))
    return _PADRES


def raiz(pid: int) -> int:
    """La forma de la que sale toda la linea: se sube de padre en padre (el primero, si hay varios)."""
    pid, vistos = int(pid), set()
    while pid in padres() and pid not in vistos:
        vistos.add(pid)
        pid = padres()[pid][0]
    return pid


def arbol(pid_raiz: int) -> list:
    """Los NODOS ids de la linea en orden de monton (None donde no hay forma)."""
    nodos = [None] * NODOS
    nodos[0] = int(pid_raiz)
    for i in range(NODOS):
        if nodos[i] is None or 2 * i + 2 >= NODOS:
            continue
        f = _tabla().get(nodos[i]) or {}
        r1, r2 = f.get('rama1'), f.get('rama2')
        nodos[2 * i + 1] = int(r1) if r1 else None
        nodos[2 * i + 2] = int(r2) if r2 and r2 != r1 else None
    return nodos


def camino(i: int, j: int):
    """Los nodos de i (sin el) a j si j cuelga de i; None si no."""
    pasos = []
    while j > i:
        pasos.append(j)
        j = (j - 1) // 2
    return list(reversed(pasos)) if j == i and pasos else None


def ficha_de(pid: int, padre=None) -> dict:
    """Lo que la ventana ensena de una forma."""
    import mascotas
    from house_services import xml_rows
    f = _tabla().get(int(pid)) or {}
    etapa = f.get('etapa', '')
    nivel = NIVEL_ETAPA.get(etapa, 1)
    clase = CLASE.get(f.get('clase'), f.get('clase') or '')
    st = mascotas.stats_de(int(pid), nivel)
    magias = xml_rows('magic.xml')
    habilidades = []
    for mid in mascotas.skills_de(int(pid), nivel):
        if not mid:
            continue
        m = magias.get(int(mid)) or {}
        habilidades.append([int(m.get('介面圖號') or 0), m.get('名稱') or '?', (m.get('說明') or '')[:180]])
    if padre:
        texto = '%s - evolves at level %d from %s' % (clase, nivel, (_tabla().get(int(padre)) or {}).get('nombre', '?'))
    else:
        texto = '%s - the egg of this line' % clase if clase else 'The egg of this line'
    n = retratos().get(int(f.get('tipo') or 0))
    return {
        'nombre': f.get('nombre') or '?', 'nivel': nivel, 'clase': clase,
        'retrato': PRIMER_ICONO + n if n is not None else int(f.get('retrato') or 0),
        'icono': PRIMER_PEQUENO + n if n is not None else 0,
        'texto': texto,
        'stats1': 'HP %d  MP %d  Atk %d  Dfs %d' % (st.get('hp_max', 0), st.get('mp_max', 0), st.get('atk', 0),
                                                   st.get('dfs', 0)),
        'stats2': 'M.Atk %d  M.Dfs %d  Rig %d  Agi %d' % (st.get('matk', 0), st.get('mdef', 0), st.get('rigor', 0),
                                                         st.get('agilidad', 0)),
        'habilidades': habilidades,
    }


def _mascota(ses):
    return getattr(getattr(ses, 'personaje', None), 'mascota', None)


def abrir(ses, aviso=None) -> list:
    """La ventana con la linea de la mascota que esta fuera."""
    import clases
    f = _mascota(ses)
    if not f:
        return [clases.aviso('Summon your pet to see its evolution.', tipo=0)]
    actual = int(f.get('sprite') or 0)
    nodos = arbol(raiz(actual))
    datos = []
    for i, pid in enumerate(nodos):
        datos.append(ficha_de(pid, nodos[(i - 1) // 2] if i else None) if pid else False)
    i_actual = nodos.index(actual) if actual in nodos else 0
    ruta = [int(x) for x in (f.get('ruta') or [])]
    elegido = next((i for i in range(NODOS - 1, -1, -1) if nodos[i] in ruta and camino(i_actual, i)), -1)
    nombre = (_tabla().get(nodos[0]) or {}).get('nombre') or f.get('nombre') or 'pet'
    return [canal_lua.paquete(_lua()),
            canal_lua.llamar('ArbolAbrir', 'Evolution of %s' % (f.get('nombre') or nombre), datos, i_actual,
                             elegido, aviso or '')]


def _certificado(ses, etapa):
    """La casilla de la mochila con un certificado de esa etapa (2 MBC, 3 ABC), o None."""
    import inventario as inv
    for r, it in sorted((ses.inventario or {}).items()):
        if 20 <= int(r) and inv.es_certificado_sangre(int(it)) == etapa:
            return int(r)
    return None


def evolucionar(ses, i_destino: int, addr='?'):
    """Evolve hacia el nodo i_destino. Devuelve el aviso para la ventana."""
    import app
    import cuentas
    import mascotas
    f = _mascota(ses)
    if not f:
        return 'Summon your pet first.'
    actual = int(f.get('sprite') or 0)
    nodos = arbol(raiz(actual))
    if not 0 <= i_destino < NODOS or not nodos[i_destino]:
        return 'Pick a form in the tree first.'
    i_actual = nodos.index(actual) if actual in nodos else -1
    pasos = camino(i_actual, i_destino) if i_actual >= 0 else None
    if not pasos:
        return 'Your pet cannot evolve into that form from here.'
    f['ruta'] = [nodos[k] for k in pasos]
    siguiente = (_tabla().get(nodos[pasos[0]]) or {})
    destino = (_tabla().get(nodos[i_destino]) or {}).get('nombre', '?')
    etapa = (_tabla().get(actual) or {}).get('etapa')
    nivel = int(f.get('nivel', 1) or 1)
    rama = 'mean' if pasos[0] == 2 * i_actual + 1 else 'nice'
    falta = None
    cert = None
    if etapa == '原型':
        if nivel < mascotas.NIVEL_PRIMERA_RAMA:
            falta = 'Path set to %s. Your pet evolves at level %d.' % (destino, mascotas.NIVEL_PRIMERA_RAMA)
    elif etapa in ('初階', '中階'):
        tope, cual, nombre_cert = ((mascotas.NIVEL_MEDIO, 2, 'Medium Blood Certificate') if etapa == '初階'
                                   else (mascotas.NIVEL_AVANZADO, 3, 'Advanced Blood Certificate'))
        cert = _certificado(ses, cual)
        if nivel < tope or cert is None:
            falta = 'Path set to %s. Next: level %d and a %s.' % (destino, tope, nombre_cert)
    else:
        return 'This pet cannot evolve any further.'
    r = f.get('ranura')
    if r is not None and getattr(ses.personaje, 'mascotas', None) is not None:
        ses.personaje.mascotas[str(r)] = f
    if falta:
        if getattr(ses, 'usuario', None):
            cuentas.guardar_mascota(ses.usuario, ses.personaje.char_id, f, getattr(ses.personaje, 'mascotas', None))
        log.info('[%s] arbol de evolucion: camino a %s guardado', addr, destino)
        return falta
    mascotas.evolucionar(f, rama)
    app._pet_tras_evolucion(ses, f, 'Your pet evolved to %s!' % f.get('nombre'), ranura_gastada=cert)
    log.info('[%s] arbol de evolucion: %s -> %s%s', addr, actual, f.get('nombre'),
             ' (certificado de la casilla %d)' % cert if cert is not None else '')
    return 'Your pet evolved to %s!' % siguiente.get('nombre', f.get('nombre'))


def procesar(ses, cuerpo, addr='?') -> bool:
    """El 0x002F de la ventana del arbol. True si era suyo."""
    import struct
    if len(cuerpo) < 9 or cuerpo[0] != CMD_ARBOL:
        return False
    a, b = struct.unpack_from('<II', cuerpo, 1)
    if a == 1:
        ses.enviar(*abrir(ses))
    elif a == 2:
        aviso = evolucionar(ses, int(b), addr)
        ses.enviar(*abrir(ses, aviso))
    return True
