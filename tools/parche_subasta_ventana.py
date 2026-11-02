"""La ventana de la casa de subastas: el tablon 3501 de wnd03.xml ("Advertise for items") rehecho (02/11/2026).

El tablon es de IGG y nunca funciono: el exe no tiene codigo para el (solo game.adtradeselectchange, que pone el
texto de una lista), ningun script lo abre y la mitad de sus botones no tienen OnCommand. Aqui se deja como ventana
de subasta; la logica la pone server/lua/subasta.lua, que el servidor manda por el canal 0x01A0
(tools/parche_canal_lua.py, server/canal_lua.py), y los datos server/subasta_ventana.py.

Lo que cambia en el XML (solo dentro de la ventana 3501). El fondo de la pestana (icono 3511, shape/wnd01/w030_01)
es una REJILLA de 10 filas x 4 columnas, cada celda con su casilla de objeto y su caja de texto, y arriba a la
izquierda unas cajas de datos; todo eso ya viene dibujado, asi que la ventana se arma encima:
- la lista 3530 vuelve a su sitio sobre la rejilla y SIN fondo (el bcolor 102 la tapaba de blanco): una fila por
  publicacion, con el icono del objeto en la primera casilla, y texto claro sobre las cajas azules.
- arriba a la izquierda, la fila de vender de la pestana Mine: la casilla donde se suelta el objeto (3590), su
  nombre (3591) y el precio (3593) en las cajas que ya estan dibujadas.
- los dos botones de arriba (susurro y carta) susurran al vendedor y refrescan; los dos circulos (Sell/Buy) ordenan
  por lo mas nuevo o lo mas barato; el peso (3535) dice cuantas publicaciones hay.
- los botones de pagina (3531, 3533), de cantidad (3537, 3539) y el de aceptar (3540) llevan su OnCommand.

    python tools/parche_subasta_ventana.py
    python tools/publicar_setting.py wnd03.xml --sin-copiar      # parche + VPS
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# El original de update23.pak, guardado aparte: extracted_paks no sirve de base, porque el servidor local lo
# sincroniza con el cliente al arrancar y alli ya esta el wnd03.xml de este parche.
ORIGEN = RAIZ / 'tools' / 'originales' / 'wnd03.xml'
SALIDA = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd03.xml'

# id: {atributo: valor}. 'title' y 'range' se reemplazan; None quita el atributo. Los textos los pone tambien el Lua:
# wndtext03.xml (la traduccion) pisa los title de aqui.
ATRIBUTOS = {
    3501: {'title': 'Auction House'},
    # Las pestanas con el icono del TEMA del cliente (2734, log/btn140, el de los botones "Set"): "que las pestanas
    # sean del color configurado en el cliente" (02/11/2026). Las 3084/3085 de antes eran naranja y gris fijos.
    3502: {'title': 'All', 'range': '9,442,32,17', 'icon': str(2734)},
    3503: {'title': 'Mine', 'range': '47,442,32,17', 'icon': str(2734)},
    3517: {'title': 'Pick an item and press the check to buy it.', 'range': '88,449,370,14'},
    3522: {'title': 'New'},
    3542: {'title': 'Cheap'},
    3523: {'title': 'Category'},
    3524: {'title': 'All'},
    3526: {'title': 'Level'},
    3527: {'title': 'All'},
    3530: {'bcolor': None, 'fcolor': '103'},
    3532: {'title': '1 / 1'},
    3535: {'title': '', 'fcolor': '103', 'font': '1'},
    3538: {'title': '1'},
    # Las flechas de pagina y de cantidad: las 3043/3044 (btn057/btn059) no estan en el cliente y salian en blanco;
    # las 2569/2571 (log/btn134, btn133) son flechas del mismo tamano que si estan.
    3531: {'icon': '2569'}, 3537: {'icon': '2569'},
    3533: {'icon': '2571'}, 3539: {'icon': '2571'},
}
OCULTAS = (3512, 3513, 3514, 3515, 3516)
# id: estilo nuevo entero (el <style .../>), para los que cambian de clase.
# (La cantidad de abajo, 3538, se probo como WND_CLASS_EDIT y salia un numero sin sentido: se queda STATIC y para
# vender hay un campo propio, 3576.)
# La lista sin lsCheck/lsSCheck: con ellos el cliente le pone una columna de casillas detras del nombre, que salia
# con numeros sin sentido y empujaba las demas (y el vendedor quedaba fuera). Las listas nativas que se pulsan
# (3582, 3587) tampoco los llevan.
ESTILOS = {3530: 'wsVisible="" lsVCenter="" lsReport="" wsTab=""'}
# Lo de vender, sobre las cajas de arriba a la izquierda del fondo: la casilla con el objeto elegido (3590, icono 484 =
# w011_2, la casilla vacia del juego), su nombre (3591) y el precio (3593). NO se arrastra: el juego no llama al OnDrop
# de estas ventanas (ni con BUTTON ni con ITEMBUTTON, ni en la lista; probado el 02/11/2026). En su lugar la pestana
# Sell (3594) ensena la mochila en la rejilla y se elige con un clic. La casilla y el precio solo se ven en Sell.
NUEVAS = (
    '<window class="WND_CLASS_BUTTON" id="3590" range="4,2,36,36" icon="484" fcolor="103" font="3" tpos="0,26" '
    'tooltip="10040" tooltext="The item you are selling">',
    '    <style wsTab="" />',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="3591" range="46,5,186,14" title="" fcolor="103" font="1">',
    '    <style wsVisible="" ssVCenter="" />',
    '</window>',
    '<window class="WND_CLASS_EDIT" id="3593" range="46,23,66,12" fcolor="103" font="1" tpos="1,0" limit="10">',
    '    <style esNumber="" esVCenter="" wsTab="" />',
    '</window>',
    # La cantidad a vender, en la cajita de la derecha (183..235): mismo tipo de campo que el precio, que si funciona.
    '<window class="WND_CLASS_EDIT" id="3576" range="186,23,46,12" fcolor="103" font="1" tpos="1,0" limit="5">',
    '    <style esNumber="" esVCenter="" wsTab="" />',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="3592" range="118,22,62,14" title="G each" fcolor="103" font="1">',
    '    <style ssVCenter="" />',
    '</window>',
)
# El icono de cada objeto de la lista, en la casilla que el fondo dibuja a la izquierda de cada fila (cada 38 px desde
# y=44). insertitemstrappnum tambien lo pintaba, pero ademas un numero sin sentido junto al nombre: estas casillas son
# botones aparte, sin numero, y al pulsarlos se elige su fila (appdata = la fila; la 0 es la cabecera).
ICONOS_FILAS = (3595, 3596, 3597, 3598, 3599, 3606, 3607, 3608, 3609)
NUEVAS = NUEVAS + tuple(linea for fila, wid in enumerate(ICONOS_FILAS, 1) for linea in (
    '<window class="WND_CLASS_BUTTON" id="%d" range="5,%d,32,32" fcolor="103" font="3" tpos="0,20" appdata="%d" '
    'tooltip="10041" tooldelay="5">' % (wid, 44 + 38 * fila, fila),
    '    <style wsVisible="" wsTab="" />',
    '    <OnCommand>OnSubastaIcono</OnCommand>',
    '    <OnTooltip>OnSubastaTooltip</OnTooltip>',      # la ficha del item, como las recompensas de wnd04.xml
    '</window>',
))
IDS_NUEVAS = (3590, 3591, 3592, 3593, 3576) + ICONOS_FILAS

# El contador de dano (server/medidor_dano.py, server/lua/medidor.lua): un dialogo pequeno y movible con una linea
# de titulo (la pelea o el jefe) y una lista de 8 filas: nombre, dano y %.
MEDIDOR_ID = 59010
MEDIDOR = (
    '<window class="WND_CLASS_DLG_1" range="0,0,236,196" id="59010" title="Damage" fcolor="104" font="1">',
    '    <style wsVisible="" wsMoveable="" />',
    '    <child>59011</child>',
    '    <child>59012</child>',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="59011" range="8,4,220,14" title="" fcolor="103" font="1">',
    '    <style wsVisible="" ssVCenter="" />',
    '</window>',
    '<window class="WND_CLASS_LIST" id="59012" range="6,22,224,166" cols="3" rows="8" gapx="2" gapy="1" tpos="1,1" '
    'fcolor="103" font="1">',
    '    <style wsVisible="" lsVCenter="" lsReport="" />',
    '</window>',
)

# La Torre de Babel (server/torre_babel.py, server/lua/torre.lua): texto, pestanas Solo/Party, el ranking (11 filas:
# la cabecera y el top 10) y el boton de entrar con su rotulo.
TORRE_ID = 59020
TORRE = (
    '<window class="WND_CLASS_DLG_1" range="0,0,300,270" id="59020" title="Tower of Babel" fcolor="104" font="1">',
    '    <style wsVisible="" wsMoveable="" />',
    '    <child>59021</child>',
    '    <child>59022</child>',
    '    <child>59023</child>',
    '    <child>59024</child>',
    '    <child>59025</child>',
    '    <child>59026</child>',
    '    <child>59027</child>',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="59021" range="8,4,284,14" title="" fcolor="103" font="1">',
    '    <style wsVisible="" ssVCenter="" />',
    '</window>',
    '<window class="WND_CLASS_BUTTON" id="59022" range="8,22,32,17" title="Solo" fcolor="103" font="1" icon="59030">',
    '    <style wsVisible="" bsHCenter="" bsVCenter="" wsTab="" />',
    '    <OnCommand>OnTorreSolo</OnCommand>',
    '</window>',
    '<window class="WND_CLASS_BUTTON" id="59023" range="44,22,32,17" title="Party" fcolor="103" font="1" icon="2734">',
    '    <style wsVisible="" bsHCenter="" bsVCenter="" wsTab="" />',
    '    <OnCommand>OnTorreParty</OnCommand>',
    '</window>',
    '<window class="WND_CLASS_LIST" id="59024" range="6,42,288,190" cols="3" rows="11" gapx="2" gapy="1" tpos="1,1" '
    'fcolor="103" font="1">',
    '    <style wsVisible="" lsVCenter="" lsReport="" />',
    '</window>',
    '<window class="WND_CLASS_BUTTON" id="59025" range="266,240,26,18" icon="1154" tooltip="10040" '
    'tooltext="Enter the Tower of Babel">',
    '    <style wsVisible="" wsTab="" />',
    '    <OnCommand>OnTorreEntrar</OnCommand>',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="59026" range="8,224,284,14" title="" fcolor="103" font="1">',
    '    <style wsVisible="" ssVCenter="" />',
    '</window>',
    '<window class="WND_CLASS_STATIC" id="59027" range="170,242,92,14" title="" fcolor="103" font="1">',
    '    <style wsVisible="" ssVCenter="" ssRight="" />',
    '</window>',
)

ICONO_PESTANA_ELEGIDA = 59030
ICONO_PESTANA = (
    r'<icon id="%d" dir="\log\" normal="btn140_d" focus="normal" down="normal" disable="normal">' % ICONO_PESTANA_ELEGIDA,
    '    <attrib ICON_ATTRIB_THEME="" ICON_ATTRIB_FAST="" />',
    '</icon>',
)

# Donde se podia soltar un objeto. Vacio: el juego no llama al OnDrop (ver arriba).
SOLTAR_EN = ()

# La tercera pestana, Sell, junto a All (3502) y Mine (3503) y con su mismo icono de pestana.
PESTANA_VENDER = (
    '<window class="WND_CLASS_BUTTON" id="3594" range="85,442,32,17" title="Sell" fcolor="103" font="1" icon="2734">',
    '    <style wsVisible="" bsHCenter="" bsVCenter="" wsTab="" />',
    '    <OnCommand>OnSubastaPestanaVender</OnCommand>',
    '</window>',
)

MANEJADORES = {
    3518: 'OnSubastaSusurrar',
    3519: 'OnSubastaRefrescar',
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
    ids = set(ATRIBUTOS) | set(OCULTAS) | set(MANEJADORES) | set(SOLTAR_EN) | set(ESTILOS)
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
        if wid in ESTILOS:
            bloque = re.sub(r'<style[^>]*/>', '<style %s />' % ESTILOS[wid], bloque, count=1)
        if wid in OCULTAS:
            bloque = re.sub(r'(<style[^>]*?)\swsVisible=""', r'\1', bloque, count=1)
        if wid in SOLTAR_EN:
            bloque = re.sub(r'(<style)', r'\1 wsDrop=""', bloque, count=1)
            bloque = re.sub(r'(<style[^>]*/>)', r'\1<OnDrop>OnSubastaSoltar</OnDrop>', bloque, count=1)
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
    # La pestana Sell: hija de la 3501, definida detras de la 3503.
    salida = re.sub(r'([ \t]*)<child>3503</child>', lambda m3: m3.group(0) + nl + m3.group(1) + '<child>3594</child>',
                    salida, count=1)
    m = re.search(r'[ \t]*<window [^>]*\bid="3503"[^>]*>[\s\S]*?</window>', salida)
    salida = salida[:m.end()] + ''.join(nl + sangria + linea for linea in PESTANA_VENDER) + salida[m.end():]
    # El contador de dano: ventana suelta, definida detras de la 3501.
    if 'id="%d"' % MEDIDOR_ID not in salida:
        m = re.search(r'[ \t]*<window [^>]*\bid="3501"[^>]*>[\s\S]*?</window>', salida)
        salida = salida[:m.end()] + ''.join(nl + sangria + linea for linea in MEDIDOR) + salida[m.end():]
    if 'id="%d"' % TORRE_ID not in salida:
        m = re.search(r'[ \t]*<window [^>]*\bid="3501"[^>]*>[\s\S]*?</window>', salida)
        salida = salida[:m.end()] + ''.join(nl + sangria + linea for linea in TORRE) + salida[m.end():]
    # La pestana ELEGIDA con el color del tema: el game no trae un icono asi (el 2734 solo lo pone al pulsar), y se
    # define aqui con la imagen de pulsado y el atributo de tema.
    if '<icon id="%d"' % ICONO_PESTANA_ELEGIDA not in salida:
        m = re.search(r'[ \t]*<window [^>]*\bid="3501"[^>]*>[\s\S]*?</window>', salida)
        salida = salida[:m.end()] + ''.join(nl + sangria + linea for linea in ICONO_PESTANA) + salida[m.end():]
    faltan = ids - hechos
    if faltan:
        raise SystemExit('no se encontraron en wnd03.xml: %s' % sorted(faltan))
    return salida


# El boton de la barra de abajo (window 116 de wnd01.xml), a la izquierda del Event Overview (16199) y el Star
# Blessing (50001): "que la auction lo abra un icono de aca" (02/11/2026). Su imagen la dibuja tools/icono_subasta.py.
# El OnCommandSubasta lo define el servidor al entrar (subasta_ventana.SALUDO_LUA): pide abrir la ventana.
WND01 = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd01.xml'
STAGE_XML = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml'
# (id, x en la barra, texto de ayuda, funcion Lua, icono): la subasta y el contador de dano (server/medidor_dano.py,
# 02/11/2026). Las imagenes las dibujan tools/icono_subasta.py y tools/icono_medidor.py.
BOTONES_BARRA = (
    (59001, 310, 'Auction House', 'OnCommandSubasta', 'aolat_ah'),
    (59002, 264, 'Damage meter', 'OnCommandMedidor', 'aolat_dm'),
    (59003, 218, 'Tower of Babel', 'OnCommandTorre', 'aolat_tb'),
)
Y_BARRA = -127      # el pie a -71, como el Event Overview (-139 + 68) y el Star Blessing


def _lineas_boton(wid, x, ayuda, funcion, icono):
    return (
        '<window class="WND_CLASS_BUTTON" range="%d,%d,40,56" id="%d" icon="%d" tooltip="10043" '
        'tooltext="%s">' % (x, Y_BARRA, wid, wid, ayuda),
        '    <style wsVisible="" wsTab="" />',
        '    <OnCommand>%s</OnCommand>' % funcion,
        '</window>',
        r'<icon id="%d" dir="\wnd01\" normal="%s_n" focus="%s_f" down="%s_n" disable="normal" />'
        % (wid, icono, icono, icono),
    )


def boton_en_la_barra(texto: str) -> str:
    """wnd01.xml con los botones propios en la barra (no repite los que ya estan)."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    for wid, x, ayuda, funcion, icono in BOTONES_BARRA:
        if 'id="%d"' % wid in texto:                   # ya esta: solo se pone en su sitio (6 px entre botones)
            texto = re.sub(r'(<window [^>]*?range=")-?\d+,-\d+(,40,56" id="%d")' % wid, r'\g<1>%d,%d\2' % (x, Y_BARRA), texto)
            continue
        m = re.search(r'([ \t]*)<child>50001</child>', texto)
        if not m:
            raise SystemExit('no esta el Star Blessing (50001) en la barra de wnd01.xml')
        texto = texto[:m.end()] + nl + m.group(1) + '<child>%d</child>' % wid + texto[m.end():]
        m = re.search(r'[ \t]*<window [^>]*\bid="50001"[^>]*>[\s\S]*?</window>', texto)
        sangria = re.match(r'[ \t]*', m.group(0)).group(0)
        nuevas = ''.join(nl + sangria + linea for linea in _lineas_boton(wid, x, ayuda, funcion, icono))
        texto = texto[:m.end()] + nuevas + texto[m.end():]
    return texto


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    crudo = ORIGEN.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nuevo = generar(texto)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes((b'\xef\xbb\xbf' if bom else b'') + nuevo.encode('utf-8'))
    print('escrito', SALIDA.relative_to(RAIZ))
    crudo = WND01.read_bytes()
    bom1 = crudo.startswith(b'\xef\xbb\xbf')
    nuevo1 = boton_en_la_barra(crudo.decode('utf-8-sig'))
    WND01.write_bytes((b'\xef\xbb\xbf' if bom1 else b'') + nuevo1.encode('utf-8'))
    print('escrito', WND01.relative_to(RAIZ))
    # El mapa de la Torre de Babel (server/torre_babel.py) con su nombre: es el 133, "年獸洞窟" en el cliente.
    crudo = STAGE_XML.read_bytes()
    bom2 = crudo.startswith(b'\xef\xbb\xbf')
    t = crudo.decode('utf-8-sig')
    t2 = re.sub(r'(<場景 編號="133" 名稱=")[^"]*(")', r'\1Tower of Babel\2', t, count=1)
    if t2 == t and 'Tower of Babel' not in t:
        raise SystemExit('no esta el mapa 133 en stage.xml')
    STAGE_XML.write_bytes((b'\xef\xbb\xbf' if bom2 else b'') + t2.encode('utf-8'))
    print('escrito', STAGE_XML.relative_to(RAIZ))


if __name__ == '__main__':
    main()
