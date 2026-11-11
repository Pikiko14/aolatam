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
# "Podria verse el team asi como si fuera el panel de team pero este seria de raid" (11/11/2026): 4 grupos de 5, cada
# uno con la corona del lider, su nombre, si esta muerto / fuera / desconectado, su rol (tanque, sanador, dano) y sus
# barras de vida y mana. Lo rellena RaidPanel de server/lua/raid.lua cada segundo.
MARCA_PANEL = 'aolat raid panel'
PANEL, PW, FILA, CABECERA = 59700, 210, 26, 14
PANEL_NOMBRE, PANEL_ROL, PANEL_CORONA, PANEL_VIDA, PANEL_MANA, PANEL_ESTADO = 59710, 59730, 59750, 59770, 59790, 59810
PANEL_GRUPO, PANEL_FONDO, PANEL_ICONO_FONDO = 59830, 59840, 59841
ICONO_CORONA, ICONO_TANQUE, ICONO_SANADOR, ICONO_DANO = 59850, 59851, 59852, 59853
BARRA_VIDA, BARRA_MANA = 159, 160          # las barras de vida y mana del jugador (shape/wnd01/w008_03 y _04)
ALTO_GRUPO = CABECERA + 5 * FILA
PH = 4 + 4 * ALTO_GRUPO + 4


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
    (SALIDA / 'aolat_raid_panel.shp').write_bytes(fondo(PW, PH))


def bloque_panel() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)
    filas = []
    for g in range(4):
        y0 = 4 + g * ALTO_GRUPO
        for r in range(5):
            filas.append((g * 5 + r, y0 + CABECERA + r * FILA))
    for i, y in filas:
        poner(PANEL_CORONA + i, _w('WND_CLASS_BUTTON', PANEL_CORONA + i, 6, y + 1, 12, 12, ' icon="%d"' % ICONO_CORONA, ''))
        poner(PANEL_ROL + i, _w('WND_CLASS_BUTTON', PANEL_ROL + i, PW - 22, y + 1, 12, 12, ' icon="0"', ''))
        poner(PANEL_NOMBRE + i, _w('WND_CLASS_STATIC', PANEL_NOMBRE + i, 20, y, 120, 14,
                                   ' title="" fcolor="103" font="1"', 'ssVCenter=""'))
        poner(PANEL_ESTADO + i, _w('WND_CLASS_STATIC', PANEL_ESTADO + i, 136, y, 50, 14,
                                   ' title="" fcolor="103" font="1"', 'ssVCenter="" ssRight=""'))
        poner(PANEL_VIDA + i, _w('WND_CLASS_PROGRESS', PANEL_VIDA + i, 8, y + 15, PW - 16, 4,
                                 ' picon="%d"' % BARRA_VIDA, 'psHorizontal=""'))
        poner(PANEL_MANA + i, _w('WND_CLASS_PROGRESS', PANEL_MANA + i, 8, y + 20, PW - 16, 3,
                                 ' picon="%d"' % BARRA_MANA, 'psHorizontal=""'))
    for g in range(4):
        poner(PANEL_GRUPO + g, _texto(PANEL_GRUPO + g, 6, 4 + g * ALTO_GRUPO, PW - 12, 'Group %d' % (g + 1)))
    poner(PANEL_FONDO, _w('WND_CLASS_BASE', PANEL_FONDO, 0, 0, PW, PH, ' icon="%d"' % PANEL_ICONO_FONDO))
    for wid, archivo, tema in ((PANEL_ICONO_FONDO, 'aolat_raid_panel', True), (ICONO_CORONA, 'aolat_corona', False),
                               (ICONO_TANQUE, 'aolat_rol_tanque', False), (ICONO_SANADOR, 'aolat_rol_sanador', False),
                               (ICONO_DANO, 'aolat_rol_dano', False)):
        ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="normal" down="normal" disable="normal">\n'
                        '%s    </icon>\n' % (wid, archivo, '        <attrib ICON_ATTRIB_THEME="" ICON_ATTRIB_FAST="" />\n'
                                             if tema else ''))
    cab = ('    <window class="WND_CLASS_DLG_1" range="0,0,%d,%d" id="%d" title="Raid" fcolor="104" font="1">\n'
           '        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
           % (PW, PH, PANEL, ''.join('        <child>%d</child>\n' % h for h in hijos)))
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA_PANEL, cab, ''.join(ventanas), MARCA_PANEL)


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
    poner(INVITAR, _boton(INVITAR, 136, 268, 'Invite', 'OnRaidInvitar'))
    poner(CREAR, _boton(CREAR, 8, 292, 'Create', 'OnRaidCrear', w=60))
    poner(PARTY, _boton(PARTY, 72, 292, 'Invite party', 'OnRaidParty', w=80))
    poner(ENTRAR, _boton(ENTRAR, 156, 292, 'Enter', 'OnRaidEntrar', w=60))
    poner(SALIR_MAPA, _boton(SALIR_MAPA, 220, 292, 'Exit map', 'OnRaidSalirMapa', w=64))
    poner(ACEPTAR, _boton(ACEPTAR, 290, 292, 'Accept', 'OnRaidAceptar', w=60, visible=False))
    poner(NOMBRE, _w('WND_CLASS_EDIT', NOMBRE, 8, 270, 120, 14, ' fcolor="103" font="1" tpos="1,0" limit="16"',
                     'wsVisible="" esVCenter="" wsTab=""'))
    poner(TITULO, _texto(TITULO, 8, 4, W - 16))
    poner(LISTA, _w('WND_CLASS_LIST', LISTA, 6, 22, W - 12, 186,
                    ' cols="3" rows="11" gapx="2" gapy="1" tpos="1,1" fcolor="103" font="1"',
                    'wsVisible="" lsVCenter="" lsReport=""'))
    for k in range(3):
        poner(JEFES + k, _texto(JEFES + k, 8, 214 + 16 * k, W - 16))
    poner(ESTADO, _texto(ESTADO, 8, 320, W - 16))
    poner(FONDO, _w('WND_CLASS_BASE', FONDO, 0, 0, W, H, ' icon="%d"' % ICONO_FONDO))
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="normal" down="normal" disable="normal">\n'
                    '        <attrib ICON_ATTRIB_THEME="" ICON_ATTRIB_FAST="" />\n    </icon>\n'
                    % (ICONO_FONDO, ARCHIVO_FONDO))
    cab = ('    <window class="WND_CLASS_DLG_1" range="0,0,%d,%d" id="%d" title="Flamefang Raid" fcolor="104" font="1">\n'
           '        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
           % (W, H, VENTANA, ''.join('        <child>%d</child>\n' % h for h in hijos)))
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA, cab, ''.join(ventanas), MARCA)


