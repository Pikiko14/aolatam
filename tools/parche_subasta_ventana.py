"""La ventana de la casa de subastas: el tablon 3501 de wnd03.xml ("Advertise for items") rehecho (02/11/2026).

El tablon es de IGG y nunca funciono: el exe no tiene codigo para el (solo game.adtradeselectchange, que pone el
texto de una lista), ningun script lo abre y la mitad de sus botones no tienen OnCommand. Aqui se deja como ventana
de subasta; la logica la pone server/lua/subasta.lua, que el servidor manda por el canal 0x01A0
(tools/parche_canal_lua.py, server/canal_lua.py), y los datos server/subasta_ventana.py.

Lo que cambia en el XML (solo dentro de la ventana 3501):
- la lista 3530 con texto oscuro (fcolor 105, el de los desplegables): con el 103 de antes, texto claro sobre su
  fondo blanco, las filas no se veian. Baja 17 px para dejar sitio a las cabeceras y avisa al elegir una fila.
- las etiquetas del pregonero (3512..3517) pasan a ser las cabeceras de las columnas y la linea de estado; se
  ocultan el susurro, la carta, Sell/Buy y el peso.
- los botones de pagina (3531, 3533), de cantidad (3537, 3539) y el de aceptar (3540) llevan su OnCommand.

    python tools/parche_subasta_ventana.py
    python tools/publicar_setting.py wnd03.xml --sin-copiar      # parche + VPS
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'wnd03.xml'
SALIDA = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd03.xml'

# Columnas de la lista (cols=4 en 783 px): el cliente las reparte a partes iguales.
X_COLUMNAS = (10, 206, 402, 598)

# id: {atributo: valor}. 'title' y 'range' se reemplazan; None quita el atributo.
ATRIBUTOS = {
    3501: {'title': 'Auction House'},
    3502: {'title': 'All'},
    3503: {'title': 'Mine'},
    3512: {'title': 'Item', 'range': '%d,43,120,14' % X_COLUMNAS[0]},
    3514: {'title': 'Qty.', 'range': '%d,43,60,14' % X_COLUMNAS[1]},
    3516: {'title': 'Price', 'range': '%d,43,80,14' % X_COLUMNAS[2]},
    3513: {'title': 'Seller', 'range': '%d,43,120,14' % X_COLUMNAS[3]},
    3517: {'title': 'Pick an item, set Qty. and press the check to buy.', 'range': '90,449,380,14'},
    3523: {'title': 'Category'},
    3524: {'title': 'All'},
    3526: {'title': 'Level'},
    3527: {'title': 'All'},
    3530: {'range': '6,60,783,340', 'fcolor': '105'},
    3532: {'title': '1 / 1'},
    3538: {'title': '1'},
}
OCULTAS = (3515, 3518, 3519, 3520, 3521, 3522, 3535, 3542)
# Lo nuevo de la pestana Mine, para publicar desde la ventana (02/11/2026): una casilla donde se suelta un objeto de
# la mochila (la 484 es la de las casillas del juego), su nombre y el precio. Van ocultos: los ensena el Lua en Mine.
NUEVAS = (
    '<window class="WND_CLASS_BUTTON" id="3590" range="8,404,36,36" icon="484" fcolor="103" font="3" tpos="0,26" '
    'tooltip="10040" tooltext="Drag an item from your backpack here to sell it">',
    '    <style wsDrop="" wsTab="" />',
    '    <OnDrop>OnSubastaSoltar</OnDrop>',
    '    <OnCommand>OnSubastaQuitar</OnCommand>',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="3591" range="52,406,330,14" title="Drag an item from your backpack to the box." '
    'fcolor="103" font="1">',
    '    <style ssVCenter="" />',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="3592" range="52,425,60,14" title="Price each" fcolor="103" font="1">',
    '    <style ssVCenter="" />',
    '</window>',
    '<window class="WND_CLASS_EDIT" id="3593" range="118,424,120,15" bcolor="102" fcolor="105" font="1" tpos="2,1" '
    'limit="10">',
    '    <style esNumber="" esVCenter="" wsTab="" />',
    '</window>',
)
IDS_NUEVAS = (3590, 3591, 3592, 3593)

MANEJADORES = {
    3530: 'OnSubastaFila',
    3531: 'OnSubastaPagAnt',
    3533: 'OnSubastaPagSig',
    3537: 'OnSubastaCantMenos',
    3539: 'OnSubastaCantMas',
    3540: 'OnSubastaAceptar',
}


def _cambiar_etiqueta(etiqueta: str, cambios: dict) -> str:
    for k, v in cambios.items():
        patron = r'\s%s="[^"]*"' % re.escape(k)
        if v is None:
            etiqueta = re.sub(patron, '', etiqueta)
        elif re.search(patron, etiqueta):
            etiqueta = re.sub(patron, lambda m: ' %s="%s"' % (k, v), etiqueta, count=1)
        else:
            etiqueta = re.sub(r'\s*>$', lambda m: ' %s="%s">' % (k, v), etiqueta, count=1)
    return etiqueta


def generar(texto: str) -> str:
    ids = set(ATRIBUTOS) | set(OCULTAS) | set(MANEJADORES)
    hechos = set()

    def tocar(m):
        bloque = m.group(0)
        wid = int(m.group(2))
        if wid not in ids:
            return bloque
        hechos.add(wid)
        inicio = re.match(r'[ \t]*<window [^>]*>', bloque).group(0)
        nuevo = _cambiar_etiqueta(inicio, ATRIBUTOS.get(wid, {}))
        bloque = nuevo + bloque[len(inicio):]
        if wid in OCULTAS:
            bloque = re.sub(r'(<style[^>]*?)\swsVisible=""', r'\1', bloque, count=1)
        if wid in MANEJADORES:
            bloque = re.sub(r'\s*<OnCommand>[^<]*</OnCommand>', '', bloque)
            sangria = re.match(r'[ \t]*', bloque).group(0)
            nl = '\r\n' if '\r\n' in bloque else '\n'
            bloque = re.sub(r'[ \t]*(</window>)$', lambda m2: '%s    <OnCommand>%s</OnCommand>%s%s%s'
                            % (sangria, MANEJADORES[wid], nl, sangria, m2.group(1)), bloque.rstrip(' \t'))
        return bloque

    # Cada <window ...> ... </window> que no anida otra ventana (los de la 3501 son hojas o solo llevan <child>).
    salida = re.sub(r'([ \t]*<window [^>]*\bid="(\d+)"[^>]*>(?:(?!<window )[\s\S])*?</window>)', tocar, texto)
    # La pestana 3511 los lleva como hijos, y van definidos justo detras de ella.
    m = re.search(r'([ \t]*)<window class="WND_CLASS_BASE"[^>]*\bid="3511"[^>]*>[\s\S]*?</window>', salida)
    if not m:
        raise SystemExit('no esta la pestana 3511')
    sangria, bloque = m.group(1), m.group(0)
    nl = '\r\n' if '\r\n' in bloque else '\n'
    hijos = ''.join('%s    <child>%d</child>%s' % (sangria, i, nl) for i in IDS_NUEVAS)
    bloque = re.sub(r'[ \t]*</window>$', lambda m2: hijos + sangria + '</window>', bloque)
    nuevas = ''.join(sangria + linea + nl for linea in NUEVAS)
    salida = salida[:m.start()] + bloque + nl + nuevas.rstrip('\r\n') + salida[m.end():]
    faltan = ids - hechos
    if faltan:
        raise SystemExit('no se encontraron en wnd03.xml: %s' % sorted(faltan))
    return salida


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    crudo = ORIGEN.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nuevo = generar(texto)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes((b'\xef\xbb\xbf' if bom else b'') + nuevo.encode('utf-8'))
    print('escrito', SALIDA.relative_to(RAIZ))


if __name__ == '__main__':
    main()
