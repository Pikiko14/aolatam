"""La ventana del arbol de evolucion de la mascota (server/arbol_mascotas.py, server/lua/arbol.lua), 10/11/2026.

Escribe en parches/extras/setting/eng:
  wnd03.xml  la ventana 59400 "Evolution of ...": 15 formas en cuatro columnas (huevo, 2, 4, 8) unidas por lineas, y
             abajo la ficha de la forma pulsada (retrato, tipo, stats, habilidades con su texto al pasar el raton),
             un aviso y los botones Evolve y Close.
  wnd01.xml  el boton Evolve (59399) debajo de la ficha de la mascota (ventana 878), que abre el arbol.

Las cajas y las lineas son ventanas BASE sin dibujo a las que el Lua da color con window.setbgcolor; el boton de cada
forma va encima (el primer hijo de la lista es el que queda arriba) y lleva su indice en appdata. Se puede correr las
veces que haga falta: quita lo suyo antes de ponerlo.

    python tools/parche_arbol_mascotas.py
"""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ENG = RAIZ / 'parches' / 'extras' / 'setting' / 'eng'

VENTANA = 59400
AVISO_ARRIBA = 59401
BOTON, NOMBRE, NIVEL, CAJA = 59410, 59430, 59450, 59470
LINEAS = 59490                      # 5 por padre: salida, media de arriba, media de abajo, entrada 1, entrada 2
RETRATO, NOMBRE_F, TEXTO_F, STATS1, STATS2, HABS = 59530, 59531, 59532, 59533, 59534, 59535
HAB_ICONO, HAB_NOMBRE = 59536, 59539
ESTADO, EVOLVE, CERRAR = 59542, 59543, 59544
# El fondo con el COLOR DEL TEMA ("que sea del color del tema", 10/11/2026). El tema no es un color: cada uno tine las
# imagenes con ICON_ATTRIB_THEME (theme.xml, 底色). Asi que el fondo es una imagen del tamano de la ventana con el
# color liso de la pagina System (shape/wnd01/w050_01: 0xd301 y su borde 0xf003), marcada como de tema.
FONDO, ICONO_FONDO, ARCHIVO_FONDO = 59545, 59546, 'aolat_arbol_fondo'
COLOR_FONDO, COLOR_BORDE = 0xd301, 0xf003
BOTON_MASCOTA = 59399
VENTANA_MASCOTA = 878

ICONO = 59550                       # la imagen pequena de cada forma (tools/retratos_arbol.py, 26 x 26)
LADO_ICONO = 26
ANCHO_NODO, ALTO_NODO, HUECO = 132, 28, 10
COLUMNAS = [8 + c * (ANCHO_NODO + HUECO) for c in range(4)]
ARRIBA, PASO_HOJA = 22, 30
ANCHO, ALTO = COLUMNAS[-1] + ANCHO_NODO + 8, 402
MARCA = 'aolat arbol'


def posicion(i):
    """(x, y) del nodo i del monton: las 8 hojas en fila y cada padre a media altura de sus dos hijos."""
    nivel = (i + 1).bit_length() - 1
    k = i - (2 ** nivel - 1)
    hojas = 2 ** (3 - nivel)                       # hojas que tiene debajo
    centro = ARRIBA + (k * hojas + (hojas - 1) / 2) * PASO_HOJA
    return COLUMNAS[nivel], round(centro)


def _w(clase, wid, x, y, w, h, extra='', estilo='wsVisible=""', cuerpo=''):
    return ('    <window class="%s" id="%d" range="%d,%d,%d,%d"%s>\n        <style %s />\n%s    </window>\n'
            % (clase, wid, x, y, w, h, extra, estilo, cuerpo))


def _texto(wid, x, y, w, titulo='', derecha=False):
    return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="%s" fcolor="103" font="1"' % titulo,
              'wsVisible="" ssVCenter=""' + (' ssRight=""' if derecha else ''))


