"""La ventana y el boton de la raid Flamefang (server/raid.py, server/lua/raid.lua), 11/11/2026.

Deja en parches/extras:
  shape/wnd01/aolat_rd_n.shp, _f.shp   el icono de la barra (espadas cruzadas entre llamas), al estilo de los nativos
                                       (tools/icono_subasta.al_estilo_nativo)
  shape/wnd01/aolat_raid_fondo.shp      el fondo de la ventana con el color del tema (como tools/parche_arbol_mascotas)
  setting/eng/wnd01.xml                el boton 59004 de la barra, a la izquierda del de la Torre de Babel
  setting/eng/wnd03.xml                la ventana 59600: miembros, jefes, invitar por nombre, crear/salir, invitar a la
                                       party, entrar, salir del mapa y aceptar una invitacion

Se puede correr las veces que haga falta: quita lo suyo antes de ponerlo.

    python tools/parche_raid.py
"""
import pathlib
import re
import struct
import sys

from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
from icono_subasta import ANCHO, ALTO, SALIDA, a_shp, al_estilo_nativo  # noqa: E402

ENG = RAIZ / 'parches' / 'extras' / 'setting' / 'eng'
MARCA = 'aolat raid ventana'
BOTON_BARRA, ICONO_BARRA, X_BARRA, Y_BARRA = 59004, 59004, 213, -127
VENTANA, W, H = 59600, 360, 344
TITULO, LISTA, JEFES, NOMBRE, INVITAR = 59601, 59602, 59603, 59606, 59607
CREAR, PARTY, ENTRAR, SALIR_MAPA, ACEPTAR, ESTADO = 59608, 59609, 59610, 59611, 59612, 59613
FONDO, ICONO_FONDO, ARCHIVO_FONDO = 59614, 59615, 'aolat_raid_fondo'
BOTON_TEMA = 12006            # el boton de la ventana System, que sigue el tema
COLOR_FONDO, COLOR_BORDE = 0xd301, 0xf003


def dibujar() -> Image.Image:
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (40, 16, 8, 255)

    def r(*xy):
        return [v * k for v in xy]
    # Llamas detras.
    d.polygon(r(20, 4, 9, 30, 13, 22, 11, 40, 20, 30, 29, 40, 27, 22, 31, 30), fill=(232, 96, 28, 255), outline=borde)
    d.polygon(r(20, 13, 14, 32, 20, 26, 26, 32), fill=(255, 200, 60, 255))
    # Dos espadas cruzadas.
    for a, b in (((8, 46), (30, 14)), ((32, 46), (10, 14))):
        d.line(r(*a, *b), fill=(220, 226, 236, 255), width=3 * k)
        d.line(r(*a, *b), fill=borde, width=k)
    d.line(r(5, 40, 13, 46), fill=(150, 96, 40, 255), width=3 * k)      # empunaduras
    d.line(r(35, 40, 27, 46), fill=(150, 96, 40, 255), width=3 * k)
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def iconos():
    im = al_estilo_nativo(dibujar())
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / 'aolat_rd_n.shp').write_bytes(a_shp(im))
    claro = Image.eval(im.convert('RGBA'), lambda v: min(255, int(v * 1.2)))
    claro.putalpha(im.getchannel('A'))
    (SALIDA / 'aolat_rd_f.shp').write_bytes(a_shp(claro))


def fondo(w=None, h=None) -> bytes:
    import fondos_interfaz as fi
    w, h = w or W, h or H
    cab, bpp, _filas, paleta = fi.leer(fi.del_cliente(r'shape\wnd01\w050_01.shp'))
    liso, borde = struct.pack('<H', COLOR_FONDO), struct.pack('<H', COLOR_BORDE)
    filas = [[(0, borde * w)] if y in (0, h - 1) else [(0, borde + liso * (w - 2) + borde)] for y in range(h)]
    cab = list(cab)
    cab[5] = w
    return fi.escribir(cab, bpp, filas, paleta)


# ---------------------------------------------------------------------------------------------- el panel
# "Podria verse el team asi como si fuera el panel de team pero este seria de raid" (11/11/2026); "el panel de grupo
# se ve muy grande, debe ser mas compacto, no desbordar, tener el color del tema, que con click derecho me de la opcion
# de sacar al personaje" (11/11/2026). 24 filas seguidas (las cabeceras "Group N" ocupan una) que RaidPanel de
# server/lua/raid.lua rellena de arriba abajo; cada fila trae su franja de fondo con el color del tema, asi las que no
# se usan no pintan nada y la ventana se encoge a las que hay. Cada fila tiene un boton transparente cuyo clic
# derecho (OnCommandEx, como el panel de party nativo) abre el menu 60210.
MARCA_PANEL = 'aolat raid panel'
PANEL, PW, FILA, N_FILAS = 59700, 172, 20, 24
PANEL_NOMBRE, PANEL_ROL, PANEL_CORONA, PANEL_VIDA, PANEL_MANA = 59940, 59970, 60000, 60030, 60060
PANEL_ESTADO, PANEL_GRUPO, PANEL_CLIC, PANEL_FRANJA = 60090, 60120, 60150, 60180
PANEL_ICONO_FRANJA = 59841
MENU_PANEL, MENU_NOMBRE, MENU_LIDER, MENU_SACAR = 60210, 60211, 60212, 60213
ICONO_CORONA, ICONO_TANQUE, ICONO_SANADOR, ICONO_DANO = 59850, 59851, 59852, 59853
# Barras propias: las del jugador (159 es la de EXP, rosa; 160 la de vida) miden 100x10 y pisaban la fila de abajo.
BARRA_VIDA, BARRA_MANA, BARRA_PISTA, PANEL_PISTA = 59866, 59867, 59868, 60240
BARRA_W = PW - 8
PH = 2 + N_FILAS * FILA + 4


def franja(w, h) -> bytes:
    """Una franja del fondo del tema (como fondo(), con borde solo a los lados)."""
    import fondos_interfaz as fi
    cab, bpp, _filas, paleta = fi.leer(fi.del_cliente(r'shape\wnd01\w050_01.shp'))
    liso, borde = struct.pack('<H', COLOR_FONDO), struct.pack('<H', COLOR_BORDE)
    filas = [[(0, borde + liso * (w - 2) + borde)] for _y in range(h)]
    cab = list(cab)
    cab[5] = w
    return fi.escribir(cab, bpp, filas, paleta)


def _icono_pequeno(dibujo) -> bytes:

    import mascota_abismo as ma
    k = 4
    im = Image.new('RGBA', (12 * k, 12 * k), (0, 0, 0, 0))
    dibujo(ImageDraw.Draw(im), k)
    im = im.resize((12, 12), Image.LANCZOS)
    return ma._tlhs_suelto(im, r'shape\pet\p001.shp', 0, 0)


