"""Los 60 pisos de la Torre de Babel (02/11/2026): un jefe por piso, del nivel del piso.

"Un evento de torre de babel, en el que salgan jefes desde lvl 1 hasta lvl 60, jefes base por supuesto ... puedes
rehacer algunos mob altos y ajustar su ataque, hp y def". Escribe server/plantillas/torre_babel.json con, por piso,
el jefe (npc_type, su nombre) y los stats con los que sale (hp, atk, def, matk, mdef).

* Se usan los jefes NORMALES del juego (monster.王 = 是 en content.db): nombre en ingles (los de nombre japones o
  chino son copias de otros servidores) y vida dentro de la curva de los jefes de campo. Fuera quedan los de evento
  y los especiales (Boom Slarm con 99.999.999, Totem Guard, los "Lord" de 4-5 millones...).
* Piso con jefe de su nivel: sale tal cual (si hay varios, el de mas vida, sin repetir el del piso anterior).
* Piso sin jefe de su nivel: el jefe del nivel mas cercano, con sus stats escalados a la curva del piso
  (CURVA: la media de los jefes base de cada nivel, interpolada).

    python tools/generar_torre_babel.py
"""
import json
import pathlib
import sqlite3

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DB = RAIZ / 'corpus' / 'content.db'
SALIDA = RAIZ / 'server' / 'plantillas' / 'torre_babel.json'
PISOS = 60
STATS = ('hp', 'atk', 'def', 'matk', 'mdef')
# Un jefe "base" tiene como mucho esta vida por nivel (los de campo andan por 300-600 por nivel; los de evento,
# por millones).
VIDA_MAX_POR_NIVEL = 1500


def _n(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def jefes_base():
    """[{npc_type, nombre, nivel, hp, atk, def, matk, mdef}] de los jefes normales de nivel 1-70."""
    con = sqlite3.connect(DB)
    filas = con.execute("select id, name, level, hp, atk_avg, def, matk, mdef from monster "
                        "where 王 = '是' and id glob '[0-9]*'").fetchall()
    con.close()
    salida = []
    for mid, nombre, nivel, hp, atk, df, matk, mdef in filas:
        nivel, hp = _n(nivel), _n(hp)
        nombre = (nombre or '').strip()
        if not (1 <= nivel <= 70) or hp <= 0 or not nombre or not nombre.isascii():
            continue
        if hp > VIDA_MAX_POR_NIVEL * max(nivel, 5) or _n(atk) <= 0:
            continue
        # Los de prueba o de broma del juego: 6 de vida o 878 de ataque a nivel 1 (Evil Clown, MechaGirl).
        if hp < 50 * nivel or not 5 * nivel <= _n(atk) <= 40 * max(nivel, 5):
            continue
        salida.append({'npc_type': int(mid), 'nombre': nombre, 'nivel': nivel, 'hp': hp, 'atk': _n(atk),
                       'def': _n(df), 'matk': _n(matk), 'mdef': _n(mdef)})
    return salida


def curva(jefes):
    """{nivel: {stat: valor}} de 1 a PISOS: la media de los jefes de cada nivel, interpolada donde no hay."""
    por_nivel = {}
    for j in jefes:
        por_nivel.setdefault(j['nivel'], []).append(j)
    # La MEDIANA de cada nivel: un jefe raro (Sam the Ox, 43.000 de vida a nivel 50) no tuerce la curva.
    puntos = {nv: {s: sorted(j[s] for j in js)[len(js) // 2] for s in STATS} for nv, js in por_nivel.items()}
    niveles = sorted(puntos)
    salida = {}
    for nv in range(1, PISOS + 1):
        if nv in puntos:
            salida[nv] = puntos[nv]
            continue
        bajo = max((x for x in niveles if x < nv), default=None)
        alto = min((x for x in niveles if x > nv), default=None)
        if bajo is None:                          # por debajo del primer jefe: proporcional al nivel
            salida[nv] = {s: puntos[alto][s] * nv / float(alto) for s in STATS}
            continue
        if alto is None:
            alto = bajo
        t = 0.0 if alto == bajo else (nv - bajo) / float(alto - bajo)
        salida[nv] = {s: puntos[bajo][s] + (puntos[alto][s] - puntos[bajo][s]) * t for s in STATS}
    return salida


# Lo que puede alejarse un jefe de lo normal de su piso (la curva): por debajo y por encima se recorta. Asi un jefe
# de evento (Fools' Day Clown, 21.000 de vida a nivel 21) o uno muy raro (Sam the Ox, mucha vida y poco ataque) no
# hacen un piso imposible ni uno regalado.
LIMITES = {'hp': (0.6, 1.8), 'atk': (0.6, 1.6), 'def': (0.6, 1.6), 'matk': (0.4, 1.6), 'mdef': (0.6, 1.6)}


def _recortar(stats, normal):
    salida, tocado = {}, False
    for s, v in stats.items():
        lo, hi = LIMITES[s]
        if normal[s] > 0:
            nv = int(round(min(max(v, normal[s] * lo), normal[s] * hi)))
            tocado = tocado or nv != v
            v = nv
        salida[s] = max(1, v)
    return salida, tocado


def pisos():
    jefes = jefes_base()
    cur = curva(jefes)
    salida, anterior, usados = [], None, set()
    for piso in range(1, PISOS + 1):
        del_nivel = sorted((j for j in jefes if j['nivel'] == piso), key=lambda j: -j['hp'])
        del_nivel = [j for j in del_nivel if j['npc_type'] != anterior] or del_nivel
        if del_nivel:
            j = del_nivel[0]
            stats = {s: j[s] for s in STATS}
            ajustado = False
        else:
            # El del nivel mas cercano, mejor uno que aun no haya salido (si no, los pisos 1-9 alternaban dos).
            cerca = sorted((j for j in jefes if j['npc_type'] != anterior),
                           key=lambda j: (abs(j['nivel'] - piso), j['npc_type'] in usados, -j['hp']))
            j = cerca[0]
            base = cur[j['nivel']] if j['nivel'] <= PISOS else cur[PISOS]
            stats = {s: max(1, int(round(j[s] * cur[piso][s] / base[s]))) if base[s] else j[s] for s in STATS}
            ajustado = True
        stats, recortado = _recortar(stats, cur[piso])
        anterior = j['npc_type']
        usados.add(j['npc_type'])
        salida.append({'piso': piso, 'npc_type': j['npc_type'], 'nombre': j['nombre'], 'nivel': piso,
                       'nivel_original': j['nivel'], 'ajustado': ajustado or recortado, **stats})
    return salida


def main():
    p = pisos()
    datos = {'_nota': 'Generado por tools/generar_torre_babel.py: un jefe por piso, del nivel del piso. '
                      '"ajustado" = jefe de otro nivel con sus stats escalados a la curva del piso.',
             'pisos': p}
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('escrito', SALIDA.relative_to(RAIZ), '-', sum(1 for x in p if not x['ajustado']), 'jefes tal cual,',
          sum(1 for x in p if x['ajustado']), 'ajustados')
    for x in p:
        print('%2d %-22s %s hp %7d atk %5d def %5d' % (x['piso'], x['nombre'][:22],
              'aj' if x['ajustado'] else '  ', x['hp'], x['atk'], x['def']))


if __name__ == '__main__':
    main()