def _boton(wid, x, y, w, h, titulo, funcion, icono=12006, extra=''):
    return _w('WND_CLASS_BUTTON', wid, x, y, w, h, ' fcolor="101" font="1" icon="%d" title="%s"%s' % (icono, titulo,
                                                                                                     extra),
              'wsVisible="" bsHCenter="" bsVCenter="" wsTab=""', '        <OnCommand>%s</OnCommand>\n' % funcion)


def bloque_wnd03() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)

    # Encima de todo: los botones de las formas, luego sus textos, luego las cajas y al final las lineas.
    for i in range(15):
        x, y = posicion(i)
        poner(BOTON + i, _w('WND_CLASS_BUTTON', BOTON + i, x, y, ANCHO_NODO, ALTO_NODO,
                            ' icon="0" appdata="%d"' % i, 'wsVisible="" wsTab=""',
                            '        <OnCommand>OnArbolNodo</OnCommand>\n'))
    # La imagen de la forma a la izquierda de cada cuadro ("pudiese salir la imagen al lado de cada cuadrito",
    # 10/11/2026) y el texto a su derecha.
    for i in range(15):
        x, y = posicion(i)
        poner(NOMBRE + i, _texto(NOMBRE + i, x + LADO_ICONO + 4, y + 1, ANCHO_NODO - LADO_ICONO - 6))
        poner(NIVEL + i, _texto(NIVEL + i, x + LADO_ICONO + 4, y + 13, ANCHO_NODO - LADO_ICONO - 6))
        poner(ICONO + i, _w('WND_CLASS_BUTTON', ICONO + i, x + 1, y + 1, LADO_ICONO, LADO_ICONO, ' icon="0"'))
    for i in range(15):
        x, y = posicion(i)
        poner(CAJA + i, _w('WND_CLASS_BASE', CAJA + i, x, y, ANCHO_NODO, ALTO_NODO))
    for p in range(7):
        xp, yp = posicion(p)
        (x1, y1), (x2, y2) = posicion(2 * p + 1), posicion(2 * p + 2)
        medio = xp + ANCHO_NODO + HUECO // 2
        cy, c1, c2 = yp + ALTO_NODO // 2, y1 + ALTO_NODO // 2, y2 + ALTO_NODO // 2
        b = LINEAS + 5 * p
        for wid, rango in ((b, (xp + ANCHO_NODO, cy - 1, medio - xp - ANCHO_NODO + 1, 2)),
                           (b + 1, (medio - 1, c1 - 1, 2, cy - c1 + 2)),
                           (b + 2, (medio - 1, cy - 1, 2, c2 - cy + 2)),
                           (b + 3, (medio - 1, c1 - 1, x1 - medio + 1, 2)),
                           (b + 4, (medio - 1, c2 - 1, x2 - medio + 1, 2))):
            poner(wid, _w('WND_CLASS_BASE', wid, *rango))
    # La ficha de la forma pulsada.
    ficha = ARRIBA + 8 * PASO_HOJA + 6
    poner(AVISO_ARRIBA, _texto(AVISO_ARRIBA, 8, 4, ANCHO - 16))
    poner(RETRATO, _w('WND_CLASS_BUTTON', RETRATO, 10, ficha + 4, 44, 44, ' icon="0"'))
    poner(NOMBRE_F, _texto(NOMBRE_F, 62, ficha + 4, 250))
    poner(TEXTO_F, _texto(TEXTO_F, 62, ficha + 20, 260))
    poner(STATS1, _texto(STATS1, 10, ficha + 56, 300))
    poner(STATS2, _texto(STATS2, 10, ficha + 72, 300))
    poner(HABS, _texto(HABS, 330, ficha + 4, 150, 'Abilities'))
    for k in range(3):
        poner(HAB_ICONO + k, _w('WND_CLASS_BUTTON', HAB_ICONO + k, 330 + 52 * k, ficha + 22, 36, 36,
                                ' icon="0" tooltip="10040" tooltext=" " tooldelay="10"', 'wsVisible=""'))
        poner(HAB_NOMBRE + k, _texto(HAB_NOMBRE + k, 322 + 52 * k, ficha + 60, 52))
    poner(ESTADO, _texto(ESTADO, 10, ALTO - 24, 340))
    poner(EVOLVE, _boton(EVOLVE, ANCHO - 126, ALTO - 26, 55, 18, 'Evolve', 'OnArbolEvolve'))
    poner(CERRAR, _boton(CERRAR, ANCHO - 66, ALTO - 26, 55, 18, 'Close', 'OnArbolCerrar'))
    # El fondo el ultimo: queda debajo de todo.
    poner(FONDO, _w('WND_CLASS_BASE', FONDO, 0, 0, ANCHO, ALTO, ' icon="%d"' % ICONO_FONDO))
    ventanas.append('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="normal" down="normal" disable="normal">\n'
                    '        <attrib ICON_ATTRIB_THEME="" ICON_ATTRIB_FAST="" />\n    </icon>\n'
                    % (ICONO_FONDO, ARCHIVO_FONDO))
    cab = ('    <window class="WND_CLASS_DLG_1" range="0,0,%d,%d" id="%d" title="Evolution" fcolor="104" font="1">\n'
           '        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
           % (ANCHO, ALTO, VENTANA, ''.join('        <child>%d</child>\n' % h for h in hijos)))
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA, cab, ''.join(ventanas), MARCA)