def _guardar(nombre, cambio):
    ruta = ENG / nombre
    crudo = ruta.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = texto.replace('\r\n', '\n')
    for marca in (MARCA, MARCA_PANEL, MARCA_LISTA):
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
LISTA_RAIDS, LW, LH = 59670, 330, 200
LISTA_FILAS, LISTA_ABRIR, LISTA_ESTADO, LISTA_FONDO, LISTA_ICONO_FONDO = 59671, 59672, 59673, 59674, 59675
MENU_JUGADOR, BOTON_MENU = 565, 59660     # el menu de clic derecho sobre un jugador (chat.lua OnClickChatOption)


def bloque_lista() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)
    poner(LISTA_ABRIR, _boton(LISTA_ABRIR, LW - 64, LH - 26, 'Open', 'OnRaidListaAbrir'))
    poner(LISTA_FILAS, _w('WND_CLASS_LIST', LISTA_FILAS, 6, 6, LW - 12, LH - 56,
                          ' cols="4" rows="8" gapx="2" gapy="1" tpos="1,1" fcolor="103" font="1"',
                          'wsVisible="" lsVCenter="" lsReport="" wsTab=""', '        <OnCommand>OnRaidListaFila</OnCommand>\n'))
    poner(LISTA_ESTADO, _texto(LISTA_ESTADO, 8, LH - 46, LW - 16))
    poner(LISTA_FONDO, _w('WND_CLASS_BASE', LISTA_FONDO, 0, 0, LW, LH, ' icon="%d"' % LISTA_ICONO_FONDO))
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="aolat_raid_lista" focus="normal" down="normal" '
                    'disable="normal">\n        <attrib ICON_ATTRIB_THEME="" ICON_ATTRIB_FAST="" />\n    </icon>\n'
                    % LISTA_ICONO_FONDO)
    cab = ('    <window class="WND_CLASS_DLG_1" range="0,0,%d,%d" id="%d" title="AOF Raids" fcolor="104" font="1">\n'
           '        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
           % (LW, LH, LISTA_RAIDS, ''.join('        <child>%d</child>\n' % h for h in hijos)))
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA_LISTA, cab, ''.join(ventanas), MARCA_LISTA)


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


def main():
    iconos()
    iconos_panel()
    (SALIDA / (ARCHIVO_FONDO + '.shp')).write_bytes(fondo())
    (SALIDA / 'aolat_raid_lista.shp').write_bytes(fondo(LW, LH))
    _guardar('wnd03.xml', _al_final(bloque_wnd03() + bloque_panel() + bloque_lista()))
    _guardar('wnd01.xml', lambda t: boton_menu(wnd01(t)))
    print('boton %d, ventana %d (%dx%d), panel %d (%dx%d) e iconos listos' % (BOTON_BARRA, VENTANA, W, H, PANEL, PW, PH))


if __name__ == '__main__':
    main()