def iconos_panel():
    negro = (24, 18, 10, 255)

    def corona(d, k):
        d.polygon([(1 * k, 10 * k), (1 * k, 4 * k), (4 * k, 7 * k), (6 * k, 2 * k), (8 * k, 7 * k), (11 * k, 4 * k),
                   (11 * k, 10 * k)], fill=(250, 200, 40, 255), outline=negro)

    def escudo(d, k):
        d.polygon([(2 * k, 1 * k), (10 * k, 1 * k), (10 * k, 6 * k), (6 * k, 11 * k), (2 * k, 6 * k)],
                  fill=(80, 140, 230, 255), outline=(230, 240, 255, 255))

    def cruz(d, k):
        d.rectangle([4 * k, 1 * k, 8 * k, 11 * k], fill=(60, 210, 70, 255), outline=negro)
        d.rectangle([1 * k, 4 * k, 11 * k, 8 * k], fill=(60, 210, 70, 255), outline=negro)
        d.rectangle([5 * k, 2 * k, 7 * k, 10 * k], fill=(60, 210, 70, 255))

    def espada(d, k):
        d.line([(2 * k, 10 * k), (10 * k, 2 * k)], fill=(230, 230, 240, 255), width=2 * k)
        d.line([(2 * k, 7 * k), (5 * k, 10 * k)], fill=(220, 60, 40, 255), width=2 * k)
    for nombre, dibujo in (('aolat_corona', corona), ('aolat_rol_tanque', escudo), ('aolat_rol_sanador', cruz),
                           ('aolat_rol_dano', espada)):
        (SALIDA / (nombre + '.shp')).write_bytes(_icono_pequeno(dibujo))
    (SALIDA / 'aolat_raid_panel.shp').write_bytes(franja(PW, FILA + 4))
    for nombre, im in barras().items():
        (SALIDA / (nombre + '.shp')).write_bytes(a_shp(im))


def barras() -> dict:
    """La vida (roja, 3 px), el mana (azul, 2 px) y la pista oscura que va detras de las dos (6 px)."""
    def degradado(h, arriba, abajo):
        im = Image.new('RGBA', (BARRA_W, h), (0, 0, 0, 255))
        d = ImageDraw.Draw(im)
        for y in range(h):
            v = y / max(1, h - 1)
            d.line((0, y, BARRA_W, y), fill=tuple(int(arriba[k] + (abajo[k] - arriba[k]) * v) for k in range(3)) + (255,))
        return im
    pista = Image.new('RGBA', (BARRA_W, 6), (16, 10, 8, 255))
    ImageDraw.Draw(pista).line((0, 3, BARRA_W, 3), fill=(4, 2, 2, 255))
    return {'aolat_barra_hp': degradado(3, (255, 96, 80), (180, 24, 20)),
            'aolat_barra_mp': degradado(2, (110, 170, 255), (40, 90, 220)),
            'aolat_barra_pista': pista}


def bloque_panel() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)
    oculto = 'ssVCenter=""'                    # sin wsVisible: el Lua ensena las filas que usa
    # El primer hijo queda encima: los botones del clic derecho van primero, las franjas del fondo al final.
    for i in range(N_FILAS):
        y = 2 + i * FILA
        poner(PANEL_CLIC + i, _w('WND_CLASS_BUTTON', PANEL_CLIC + i, 0, y, PW, FILA, ' appdata="%d"' % i, 'wsTab=""',
                                 '        <OnCommandEx>OnRaidPanelMenu</OnCommandEx>\n'))
    for i in range(N_FILAS):
        y = 2 + i * FILA
        poner(PANEL_CORONA + i, _w('WND_CLASS_BUTTON', PANEL_CORONA + i, 3, y + 1, 12, 12, ' icon="%d"' % ICONO_CORONA, ''))
        poner(PANEL_ROL + i, _w('WND_CLASS_BUTTON', PANEL_ROL + i, PW - 16, y + 1, 12, 12, ' icon="0"', ''))
        poner(PANEL_NOMBRE + i, _w('WND_CLASS_STATIC', PANEL_NOMBRE + i, 17, y, 92, 12,
                                   ' title="" fcolor="103" font="1"', oculto))
        poner(PANEL_ESTADO + i, _w('WND_CLASS_STATIC', PANEL_ESTADO + i, 110, y, 42, 12,
                                   ' title="" fcolor="510" font="1"', oculto + ' ssRight=""'))
        poner(PANEL_GRUPO + i, _w('WND_CLASS_STATIC', PANEL_GRUPO + i, 4, y + 3, PW - 8, 14,
                                  ' title="" fcolor="514" font="1"', oculto))
        # Nombre en y..y+12; vida y+13..15, una raya oscura, mana y+17..18; la fila siguiente empieza en y+20.
        poner(PANEL_VIDA + i, _w('WND_CLASS_PROGRESS', PANEL_VIDA + i, 4, y + 13, BARRA_W, 3,
                                 ' picon="%d"' % BARRA_VIDA, 'psHorizontal=""'))
        poner(PANEL_MANA + i, _w('WND_CLASS_PROGRESS', PANEL_MANA + i, 4, y + 17, BARRA_W, 2,
                                 ' picon="%d"' % BARRA_MANA, 'psHorizontal=""'))
    for i in range(N_FILAS):                   # la pista, debajo de las barras
        poner(PANEL_PISTA + i, _w('WND_CLASS_BASE', PANEL_PISTA + i, 4, 2 + i * FILA + 13, BARRA_W, 6,
                                  ' icon="%d"' % BARRA_PISTA, ''))
    for i in range(N_FILAS):
        poner(PANEL_FRANJA + i, _w('WND_CLASS_BASE', PANEL_FRANJA + i, 0, i * FILA, PW, FILA + 4,
                                   ' icon="%d"' % PANEL_ICONO_FRANJA, ''))
    for wid, archivo, tema in ((PANEL_ICONO_FRANJA, 'aolat_raid_panel', True), (ICONO_CORONA, 'aolat_corona', False),
                               (ICONO_TANQUE, 'aolat_rol_tanque', False), (ICONO_SANADOR, 'aolat_rol_sanador', False),
                               (ICONO_DANO, 'aolat_rol_dano', False), (BARRA_VIDA, 'aolat_barra_hp', False),
                               (BARRA_MANA, 'aolat_barra_mp', False), (BARRA_PISTA, 'aolat_barra_pista', False)):
        ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="normal" down="normal" disable="normal">\n'
                        '%s    </icon>\n' % (wid, archivo, '        <attrib ICON_ATTRIB_THEME="" ICON_ATTRIB_FAST="" />\n'
                                             if tema else ''))
    cab = _cabeza_dlg(PANEL, PW, PH, 'Raid', hijos)
    # El menu del clic derecho, como el del jugador (565): el nombre y lo que puede hacer el lider.
    menu = ('    <window class="WND_CLASS_BASE" id="%d" range="0,0,124,62" fillrange="7, 7,300,100" '
            'puzzle1="10021" puzzle2="10022" puzzle3="10023" puzzle4="10024" puzzle5="10025" puzzle6="10026" '
            'puzzle7="10027" puzzle8="10028" puzzle9="10029">\n'
            '        <style wsVisible="" wsPuzzle="" wsPopup="" wsAutoClose="" />\n'
            '        <child>%d</child>\n        <child>%d</child>\n        <child>%d</child>\n    </window>\n'
            % (MENU_PANEL, MENU_NOMBRE, MENU_LIDER, MENU_SACAR)
            + '    <window class="WND_CLASS_STATIC" id="%d" range="6,7,112,12" title="" fcolor="101" font="1">\n'
              '        <style wsVisible="" />\n    </window>\n' % MENU_NOMBRE
            + ''.join('    <window class="WND_CLASS_BUTTON" range="6,%d,112,12" id="%d" fcolor="106" font="1" '
                      'title="%s">\n        <style wsVisible="" ssVCenter="" wsTab="" />\n'
                      '        <OnCommand>%s</OnCommand>\n    </window>\n' % (y, wid, t, f)
                      for y, wid, t, f in ((25, MENU_LIDER, 'Make leader', 'OnRaidPanelLider'),
                                           (41, MENU_SACAR, 'Remove from raid', 'OnRaidPanelSacar'))))
    return '    <!-- %s -->\n%s%s%s    <!-- /%s -->\n' % (MARCA_PANEL, cab, ''.join(ventanas), menu, MARCA_PANEL)


