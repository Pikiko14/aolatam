"""Tareas del Angel Pass que se pueden hacer hoy en el servidor (nivel 60): parches/extras/setting/battlepasstask.xml y
los dos textos de parches/extras/setting/eng/string.xml que cambian.

Pedido del usuario (15/11/2026): "cambia las misiones por misiones que se puedan hacer en nuestro server actualmente
lvl 60: ir a raid por ejemplo semanales, diaria jugar torre de babel".

El cliente arma el texto de cada tarea con una plantilla fija por regla (string.xml 3863..3888) y no hay ninguna de
Raid ni de Torre de Babel, asi que se reutilizan dos reglas que ya no se usan, cambiando su plantilla:
  * 參與奧塔類 (Olympus Tower, 3871) -> "Play the Tower of Babel %d times"   (torre_babel.iniciar)
  * 參與紅白類 (Holy Battlefield, 3869) -> "Join the Raid %d times"          (raid.entrar)
El resto son reglas que el servidor ya cuenta (app._pase_evento): monstruos por raza, mascotas, fusion, granja, totem,
login y "completa X de exp de pase". Fuera las que no cuenta (Elementary, Olympus, GvG, Arena, Star Sign, recolectar,
producir, pedidos, baile...).

Los ids siguen dentro del rango de cada grupo del original, y solo se tocan los cuatro grupos de la temporada.

    python tools/pase_tareas.py
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

ORIGEN_TAREAS = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'battlepasstask.xml'
ORIGEN_TEXTOS = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'string.xml'
DESTINO_TAREAS = RAIZ / 'parches' / 'extras' / 'setting' / 'battlepasstask.xml'
DESTINO_TEXTOS = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'string.xml'

BABEL, RAID = '參與奧塔類', '參與紅白類'
TEXTOS = {3871: 'Play the Tower of Babel %d times', 3869: 'Join the Raid %d times'}

RAZAS = (1, 2, 3, 4, 5, 6)                 # 人型 動物 植物 能量 不死 惡魔 (monster.xml 系別)


def _tareas(lista):
    """[(regla, exp, param1, param2 o None)] -> filas con su id; se pasa la lista sin ids."""
    return lista


# (regla, exp, 動態參數1, 動態參數2)
# Sin granja de momento ("elimina estas misiones y agregas otras, no tendremos farm de momento", 16/11/2026): fuera
# regar, abonar, cosechar y plantar. Tampoco mascotas ni fusion (Capture Pet / Perform Fusion: "quita esto tambien",
# 16/11/2026). La temporada sortea 7 diarias, asi que la septima es la Torre de Babel x3.
DIARIAS_AZAR = [('打怪類', 10, 50, r) for r in RAZAS] + [(BABEL, 20, 3, None)]
DIARIAS_FIJAS = [(BABEL, 20, 1, None), ('登入遊戲類', 10, 1, None), ('完成通行證任務類', 20, 70, None)]
SEMANALES_AZAR = ([('打怪類', 50, 200, r) for r in RAZAS] +
                  [('參與圖騰戰類', 50, 1, None), (BABEL, 50, 5, None)])
SEMANALES_FIJAS = [('登入遊戲類', 30, 5, None), (RAID, 70, 1, None), ('完成通行證任務類', 150, 800, None)]


def _fila(id_, grupo, t):
    regla, exp, p1, p2 = t
    s = '<battlepasstask 編號="%d" 群組編號="%d" 規則="%s" 經驗值="%d" 動態參數1="%d"' % (id_, grupo, regla, exp, p1)
    if p2 is not None:
        s += ' 動態參數2="%d"' % p2
    return s + '/>'


def generar():
    import pase
    tem = pase.temporada()
    grupos = {
        int(tem['每日隨機任務群組ID']): DIARIAS_AZAR, int(tem['每日固定任務群組ID']): DIARIAS_FIJAS,
        int(tem['每週隨機任務群組ID']): SEMANALES_AZAR, int(tem['每週固定任務群組ID']): SEMANALES_FIJAS,
    }
    assert len(DIARIAS_AZAR) >= int(tem['每日隨機任務數量']) and len(SEMANALES_AZAR) >= int(tem['每週隨機任務數量'])
    texto = ORIGEN_TAREAS.read_bytes().decode('utf-8')
    filas = re.findall(r'\t<battlepasstask [^>]*/>\r?\n', texto)
    # los ids que tenia cada grupo, para reutilizarlos en orden
    ids = {}
    for f in filas:
        g = int(re.search(r'群組編號="(\d+)"', f).group(1))
        ids.setdefault(g, []).append(int(re.search(r'編號="(\d+)"', f).group(1)))
    for g, lista in grupos.items():
        assert len(lista) <= len(ids[g]), (g, len(lista), len(ids[g]))
    nuevas, puestos = [], set()
    for f in filas:
        g = int(re.search(r'群組編號="(\d+)"', f).group(1))
        if g not in grupos:
            nuevas.append(f)
        elif g not in puestos:
            puestos.add(g)
            fin = '\r\n' if f.endswith('\r\n') else '\n'
            nuevas += ['\t' + _fila(i, g, t) + fin for i, t in zip(ids[g], grupos[g])]
    cuerpo = ''.join(nuevas)
    ini = texto.index(filas[0])
    fin = texto.rindex(filas[-1]) + len(filas[-1])
    DESTINO_TAREAS.parent.mkdir(parents=True, exist_ok=True)
    DESTINO_TAREAS.write_bytes((texto[:ini] + cuerpo + texto[fin:]).encode('utf-8'))

    textos = ORIGEN_TEXTOS.read_bytes().decode('utf-8')
    for n, t in TEXTOS.items():
        textos, k = re.subn(r'(<字串 編號="%d" 文字=")[^"]*(")' % n, r'\g<1>%s\g<2>' % t, textos)
        assert k == 1, n
    DESTINO_TEXTOS.parent.mkdir(parents=True, exist_ok=True)
    DESTINO_TEXTOS.write_bytes(textos.encode('utf-8'))


if __name__ == '__main__':
    generar()
    print('battlepasstask.xml y string.xml en parches/extras/setting')
