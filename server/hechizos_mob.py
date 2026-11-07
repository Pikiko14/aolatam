"""Hechizos de los monstruos (攻擊法術1..4 de la tabla monster), 06/11/2026.

"hay mob que usan spell pero no los veo que lo usen en el juego": el servidor solo hacia usar sus habilidades a Santa
Clausula; los demas pegaban siempre el golpe normal. 261 bichos de nivel <= 60 traen alguna, de dos clases:

  * fisicas (Basic Beat, Cross Chop, Swiftness Cut...: sin 平均傷害, alcance 1): su golpe x MULT_FISICA;
  * magicas (Fireball Hit, Phoenix Fire, Frozen Spell...: 平均傷害 +- 傷害變數): ataque magico del bicho + el dano
    del hechizo, contra la defensa magica del jugador (Evil Fire Elf: 333 + 168..172).

Las usa en un golpe de cada PROB_POR_DEFECTO salvo que traiga 施展機率.
"""
import random
import sqlite3
import pathlib

PROB_POR_DEFECTO = 0.25
MULT_FISICA = 1.3
DB = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'

_CACHE = {}


def _num(v, defecto=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return defecto


def hechizos(npc_type):
    """(prob, [(magic_id, media, variacion), ...]) de los hechizos de ataque de ese monstruo."""
    npc_type = int(npc_type or 0)
    if npc_type in _CACHE:
        return _CACHE[npc_type]
    res = (0.0, [])
    try:
        con = sqlite3.connect(DB)
        try:
            fila = con.execute('select 攻擊法術1, 攻擊法術2, 攻擊法術3, 攻擊法術4, 施展機率 from monster where id=?',
                               (str(npc_type),)).fetchone()
            if fila:
                lista = []
                for mid in fila[:4]:
                    mid = _num(mid)
                    if mid <= 0:
                        continue
                    g = con.execute('select 平均傷害, 傷害變數, 攻擊型 from magic where id=?', (str(mid),)).fetchone()
                    if g and g[2] == '是':
                        lista.append((mid, _num(g[0]), _num(g[1])))
                if lista:
                    prob = _num(fila[4], -1)
                    res = ((prob / 100.0) if prob >= 0 else PROB_POR_DEFECTO, lista)
        finally:
            con.close()
    except Exception:
        pass
    _CACHE[npc_type] = res
    return res


def elegir(m, rng=None):
    """(magic_id, media, variacion) del hechizo de este golpe, o None (golpe normal)."""
    rng = rng or random
    prob, lista = hechizos(getattr(m, 'npc_type', 0))
    if not lista or rng.random() >= prob:
        return None
    return rng.choice(lista)


def dano(hechizo, m, defensa_fisica, defensa_magica, rng=None):
    """El dano al jugador del hechizo elegido."""
    import combate as cb
    rng = rng or random
    _mid, media, var = hechizo
    if media > 0:
        base = int(getattr(m, 'matk', 0) or 0) + media + rng.randint(-var, var)
        return cb.dano_recibido(base, int(defensa_magica))
    return cb.dano_recibido(int(m.pegar() * MULT_FISICA), int(defensa_fisica))