def _w(clase, wid, x, y, w, h, extra='', estilo='wsVisible=""', cuerpo=''):
    return ('    <window class="%s" id="%d" range="%d,%d,%d,%d"%s>\n        <style %s />\n%s    </window>\n'
            % (clase, wid, x, y, w, h, extra, estilo, cuerpo))


def _texto(wid, x, y, w, titulo=''):
    return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="%s" fcolor="103" font="1"' % titulo,
              'wsVisible="" ssVCenter=""')


def _boton(wid, x, y, titulo, funcion, w=55, visible=True):
    return _w('WND_CLASS_BUTTON', wid, x, y, w, 18, ' fcolor="101" font="1" icon="%d" title="%s"' % (BOTON_TEMA, titulo),
              ('wsVisible="" ' if visible else '') + 'bsHCenter="" bsVCenter="" wsTab=""',
              '        <OnCommand>%s</OnCommand>\n' % funcion)


def bloque_wnd03() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)
    def texto(wid, x, y, w, color=103):
        return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="" fcolor="%d" font="1"' % color,
                  'wsVisible="" ssVCenter=""')
    fila = 318
    poner(INVITAR, _boton(INVITAR, R_INVITAR[2] + 6, R_INVITAR[1] - 1, 'Invite', 'OnRaidInvitar', w=60))
    poner(GUIA_RAID, _boton(GUIA_RAID, R_INVITAR[2] + 70, R_INVITAR[1] - 1, 'Guide', 'OnRaidGuia', w=60))
    poner(CREAR, _boton(CREAR, 8, fila, 'Create', 'OnRaidCrear', w=60))
    poner(PARTY, _boton(PARTY, 72, fila, 'Invite', 'OnRaidParty', w=80))
    poner(ENTRAR, _boton(ENTRAR, 156, fila, 'Enter', 'OnRaidEntrar', w=60))
    poner(SALIR_MAPA, _boton(SALIR_MAPA, 220, fila, 'Exit', 'OnRaidSalirMapa', w=64))
    poner(ACEPTAR, _boton(ACEPTAR, 290, fila, 'Accept', 'OnRaidAceptar', w=74, visible=False))
    poner(NOMBRE, _w('WND_CLASS_EDIT', NOMBRE, R_INVITAR[0] + 4, R_INVITAR[1] + 1, R_INVITAR[2] - R_INVITAR[0] - 8, 14,
                     ' fcolor="103" font="1" tpos="1,0" limit="16"', 'wsVisible="" esVCenter="" wsTab=""'))
    poner(TITULO, texto(TITULO, R_MIEMBROS[0] + 80, R_MIEMBROS[1] + 4, R_MIEMBROS[2] - R_MIEMBROS[0] - 88, 513))
    poner(LISTA, _w('WND_CLASS_LIST', LISTA, R_MIEMBROS[0] + 4, R_MIEMBROS[1] + 24, R_MIEMBROS[2] - R_MIEMBROS[0] - 8,
                    R_MIEMBROS[3] - R_MIEMBROS[1] - 28,
                    ' cols="3" rows="8" gapx="2" gapy="1" tpos="3,1" fcolor="103" font="1"',
                    'wsVisible="" lsVCenter="" lsReport=""'))
    for k in range(3):
        poner(JEFES + k, texto(JEFES + k, 26, R_JEFES[1] + 23 + 17 * k, RW - 40))
    poner(ESTADO, texto(ESTADO, 8, RH - 18, RW - 16, 513))
    poner(BANNER_RAID, _w('WND_CLASS_BASE', BANNER_RAID, R_BANNER[0], R_BANNER[1], R_BANNER[2] - R_BANNER[0], R_BANNER[3] - R_BANNER[1], ' icon="%d"' % ICONO_BANNER_RAID))
    for t in range(N_TEMAS):
        ventanas.append('    <icon id="%d" dir="%swnd01%s" normal="aolat_raid_banr%d" focus="normal" down="normal" '
                        'disable="normal" />\n' % (ICONO_BANNER_RAID + t, chr(92), chr(92), t))
    poner(FONDO, _w('WND_CLASS_BASE', FONDO, 0, 0, RW, RH, ' icon="%d"' % ICONO_FONDO))
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="normal" down="normal" disable="normal" />\n'
                    % (ICONO_FONDO, ARCHIVO_FONDO))
    cab = _cabeza_dlg(VENTANA, RW, RH, 'Flamefang Raid', hijos)
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA, cab, ''.join(ventanas), MARCA)


def _guardar(nombre, cambio):
    ruta = ENG / nombre
    crudo = ruta.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = texto.replace('\r\n', '\n')
    for marca in (MARCA, MARCA_PANEL, MARCA_LISTA, MARCA_GUIA, MARCA_RANKING):
        texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\r?\n' % (marca, marca), '', texto, flags=re.S)
    texto = re.sub(r'\n[ \t]*<child>(%d|%d)</child>' % (BOTON_BARRA, BOTON_MENU), '', texto)
    texto = cambio(texto).replace('\n', nl)
    ruta.write_bytes((b'\xef\xbb\xbf' if bom else b'') + texto.encode('utf-8'))


def _al_final(bloque):
    def cambio(texto):
        fin = texto.rindex('</root>')
        return texto[:fin] + bloque + texto[fin:]
    return cambio


def wnd01(texto):
    """El boton de la barra, hermano de los de la subasta, el medidor y la torre (despues del Star Blessing)."""
    m = re.search(r'([ \t]*)<child>59003</child>', texto)
    if not m:
        raise SystemExit('no esta el boton de la Torre de Babel (59003) en wnd01.xml')
    texto = texto[:m.end()] + '\n' + m.group(1) + '<child>%d</child>' % BOTON_BARRA + texto[m.end():]
    boton = ('    <!-- %s -->\n' % MARCA
             + '    <window class="WND_CLASS_BUTTON" range="%d,%d,40,56" id="%d" icon="%d" tooltip="10043" '
               'tooltext="AOF Raid">\n        <style wsVisible="" wsTab="" />\n'
               '        <OnCommand>OnCommandRaid</OnCommand>\n    </window>\n' % (X_BARRA, Y_BARRA, BOTON_BARRA, ICONO_BARRA)
             + '    <icon id="%d" dir="\\wnd01\\" normal="aolat_rd_n" focus="aolat_rd_f" down="aolat_rd_n" '
               'disable="normal" />\n' % ICONO_BARRA
             + '    <!-- /%s -->\n' % MARCA)
    return _al_final(boton)(texto)


