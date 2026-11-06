"""El equipo de nivel 1 a 60 se vende a la tienda por 100 a 6.000 de oro segun su nivel.

Pedido del usuario el 04/11/2026 (1.000 a 6.000) y el 05/11/2026 ("vender gear de lvl 1 a 60 en 100 a 6k gold"): en linea
recta del nivel 1 al 60. Solo sube el precio (monturas y robots, que ya valen mas, quedan igual) y solo para equipo que
NO se compra con oro ni con AG: lo que venden las tiendas NPC (shop.xml: una Dagger de 35 de oro se venderia por mas,
oro infinito) y lo del Item Mall se queda con su precio de siempre. La municion y lo que no se equipa tampoco.

Lo usan app._precio_venta (lo que paga el servidor) y cliente_local (el 收購價格 de los item*.xml del parche, que es lo
que el cliente ENSEÑA en la tienda: sin el se veia el precio viejo y parecia que no funcionaba).
"""
import logging
import pathlib
import re

log = logging.getLogger('venta_nivel')

VENTA_POR_NIVEL = ((1, 100), (60, 6000))
_COMPRABLES = None


def items_comprables():
    """Los items que se compran en tiendas NPC (shop.xml) o en los Item Mall (item_mall.json, recent_mall.json)."""
    global _COMPRABLES
    if _COMPRABLES is not None:
        return _COMPRABLES
    ids = set()
    raiz = pathlib.Path(__file__).parent.parent
    try:
        texto = (raiz / 'extracted_paks' / 'update26' / 'setting' / 'shop.xml').read_text(encoding='utf-8-sig', errors='ignore')
        ids.update(int(x) for x in re.findall(r'<item\d+>\s*(\d+)\s*</item\d+>', texto))
    except OSError:
        log.warning('venta por nivel: no se pudo leer shop.xml; no se aplica a nada')
        return None

    def _recoger(nodo):
        if isinstance(nodo, dict):
            for k, v in nodo.items():
                if k in ('item', 'item_id', 'id_item') and str(v).isdigit():
                    ids.add(int(v))
                else:
                    _recoger(v)
        elif isinstance(nodo, list):
            for v in nodo:
                _recoger(v)
    for modulo in ('item_mall', 'recent_mall'):
        try:
            _recoger(__import__(modulo).datos())
        except Exception:
            log.exception('venta por nivel: catalogo de %s', modulo)
    _COMPRABLES = ids
    return ids


def precio(item_id) -> int:
    """El minimo que paga la tienda por equipo de nivel 1..60 que no se compra (0 si no aplica)."""
    import inventario as _iv
    try:
        item_id = int(item_id or 0)
        if not item_id or _iv.ranura_equipo_de(item_id) is None or _iv.es_municion(item_id):
            return 0
        nivel = int(_iv._col_item(item_id, '等級限制') or 0)
    except Exception:
        return 0
    (n0, p0), (n1, p1) = VENTA_POR_NIVEL
    if not n0 <= nivel <= n1:
        return 0
    comprables = items_comprables()
    if comprables is None or item_id in comprables:
        return 0
    return int(round((p0 + (nivel - n0) * (p1 - p0) / (n1 - n0)) / 10.0)) * 10
