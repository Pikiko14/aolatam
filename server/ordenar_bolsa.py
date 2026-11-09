"""Ordenar el Prop y la Backpack por categoria (09/11/2026: "necesitamos agregar un ordenador de mochila y bag, coloca
el icono donde esta el mouse y que ordene por categorias de items").

El boton va en la barra de titulo de cada ventana (tools/parche_ordenar_bolsa.py) y manda game.netcommand(ACCION, 1|2):
c2s 0x0016 [ACCION][u32 1 = Prop, 2 = Backpack]. Lo aplica app._ordenar_bolsa.

EL ORDEN es el de las categorias del propio cliente (los <DEFINE> de item.xml: 一般 0, 頭飾 2, 衣服 3 ... 寵物寶石 80),
dentro de cada una por id y los montones grandes primero. Los montones del mismo objeto se juntan hasta 999 si no llevan
estado propio (mejoras, caducidad, marca del Maple Mark...). Las mascotas no se mueven: tienen ficha y sala propias.
"""
ACCION = 200
PROP, MOCHILA = 1, 2
TOPE_MONTON = 999

ORDEN_CATEGORIA = {
    '一般': 0, '金錢': 1, '頭飾': 2, '衣服': 3, '手套': 4, '鞋子': 5, '飾品': 6, '背包': 7, '披風': 8, '劍': 9, '刀': 10,
    '斧': 11, '錘': 12, '槍': 13, '杖': 14, '弓箭': 15, '彈弓': 16, '盾': 17, '卷軸': 18, '配方': 19, '鐵鍬': 20,
    '鐮刀': 21, '釣竿': 22, '寵物': 23, '機甲': 24, '座騎': 25, '箭矢': 26, '彈藥': 27, '染劑': 28, '寶石': 29, '寶圖': 30,
    '任務': 31, '隱藏': 32, '紅包': 33, '附魔': 34, '禮物': 35, '地圖碎片': 36, '打孔道具': 37, '強化道具': 38,
    '小遊戲道具': 39, '機甲零件': 40, '防禦塔': 41, '計時道具': 42, 'DNA道具': 43, '訂單': 44, '表情卡': 45, '紙娃娃': 46,
    '徽章': 47, '特殊碎片': 48, '扭蛋': 49, '強化飼料': 50, '卡片': 51, '寵物復活': 52, '幸運骰': 53, '寵物強化': 54,
    '儲值道具': 55, '字卡': 56, '房屋': 57, '傢俱': 58, '怪物蛋': 59, '魔力骰': 60, '房屋外觀': 61, '經驗卷': 62, '影刃': 63,
    '小鋼珠': 64, '挖寶石道具': 65, '融合劑': 66, '抓寵空蛋': 67, '經驗球': 68, '技能經驗球': 69, '寵物經驗球': 70,
    '魯易浮標': 71, '農場種子': 72, '加速肥料': 73, '驅蟲劑': 74, '寵物武器': 75, '寵物防具': 76, '寵物飾品': 77,
    '星盤金幣抽': 78, '星盤賓果': 79, '寵物寶石': 80, '對話泡泡': 81, '更名道具': 82,
}


def plan(casillas, objetos, categoria, apilable, fija):
    """El nuevo reparto: {casilla_destino: (casilla_origen, item, cantidad)}.

    casillas: las casillas de la ventana, en su orden. objetos: {casilla: (item, cantidad)} de las que tienen algo.
    categoria(item) -> str, apilable(item) -> bool, fija(casilla) -> True si no se mueve (mascotas).
    Las casillas de origen que se quedan sin nada (montones juntados) no aparecen en el resultado.
    """
    fijas = {c for c in casillas if c in objetos and fija(c)}
    sueltas = [c for c in casillas if c in objetos and c not in fijas]
    # Montones que se pueden juntar: mismo objeto, apilable y sin estado propio (fija() ya cubre lo que no se toca;
    # lo que lleva estado lo marca `apilable` como no apilable para esa casilla).
    unidades, grupos = [], {}
    for c in sueltas:
        item, n = objetos[c]
        if apilable(c):
            grupos.setdefault(item, []).append(c)
        else:
            unidades.append((c, item, int(n)))
    for item, origenes in grupos.items():
        total = sum(int(objetos[c][1]) for c in origenes)
        for i, c in enumerate(origenes):
            if total <= 0:
                break
            n = min(TOPE_MONTON, total)
            unidades.append((c, item, n))
            total -= n
    unidades.sort(key=lambda u: (ORDEN_CATEGORIA.get(categoria(u[1]), 999), u[1], -u[2], u[0]))
    libres = [c for c in casillas if c not in fijas]
    return {destino: u for destino, u in zip(libres, unidades)}