# ---------------------------------------------------------------------------------------------- AOF Raids y el menu
# "Que se pueda invitar al dar click derecho a 1 personaje, si la persona es lider de la raid ... tambien que en vez de
# ser 1 icono por raid, sea un listado de raid, ese nuevo icono de acciones sea AOF raid" (11/11/2026).
MARCA_LISTA = 'aolat raid lista'
LISTA_RAIDS, LW, LH = 59670, 400, 304
LISTA_FILAS, LISTA_ABRIR, LISTA_ESTADO, LISTA_FONDO, LISTA_ICONO_FONDO = 59671, 59672, 59673, 59674, 59675
# "Que se vea mas bonito" (11/11/2026): un banner con los tres jefes, la lista solo con los nombres (las columnas del
# cliente son todas del mismo ancho y el nombre se comia el nivel) y los detalles de la raid elegida a la derecha.
LISTA_NOMBRE, LISTA_NIVEL, LISTA_SEMANA, LISTA_JEFES, LISTA_BOTIN = 59676, 59677, 59678, 59679, 59683  # 59679..82, 83..84
BANNER = (4, 4, 396, 108)
# Los banners por raid, encima del fondo: una ventana en cada sitio y un icono por raid (RaidImagen, RaidGuiaImagen y el
# detalle de AOF Raids en server/lua).
BANNER_LISTA, BANNER_RAID, BANNER_GUIA = 60320, 60321, 60322
ICONO_BANNER_LISTA, ICONO_BANNER_RAID, ICONO_BANNER_GUIA = 60330, 60334, 60338        # + 0..3
PANEL_IZQ, PANEL_DER = (4, 114, 132, 270), (138, 114, 396, 270)
X_DETALLE = PANEL_DER[0] + 8
MENU_JUGADOR, BOTON_MENU = 565, 59660     # el menu de clic derecho sobre un jugador (chat.lua OnClickChatOption)
# Lavamon, Satrixia (delante) y Razorex: (shape\mon\..._Wait.spr, frame de frente, escala).
JEFES_SPR = ((r'M2085\110086', 4, 0.33), (r'M2086\110087', 0, 0.36), (r'M2084\110085', 4, 0.30))


