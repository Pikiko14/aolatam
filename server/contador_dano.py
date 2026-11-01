"""Ranking de dano al morir un jefe (pedido del usuario el 31/10/2026).

Monstruo.registrar_dano ya lleva cuanto le hizo cada personaje (dano_por, por char_id; la mascota y las invocaciones
cuentan para su dueno). Al morir un jefe se manda a todos los de la sala el cartel que cruza la parte de arriba de
la pantalla (totem_war.cartel_deslizante, 0x0128 canal 0), que tambien queda en el chat:

    Dragonkin Moowad defeated! 1. Impacty 45,230 (38%)  2. Baco 31,100 (26%)  3. Nubyx 20,050 (17%)
"""
import combate

TOP = 3


def es_jefe(m) -> bool:
    import instancia_oscura
    tipo = int(getattr(m, 'npc_type', 0) or 0)
    return combate.es_jefe(tipo) or tipo in instancia_oscura._tipos_jefe()


def texto(m, nombres) -> str:
    """El cartel; `nombres` es {char_id: nombre}. '' si nadie le hizo dano."""
    dano = {int(k): int(v) for k, v in (getattr(m, 'dano_por', None) or {}).items() if int(v) > 0}
    total = sum(dano.values())
    if not total:
        return ''
    filas = sorted(dano.items(), key=lambda kv: -kv[1])[:TOP]
    partes = ['%d. %s %s (%d%%)' % (i, nombres.get(cid, '?'), format(d, ',d'), round(100.0 * d / total))
              for i, (cid, d) in enumerate(filas, 1)]
    return '%s defeated! %s' % (getattr(m, 'nombre', '') or 'Boss', '  '.join(partes))


def anunciar(sesiones, m):
    """Manda el ranking a `sesiones` si `m` es un jefe."""
    if not es_jefe(m):
        return
    sesiones = [s for s in sesiones if getattr(s, 'personaje', None)]
    t = texto(m, {int(s.personaje.char_id): s.personaje.nombre for s in sesiones})
    if not t:
        return
    import totem_war
    pkt = totem_war.cartel_deslizante(t)
    for s in sesiones:
        try:
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(pkt)
            if hasattr(s, 'volcar'):
                s.volcar()
        except Exception:
            pass