def _sin_lo_nuestro(texto: str) -> str:
    texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\r?\n' % (MARCA, MARCA), '', texto, flags=re.S)
    return re.sub(r'\r?\n[ \t]*<child>%d</child>' % BOTON_MASCOTA, '', texto)


def _guardar(nombre, cambio):
    ruta = ENG / nombre
    crudo = ruta.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = cambio(_sin_lo_nuestro(texto).replace('\r\n', '\n')).replace('\n', nl)
    ruta.write_bytes((b'\xef\xbb\xbf' if bom else b'') + texto.encode('utf-8'))


def _al_final(bloque):
    def cambio(texto):
        fin = texto.rindex('</root>')
        return texto[:fin] + bloque + texto[fin:]
    return cambio


def wnd01(texto: str) -> str:
    """El boton Evolve como hijo de la ficha de la mascota, debajo del panel de stats (880, 200 x 291)."""
    m = re.search(r'<window [^>]*id="%d"[^>]*>\s*<style[^>]*/>' % VENTANA_MASCOTA, texto)
    if not m:
        raise SystemExit('no esta la ventana %d en wnd01.xml' % VENTANA_MASCOTA)
    texto = texto[:m.end()] + '\n        <child>%d</child>' % BOTON_MASCOTA + texto[m.end():]
    boton = ('    <!-- %s -->\n' % MARCA
             + _boton(BOTON_MASCOTA, 72, 293, 55, 18, 'Evolve', 'OnCommandArbol',
                      extra=' tooltip="10040" tooltext="Evolution tree of your pet"')
             + '    <!-- /%s -->\n' % MARCA)
    return _al_final(boton)(texto)


def fondo() -> bytes:
    """La imagen del fondo: el color de la pagina System con un borde de un pixel, en el formato de w050_01."""
    import struct
    import sys
    sys.path.insert(0, str(RAIZ / 'tools'))
    import fondos_interfaz as fi
    cab, bpp, _filas, paleta = fi.leer(fi.del_cliente(r'shape\wnd01\w050_01.shp'))
    liso, borde = struct.pack('<H', COLOR_FONDO), struct.pack('<H', COLOR_BORDE)
    filas = []
    for y in range(ALTO):
        if y in (0, ALTO - 1):
            filas.append([(0, borde * ANCHO)])
        else:
            filas.append([(0, borde + liso * (ANCHO - 2) + borde)])
    cab = list(cab)
    cab[5] = ANCHO
    return fi.escribir(cab, bpp, filas, paleta)


def main():
    destino = RAIZ / 'parches' / 'extras' / 'shape' / 'wnd01' / (ARCHIVO_FONDO + '.shp')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(fondo())
    _guardar('wnd03.xml', _al_final(bloque_wnd03()))
    _guardar('wnd01.xml', wnd01)
    print('ventana %d (%dx%d) y boton %d listos' % (VENTANA, ANCHO, ALTO, BOTON_MASCOTA))


if __name__ == '__main__':
    main()