def _sprite(ruta, frame):
    """Un frame del _Wait.spr de un monstruo como RGBA. Los TLHS de tipo 4 (Satrixia) llevan ARGB4444, no paleta."""
    import fondos_interfaz as fi
    import spr_ewsp
    d = fi.del_cliente('shape\\mon\\%s_Wait.spr' % ruta)
    _o, o_t, tam = struct.unpack_from('<3I', d, 80 + 12 * frame)
    b = d[o_t:o_t + tam]
    c = struct.unpack_from('<4s19I', b, 0)
    if c[2] != 4:
        return spr_ewsp.leer(d)[0][frame][0]
    w, h = c[5], c[6]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = im.load()
    for y in range(h):
        p = struct.unpack_from('<I', b, 80 + 4 * y)[0]
        while True:
            cnt, x, src = struct.unpack_from('<HHI', b, p)
            p += 8
            if x == 0xFFFF:
                break
            for j in range(cnt):
                v = struct.unpack_from('<H', b, src + 2 * j)[0]
                px[x + j, y] = (((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, (v >> 12) * 17)
    return im


def _fuente(nombre, tam):
    from PIL import ImageFont
    try:
        return ImageFont.truetype('C:/Windows/Fonts/' + nombre, tam)
    except OSError:
        return ImageFont.load_default()


def _texto_dorado(lienzo, xy, texto, fuente, arriba=(255, 236, 150), abajo=(255, 146, 30)):
    """Texto con degradado dorado, sombra difuminada y contorno oscuro."""
    from PIL import ImageFilter
    w, h = lienzo.size
    sombra = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text(xy, texto, font=fuente, fill=(0, 0, 0, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(2)))
    ImageDraw.Draw(lienzo).text(xy, texto, font=fuente, fill=(70, 20, 6, 255), stroke_width=1,
                                stroke_fill=(70, 20, 6, 255))
    x0, y0, x1, y1 = ImageDraw.Draw(lienzo).textbbox(xy, texto, font=fuente)
    oro = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(oro)
    for y in range(y0, y1 + 1):
        v = (y - y0) / max(1, y1 - y0)
        od.line((0, y, w, y), fill=tuple(int(arriba[k] + (abajo[k] - arriba[k]) * v) for k in range(3)) + (255,))
    mascara = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mascara).text(xy, texto, font=fuente, fill=255)
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    capa.paste(oro, (0, 0), mascara)
    lienzo.alpha_composite(capa)


# 11/11/2026, "que cambie la imagen de la pestana cuando selecciono la raid que quiero": un banner por raid (el orden del
# CATALOGO de server/raid.py), con su cielo, su resplandor, sus chispas y sus tres jefes (el del medio, por delante).
TEMAS = (
    dict(titulo='FLAMEFANG', nivel=60, cielo=((36, 8, 12), (146, 42, 14)), brillo=((255, 110, 20), (190, 50, 10)),
         chispas=((255, 210, 90), (255, 150, 40), (255, 90, 30)), jefes=None),
    dict(titulo='WARRING REALM', nivel=50, cielo=((18, 6, 26), (120, 18, 44)), brillo=((210, 40, 90), (110, 30, 160)),
         chispas=((230, 140, 255), (255, 90, 130), (170, 70, 220)), jefes=(111252, 111243, 110931)),
    dict(titulo='WINTRY REALM', nivel=40, cielo=((6, 12, 40), (70, 130, 190)), brillo=((150, 215, 255), (60, 110, 200)),
         chispas=((255, 255, 255), (210, 235, 255), (160, 205, 255)), jefes=(111144, 111148, 111143)),
    dict(titulo="DRAGON'S LAIR", nivel=30, cielo=((32, 10, 44), (196, 84, 118)), brillo=((255, 150, 190), (180, 60, 140)),
         chispas=((255, 205, 225), (255, 160, 200), (255, 235, 245)), jefes=(111384, 111386, 111385)),
)
N_TEMAS = len(TEMAS)


def _jefe_banner(tema, i, k, bh):
    """(imagen, delante) del jefe i del banner del tema, ya a su tamano."""
    if tema['jefes'] is None:
        ruta, frame, escala = JEFES_SPR[i]
        s = _sprite(ruta, frame)
        escala *= k
    else:
        sprite = tema['jefes'][i]
        s = _sprite('M%d' % (sprite - 108001) + chr(92) + str(sprite), 4)
        s = s.crop(s.getbbox())
        escala = bh * (1.02 if i == 1 else 0.86) / s.height
        escala = min(escala, (120 if i == 1 else 80) * k / s.width)        # que no tapen el titulo
    return s.resize((max(1, int(s.width * escala)), max(1, int(s.height * escala))), Image.LANCZOS)


def _banner(bw=None, bh=None, grande=True, tema=0) -> Image.Image:
    """El banner de la raid `tema` (TEMAS). grande: el de AOF Raids (titulo en dos lineas y la linea de datos); si no,
    una franja con el titulo en una linea y los jefes mas pequenos (la ventana de la raid y la guia)."""
    import random
    from PIL import ImageFilter
    t = TEMAS[tema]
    bw, bh = bw or BANNER[2] - BANNER[0], bh or BANNER[3] - BANNER[1]
    ban = Image.new('RGBA', (bw, bh), (0, 0, 0, 255))
    bd = ImageDraw.Draw(ban)
    (r0, g0, b0), (r1, g1, b1) = t['cielo']
    for y in range(bh):                                         # de noche arriba al color de la raid abajo
        v = y / bh
        bd.line((0, y, bw, y), fill=(int(r0 + (r1 - r0) * v ** 2), int(g0 + (g1 - g0) * v ** 3),
                                     int(b0 + (b1 - b0) * v), 255))
    glow = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((bw * 0.42, bh * 0.30, bw * 1.08, bh * 1.7), fill=t['brillo'][0] + (160,))
    gd.ellipse((-60, bh * 0.70, bw * 0.45, bh * 1.6), fill=t['brillo'][1] + (110,))
    ban.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    rnd = random.Random(902)
    for _ in range(80):                                         # ascuas
        x, y, r = rnd.uniform(0, bw), rnd.uniform(0, bh), rnd.choice((1, 1, 1, 2))
        c = rnd.choice(t['chispas'])
        bd.ellipse((x, y, x + r, y + r), fill=c + (255,))
    k = 1.0 if grande else 0.62
    xs = (bw - 152 * k, bw - 94 * k, bw - 36 * k)
    orden = ((0, False), (2, False), (1, True))                 # el del medio el ultimo, por delante
    for i, delante in orden:
        s = _jefe_banner(t, i, k, bh)
        if not delante:                                         # los de los lados un poco en penumbra
            oscuro = Image.new('RGBA', s.size, (20, 6, 4, 0))
            oscuro.putalpha(s.getchannel('A').point(lambda a: a // 5))
            s = Image.alpha_composite(s, oscuro)
        x, y = int(xs[i] - s.width / 2), bh - s.height + (8 if delante else 4)
        if y < 0:
            s, y = s.crop((0, -y, s.width, s.height)), 0
        ban.alpha_composite(s, (x, y))
    if not grande:
        titulo = t['titulo'] + ' RAID'
        tam = 21
        while tam > 12 and _fuente('georgiab.ttf', tam).getlength(titulo) > bw - 200 * k - 12:
            tam -= 1
        _texto_dorado(ban, (12, (bh - tam - 3) // 2), titulo, _fuente('georgiab.ttf', tam))
        return ban
    tam = 30
    while tam > 16 and _fuente('georgiab.ttf', tam).getlength(t['titulo']) > bw - 200:
        tam -= 1
    _texto_dorado(ban, (14, 12 + (30 - tam) // 2), t['titulo'], _fuente('georgiab.ttf', tam))
    _texto_dorado(ban, (16, 48), 'R A I D', _fuente('georgiab.ttf', 15), (255, 214, 150), (230, 120, 40))
    d = ImageDraw.Draw(ban)
    d.line((16, 72, 160, 72), fill=(200, 140, 60, 255))
    d.line((16, 73, 160, 73), fill=(80, 30, 10, 255))
    f = _fuente('trebucbd.ttf', 11)
    datos = 'Level %d  \u2022  20 players  \u2022  3 bosses' % t['nivel']
    d.text((16, 79), datos, font=f, fill=(0, 0, 0, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    d.text((16, 79), datos, font=f, fill=(255, 226, 180, 255))
    return ban


def _caja(d, caja, relleno=(14, 9, 8, 255), borde=(110, 66, 30, 255), brillo=(44, 28, 18, 255)):
    x0, y0, x1, y1 = caja
    d.rectangle(caja, fill=relleno, outline=borde)
    d.line((x0 + 1, y0 + 1, x1 - 1, y0 + 1), fill=brillo)


def _lienzo(w, h):
    im = Image.new('RGBA', (w, h), (22, 14, 12, 255))
    d = ImageDraw.Draw(im)
    for y in range(h):
        v = y / h
        d.line((0, y, w, y), fill=(int(36 - 16 * v), int(22 - 10 * v), int(17 - 8 * v), 255))
    return im, d


def _marco(d, w, h):
    d.rectangle((0, 0, w - 1, h - 1), outline=(176, 120, 48, 255))
    d.rectangle((1, 1, w - 2, h - 2), outline=(60, 34, 16, 255))


def _cabecera(d, xy, texto):
    d.text(xy, texto, font=_fuente('trebucbd.ttf', 11), fill=(214, 160, 70, 255))


# El marco de WND_CLASS_DLG_1 se dibuja dentro de su range y mete a los hijos MARCO_X a la derecha y MARCO_Y abajo
# (la barra del titulo): medido en el cliente, 11/11/2026. El range de la ventana es el contenido mas eso.
MARCO_X, MARCO_Y, MARCO_ABAJO = 4, 20, 4


def _cabeza_dlg(wid, w, h, titulo, hijos):
    return ('    <window class="WND_CLASS_DLG_1" range="0,0,%d,%d" id="%d" title="%s" fcolor="104" font="1">\n'
            '        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
            % (w + 2 * MARCO_X, h + MARCO_Y + MARCO_ABAJO, wid, titulo,
               ''.join('        <child>%d</child>\n' % c for c in hijos)))


# ---------------------------------------------------------------------------------------------- la ventana de la raid
# "Que esta ventana tambien se vea bonita, amigable" (11/11/2026): el mismo estilo que AOF Raids.
RW, RH = 372, 356
R_BANNER = (4, 4, RW - 4, 52)
R_MIEMBROS = (4, 56, RW - 4, 204)
R_JEFES = (4, 208, RW - 4, 284)
R_INVITAR = (92, 290, 234, 306)         # la caja del nombre


def dibujar_raid() -> Image.Image:
    im, d = _lienzo(RW, RH)
    im.alpha_composite(_banner(R_BANNER[2] - R_BANNER[0], R_BANNER[3] - R_BANNER[1], grande=False), R_BANNER[:2])
    d.rectangle(R_BANNER, outline=(150, 96, 40, 255))
    linea = (90, 54, 26, 255)
    for caja, cab in ((R_MIEMBROS, 'MEMBERS'), (R_JEFES, 'BOSSES')):
        _caja(d, caja)
        _cabecera(d, (caja[0] + 8, caja[1] + 4), cab)
        d.line((caja[0] + 6, caja[1] + 20, caja[2] - 6, caja[1] + 20), fill=linea)
    for k in range(3):                                          # una ascua delante de cada jefe
        y = R_JEFES[1] + 30 + 17 * k
        d.ellipse((14, y - 3, 20, y + 3), fill=(255, 140, 40, 255), outline=(120, 40, 10, 255))
        d.point((16, y - 1), fill=(255, 230, 150, 255))
    _caja(d, R_INVITAR, (8, 5, 4, 255), (130, 84, 36, 255), (30, 20, 14, 255))
    _cabecera(d, (10, R_INVITAR[1] + 1), 'Invite player:')
    d.line((4, 312, RW - 4, 312), fill=linea)
    _marco(d, RW, RH)
    return im


def dibujar_lista() -> Image.Image:
    """El fondo de AOF Raids, opaco: marco dorado, el banner de Flamefang y los dos paneles."""
    im, d = _lienzo(LW, LH)
    im.alpha_composite(_banner(), BANNER[:2])
    d.rectangle(BANNER, outline=(150, 96, 40, 255))
    _caja(d, PANEL_IZQ)
    _caja(d, PANEL_DER)
    f = _fuente('trebucbd.ttf', 11)
    d.text((PANEL_IZQ[0] + 8, PANEL_IZQ[1] + 4), 'RAIDS', font=f, fill=(214, 160, 70, 255))
    linea = (90, 54, 26, 255)
    d.line((PANEL_IZQ[0] + 6, PANEL_IZQ[1] + 20, PANEL_IZQ[2] - 6, PANEL_IZQ[1] + 20), fill=linea)
    d.line((X_DETALLE, PANEL_DER[1] + 55, PANEL_DER[2] - 8, PANEL_DER[1] + 55), fill=linea)
    d.line((X_DETALLE, PANEL_DER[1] + 122, PANEL_DER[2] - 8, PANEL_DER[1] + 122), fill=linea)
    _marco(d, LW, LH)
    return im


def bloque_lista() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)

    def texto(wid, x, y, w, color):
        return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="" fcolor="%d" font="1"' % color,
                  'wsVisible="" ssVCenter=""')
    poner(LISTA_ABRIR, _boton(LISTA_ABRIR, LW - 74, LH - 30, 'Open', 'OnRaidListaAbrir', w=66))
    poner(GUIA_LISTA, _boton(GUIA_LISTA, LW - 144, LH - 30, 'Guide', 'OnRaidListaGuia', w=66))
    poner(RANKING_LISTA, _boton(RANKING_LISTA, LW - 214, LH - 30, 'Ranking', 'OnRaidListaRanking', w=66))
    poner(LISTA_FILAS, _w('WND_CLASS_LIST', LISTA_FILAS, PANEL_IZQ[0] + 4, PANEL_IZQ[1] + 24,
                          PANEL_IZQ[2] - PANEL_IZQ[0] - 8, PANEL_IZQ[3] - PANEL_IZQ[1] - 28,
                          ' cols="1" rows="7" gapx="0" gapy="2" tpos="3,2" fcolor="103" font="1"',
                          'wsVisible="" lsVCenter="" lsReport="" wsTab=""',     # sin lsReport no pinta las filas
                          '        <OnCommand>OnRaidListaFila</OnCommand>\n'))
    ancho = PANEL_DER[2] - X_DETALLE - 8
    y = PANEL_DER[1] + 5
    poner(LISTA_NOMBRE, texto(LISTA_NOMBRE, X_DETALLE, y, ancho, 514))
    poner(LISTA_NIVEL, texto(LISTA_NIVEL, X_DETALLE, y + 17, ancho, 103))
    poner(LISTA_SEMANA, texto(LISTA_SEMANA, X_DETALLE, y + 32, ancho, 511))
    poner(LISTA_JEFES, texto(LISTA_JEFES, X_DETALLE, y + 55, ancho, 513))
    for k in range(3):
        poner(LISTA_JEFES + 1 + k, texto(LISTA_JEFES + 1 + k, X_DETALLE + 6, y + 71 + 15 * k, ancho - 6, 103))
    poner(LISTA_BOTIN, texto(LISTA_BOTIN, X_DETALLE, y + 121, ancho, 510))
    poner(LISTA_BOTIN + 1, texto(LISTA_BOTIN + 1, X_DETALLE, y + 121 + 13, ancho, 510))
    poner(LISTA_ESTADO, texto(LISTA_ESTADO, 10, LH - 26, LW - 232, 513))
    poner(BANNER_LISTA, _w('WND_CLASS_BASE', BANNER_LISTA, BANNER[0], BANNER[1], BANNER[2] - BANNER[0], BANNER[3] - BANNER[1], ' icon="%d"' % ICONO_BANNER_LISTA))
    for t in range(N_TEMAS):
        ventanas.append('    <icon id="%d" dir="%swnd01%s" normal="aolat_raid_ban%d" focus="normal" down="normal" '
                        'disable="normal" />\n' % (ICONO_BANNER_LISTA + t, chr(92), chr(92), t))
    poner(LISTA_FONDO, _w('WND_CLASS_BASE', LISTA_FONDO, 0, 0, LW, LH, ' icon="%d"' % LISTA_ICONO_FONDO))
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="aolat_raid_lista" focus="normal" down="normal" '
                    'disable="normal" />\n' % LISTA_ICONO_FONDO)
    cab = _cabeza_dlg(LISTA_RAIDS, LW, LH, 'AOF Raids', hijos)
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA_LISTA, cab, ''.join(ventanas), MARCA_LISTA)


# ---------------------------------------------------------------------------------------------- la guia
# "Una opcion con las instrucciones de cada raid, mecanicas de la raid y de los jefes" (11/11/2026). Pestanas arriba
# (Overview, un jefe cada una, Loot), el titulo de la pagina, 13 lineas y, en las de los jefes, su retrato. El texto lo
# manda el servidor (server/raid.py guia) y lo pinta RaidGuia de server/lua/raid_menu.lua.
MARCA_GUIA = 'aolat raid guia'
MARCA_RANKING = 'aolat raid ranking'
# EL RANKING (11/11/2026): las 10 raids mas rapidas de cada una (server/raid.py filas_ranking, lua RaidRanking). Mismo
# ancho que la guia para usar sus banners (ICONO_BANNER_GUIA). Cada fila: puesto y lider, tiempo y fecha, y encima un
# boton transparente cuyo tooltip lleva a todos los miembros.
RANKING, KW, KH = 60350, 420, 316
RANKING_LISTA = 60349                     # el boton "Ranking" de AOF Raids
K_BANNER, K_TITULO, K_CABECERA, K_VACIO, K_CERRAR, K_FONDO, K_ICONO_FONDO = (60351, 60352, 60353, 60354, 60355,
                                                                            60356, 60357)
K_LIDER, K_TIEMPO, K_FECHA, K_CLIC = 60360, 60370, 60380, 60390
K_TABLA = (4, 74, KW - 4, KH - 32)
GUIA, GW, GH = 59880, 420, 330
GUIA_PESTANA, GUIA_TITULO, GUIA_LINEA, GUIA_RETRATO, GUIA_CERRAR = 59881, 59886, 59887, 59900, 59901
GUIA_FONDO, GUIA_ICONO_FONDO, GUIA_ICONO_RETRATO = 59902, 59903, 59860      # retratos 59861..59863
GUIA_RAID, GUIA_LISTA = 59616, 59685                                          # los botones "Guide"
G_BANNER = (4, 4, GW - 4, 52)
G_PAGINA = (4, 82, GW - 4, GH - 32)
G_RETRATO = (GW - 112, 112, GW - 12, 232)                                     # 100 x 120
N_LINEAS, ALTO_LINEA = 13, 14
# Seis pestanas (11/11/2026: la de los puzles): la sexta no cabe en 59881..59885 (el 59886 es el titulo).
PESTANA_W, PESTANA_H, ICONO_PESTANA, ICONO_PESTANA_ACTIVA = 66, 20, 59864, 59865
PESTANAS_GUIA = (59881, 59882, 59883, 59884, 59885, 60323)


def pestana(estado) -> Image.Image:
    """Una pestana de 78x20: 'n' normal, 'f' con el raton encima, 's' la elegida (brasa encendida)."""
    w, h = PESTANA_W, PESTANA_H
    im = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    arriba, abajo = {'n': ((70, 40, 24), (34, 20, 14)), 'f': ((100, 58, 30), (46, 26, 16)),
                     's': ((214, 120, 40), (120, 44, 14))}[estado]
    for y in range(h):
        v = y / (h - 1)
        d.line((0, y, w, y), fill=tuple(int(arriba[k] + (abajo[k] - arriba[k]) * v) for k in range(3)) + (255,))
    borde = (230, 170, 70, 255) if estado == 's' else (150, 96, 40, 255)
    d.rectangle((0, 0, w - 1, h - 1), outline=borde)
    d.line((1, 1, w - 2, 1), fill=(255, 220, 140, 255) if estado == 's' else (120, 80, 46, 255))
    return im


# Los retratos de la guia (server/raid.py, 'retrato' de cada raid del CATALOGO): 1..3 los de la Flamefang (iconos
# 59861..59863) y 4..12 los de las raids de nivel 50, 40 y 30 (11/11/2026; iconos 60301..60309): Cerberus, Ares, Hades,
# Ice Giant Hydea, Mighty Leon, Seasonia, Blossom Hail, General Rizaburo y Watatsumi. Su carpeta es M<sprite-108001>.
RETRATOS_NUEVOS = (111252, 110931, 111243, 111144, 111143, 111148, 111384, 111385, 111386)
ICONO_RETRATO_NUEVO = 60300                                                     # + 1..9


def _ruta_retrato(i):
    if i < 3:
        return JEFES_SPR[(0, 2, 1)[i]][:2]
    sprite = RETRATOS_NUEVOS[i - 3]
    return 'M%d' % (sprite - 108001) + chr(92) + str(sprite), 4


def icono_retrato(i):
    """El icono del retrato i (0..11)."""
    return GUIA_ICONO_RETRATO + 1 + i if i < 3 else ICONO_RETRATO_NUEVO + i - 2


def retrato(i) -> Image.Image:
    """El jefe i (0..11: Lavamon, Razorex, Satrixia y los de las demas raids) en un recuadro de brasa de 100x120."""
    from PIL import ImageFilter
    w, h = G_RETRATO[2] - G_RETRATO[0], G_RETRATO[3] - G_RETRATO[1]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    for y in range(h):
        v = y / h
        d.line((0, y, w, y), fill=(int(30 + 120 * v ** 2), int(8 + 30 * v ** 3), 10, 255))
    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-10, h * 0.45, w + 10, h * 1.4), fill=(255, 110, 20, 150))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))
    ruta, frame = _ruta_retrato(i)
    s = _sprite(ruta, frame)
    caja = s.getbbox()
    s = s.crop(caja)
    k = min((w - 6) / s.width, (h - 6) / s.height)
    s = s.resize((max(1, int(s.width * k)), max(1, int(s.height * k))), Image.LANCZOS)
    im.alpha_composite(s, ((w - s.width) // 2, h - s.height - 2))
    d.rectangle((0, 0, w - 1, h - 1), outline=(176, 120, 48, 255))
    return im


def dibujar_guia() -> Image.Image:
    im, d = _lienzo(GW, GH)
    im.alpha_composite(_banner(G_BANNER[2] - G_BANNER[0], G_BANNER[3] - G_BANNER[1], grande=False), G_BANNER[:2])
    d.rectangle(G_BANNER, outline=(150, 96, 40, 255))
    _caja(d, G_PAGINA)
    d.line((G_PAGINA[0] + 6, G_PAGINA[1] + 22, G_PAGINA[2] - 6, G_PAGINA[1] + 22), fill=(90, 54, 26, 255))
    _marco(d, GW, GH)
    return im


def bloque_guia() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)

    def texto(wid, x, y, w, color):
        return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="" fcolor="%d" font="1"' % color,
                  'wsVisible="" ssVCenter=""')
    # Pestanas con icono propio de su ancho: el boton del tema (btn111) no se estira y el texto se salia de el.
    for k, wid in enumerate(PESTANAS_GUIA):
        poner(wid, _w('WND_CLASS_BUTTON', wid, 6 + 69 * k, 58, PESTANA_W, PESTANA_H,
                                   ' fcolor="101" font="1" icon="%d" title=""' % ICONO_PESTANA,
                                   'wsVisible="" bsHCenter="" bsVCenter="" wsTab=""',
                                   '        <OnCommand>OnRaidGuiaPestana%d</OnCommand>\n' % (k + 1)))
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="aolat_raid_tab_n" focus="aolat_raid_tab_f" '
                    'down="aolat_raid_tab_s" disable="normal" />\n' % ICONO_PESTANA)
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="aolat_raid_tab_s" focus="aolat_raid_tab_s" '
                    'down="aolat_raid_tab_s" disable="aolat_raid_tab_s" />\n' % ICONO_PESTANA_ACTIVA)
    poner(GUIA_CERRAR, _boton(GUIA_CERRAR, GW - 74, GH - 26, 'Close', 'OnRaidGuiaCerrar', w=66))
    poner(GUIA_TITULO, texto(GUIA_TITULO, G_PAGINA[0] + 8, G_PAGINA[1] + 5, G_PAGINA[2] - G_PAGINA[0] - 16, 514))
    for k in range(N_LINEAS):
        poner(GUIA_LINEA + k, texto(GUIA_LINEA + k, G_PAGINA[0] + 8, G_PAGINA[1] + 28 + ALTO_LINEA * k,
                                    G_PAGINA[2] - G_PAGINA[0] - 16, 103))
    poner(GUIA_RETRATO, _w('WND_CLASS_BASE', GUIA_RETRATO, G_RETRATO[0], G_RETRATO[1], G_RETRATO[2] - G_RETRATO[0],
                           G_RETRATO[3] - G_RETRATO[1], ' icon="%d"' % (GUIA_ICONO_RETRATO + 1)))
    poner(BANNER_GUIA, _w('WND_CLASS_BASE', BANNER_GUIA, G_BANNER[0], G_BANNER[1], G_BANNER[2] - G_BANNER[0], G_BANNER[3] - G_BANNER[1], ' icon="%d"' % ICONO_BANNER_GUIA))
    for t in range(N_TEMAS):
        ventanas.append('    <icon id="%d" dir="%swnd01%s" normal="aolat_raid_bang%d" focus="normal" down="normal" '
                        'disable="normal" />\n' % (ICONO_BANNER_GUIA + t, chr(92), chr(92), t))
    poner(GUIA_FONDO, _w('WND_CLASS_BASE', GUIA_FONDO, 0, 0, GW, GH, ' icon="%d"' % GUIA_ICONO_FONDO))
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="aolat_raid_guia" focus="normal" down="normal" '
                    'disable="normal" />\n' % GUIA_ICONO_FONDO)
    for i in range(3 + len(RETRATOS_NUEVOS)):
        ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="aolat_raid_jefe%d" focus="normal" down="normal" '
                        'disable="normal" />\n' % (icono_retrato(i), i + 1))
    cab = _cabeza_dlg(GUIA, GW, GH, 'Raid Guide', hijos)
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA_GUIA, cab, ''.join(ventanas), MARCA_GUIA)


def boton_menu(texto):
    """'Invite to raid' en el menu del jugador (565), oculto: el Lua lo ensena al lider de una raid."""
    m = re.search(r'<window [^>]*\bid="%d"[^>]*>\s*<style[^>]*/>' % MENU_JUGADOR, texto)
    if not m:
        raise SystemExit('no esta el menu del jugador (%d) en wnd01.xml' % MENU_JUGADOR)
    texto = texto[:m.end()] + '\n        <child>%d</child>' % BOTON_MENU + texto[m.end():]
    boton = ('    <!-- %s -->\n' % MARCA_LISTA
             + '    <window class="WND_CLASS_BUTTON" range="2,159,110,12" id="%d" fcolor="106" font="1" '
               'title="Invite to raid">\n        <style ssVCenter="" ssHCenter="" wsTab="" />\n'
               '        <OnCommand>OnClickChatOptionRaid</OnCommand>\n    </window>\n' % BOTON_MENU
             + '    <!-- /%s -->\n' % MARCA_LISTA)
    return _al_final(boton)(texto)


def dibujar_ranking() -> Image.Image:
    im, d = _lienzo(KW, KH)
    d.rectangle(G_BANNER, outline=(150, 96, 40, 255))
    _caja(d, K_TABLA)
    linea = (90, 54, 26, 255)
    d.line((K_TABLA[0] + 6, K_TABLA[1] + 22, K_TABLA[2] - 6, K_TABLA[1] + 22), fill=linea)
    for i in range(1, 10, 2):                                   # franjas alternas
        y = K_TABLA[1] + 26 + 20 * i
        d.rectangle((K_TABLA[0] + 4, y - 1, K_TABLA[2] - 4, y + 17), fill=(26, 17, 12, 255))
    _marco(d, KW, KH)
    return im


def bloque_ranking() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)

    def texto(wid, x, y, w, color=103, titulo=''):
        return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="%s" fcolor="%d" font="1"' % (titulo, color),
                  'wsVisible="" ssVCenter=""')
    for i in range(10):                                         # encima de todo: el raton
        y = K_TABLA[1] + 26 + 20 * i
        poner(K_CLIC + i, _w('WND_CLASS_BUTTON', K_CLIC + i, K_TABLA[0] + 4, y - 1, K_TABLA[2] - K_TABLA[0] - 8, 18,
                             ' appdata="%d"' % i, 'wsVisible="" wsTab=""'))
    poner(K_CERRAR, _boton(K_CERRAR, KW - 74, KH - 26, 'Close', 'OnRaidRankingCerrar', w=66))
    poner(K_TITULO, texto(K_TITULO, 10, 56, KW - 20, 514))
    poner(K_CABECERA, texto(K_CABECERA, K_TABLA[0] + 8, K_TABLA[1] + 5, 200, 510, '#   Leader'))
    poner(K_CABECERA + 100, texto(K_CABECERA + 100, 250, K_TABLA[1] + 5, 70, 510, 'Time'))
    poner(K_CABECERA + 101, texto(K_CABECERA + 101, 330, K_TABLA[1] + 5, 70, 510, 'Date'))
    poner(K_VACIO, texto(K_VACIO, K_TABLA[0] + 12, K_TABLA[1] + 30, 300, 103, 'Nobody has cleared this raid yet.'))
    for i in range(10):
        y = K_TABLA[1] + 26 + 20 * i
        poner(K_LIDER + i, texto(K_LIDER + i, K_TABLA[0] + 8, y, 230, 514 if i == 0 else 103))
        poner(K_TIEMPO + i, texto(K_TIEMPO + i, 250, y, 70))
        poner(K_FECHA + i, texto(K_FECHA + i, 330, y, 70))
    poner(K_BANNER, _w('WND_CLASS_BASE', K_BANNER, G_BANNER[0], G_BANNER[1], G_BANNER[2] - G_BANNER[0],
                       G_BANNER[3] - G_BANNER[1], ' icon="%d"' % ICONO_BANNER_GUIA))
    poner(K_FONDO, _w('WND_CLASS_BASE', K_FONDO, 0, 0, KW, KH, ' icon="%d"' % K_ICONO_FONDO))
    ventanas.append('    <icon id="%d" dir="%swnd01%s" normal="aolat_raid_ranking" focus="normal" down="normal" '
                    'disable="normal" />\n' % (K_ICONO_FONDO, chr(92), chr(92)))
    cab = _cabeza_dlg(RANKING, KW, KH, 'Raid Ranking', hijos)
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA_RANKING, cab, ''.join(ventanas), MARCA_RANKING)


def main():
    iconos()
    iconos_panel()
    (SALIDA / (ARCHIVO_FONDO + '.shp')).write_bytes(a_shp(dibujar_raid()))
    (SALIDA / 'aolat_raid_lista.shp').write_bytes(a_shp(dibujar_lista()))
    (SALIDA / 'aolat_raid_guia.shp').write_bytes(a_shp(dibujar_guia()))
    for i in range(3 + len(RETRATOS_NUEVOS)):
        (SALIDA / ('aolat_raid_jefe%d.shp' % (i + 1))).write_bytes(a_shp(retrato(i)))
    for e in 'nfs':
        (SALIDA / ('aolat_raid_tab_%s.shp' % e)).write_bytes(a_shp(pestana(e)))
    for t in range(N_TEMAS):
        (SALIDA / ('aolat_raid_ban%d.shp' % t)).write_bytes(a_shp(_banner(tema=t)))
        for archivo, caja in (('aolat_raid_banr%d', R_BANNER), ('aolat_raid_bang%d', G_BANNER)):
            (SALIDA / ((archivo % t) + '.shp')).write_bytes(
                a_shp(_banner(caja[2] - caja[0], caja[3] - caja[1], grande=False, tema=t)))
    (SALIDA / 'aolat_raid_ranking.shp').write_bytes(a_shp(dibujar_ranking()))
    _guardar('wnd03.xml', _al_final(bloque_wnd03() + bloque_panel() + bloque_lista() + bloque_guia()
                                    + bloque_ranking()))
    _guardar('wnd01.xml', lambda t: boton_menu(wnd01(t)))
    print('boton %d, ventana %d (%dx%d), panel %d (%dx%d) e iconos listos' % (BOTON_BARRA, VENTANA, RW, RH, PANEL, PW, PH))


if __name__ == '__main__':
    main()
