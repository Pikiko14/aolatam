"""El boton de ordenar en la barra de titulo del Prop y de la Backpack (09/11/2026: "necesitamos agregar un ordenador
de mochila y bag, coloca el icono donde esta el mouse y que ordene por categorias de items").

Hace dos cosas, y se puede correr las veces que haga falta:

1. shape/wnd01/aolat_ordenar_{n,f,d}.shp: el boton "?" del titulo (btn003, 14x14, misma paleta y mismo marco en
   reposo / encima / pulsado) con unas barras de mayor a menor en vez del signo.
2. parches/extras/setting/eng/wnd03.xml: el icono 59200 y dos botones, 59201 en el Prop (3031) y 59202 en las diez
   Backpack (3401 ... 3460, que ya comparten sus casillas como hijos). Van a la izquierda del candado, donde el
   usuario tenia el raton. Su OnCommand (AofOrdenarProp / AofOrdenarMochila) lo define server/lua/teclas.lua, que el
   servidor manda por el canal Lua al entrar, y llama a game.netcommand(200, 1|2) -> server/ordenar_bolsa.py.

    python tools/parche_ordenar_bolsa.py
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import fondos_interfaz as fi  # noqa: E402

WND03 = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd03.xml'
SHAPES = RAIZ / 'parches' / 'extras' / 'shape' / 'wnd01'

ICONO = 59200
BOTON_PROP = 59201
BOTON_MOCHILA = 59202
PROP = 3031
MOCHILAS = (3401, 3407, 3418, 3434, 3455, 3456, 3457, 3458, 3459, 3460)
POSICION = '128,-15,14,14'          # en la barra de titulo, a la izquierda del candado (x 150) y la X

FONDO, TRAZO = 1, 2                 # indices de la paleta del btn003: fondo y dibujo (y marco en _f/_d)
# Barras de mayor a menor (filas, columnas) dentro del hueco del "?" (columnas 3..10, filas 2..11).
BARRAS = (((2, 3), range(3, 11)), ((5, 6), range(3, 9)), ((8, 9), range(3, 7)), ((11,), range(3, 5)))


def icono(estado: str) -> bytes:
    cab, bpp, filas, paleta = fi.leer(fi.del_cliente(r'shape\wnd01\btn003_%s.shp' % estado))
    marco = estado != 'n'
    px = [[FONDO] * 14 for _ in range(14)]
    for y in range(14):
        for x in range(14):
            if marco and (x in (0, 13) or y in (0, 13)):
                px[y][x] = TRAZO
    for ys, xs in BARRAS:
        for y in ys:
            for x in xs:
                px[y][x] = TRAZO
    return fi.escribir(cab, bpp, [[(0, bytes(fila))] for fila in px], paleta)


def _boton(wid, funcion, texto):
    return ('    <window class="WND_CLASS_BUTTON" id="%d" range="%s" icon="%d" tooltip="10040" tooltext="%s" '
            'tooldelay="20">\n        <style wsVisible="" wsTab="" />\n        <OnCommand>%s</OnCommand>\n'
            '    </window>\n' % (wid, POSICION, ICONO, texto, funcion))


def wnd03(texto: str) -> str:
    texto = re.sub(r'\n\s*<!-- aolat ordenar -->.*?<!-- /aolat ordenar -->', '', texto, flags=re.S)
    texto = re.sub(r'\n\s*<child>(%d|%d)</child>' % (BOTON_PROP, BOTON_MOCHILA), '', texto)
    for padre, hijo in [(PROP, BOTON_PROP)] + [(m, BOTON_MOCHILA) for m in MOCHILAS]:
        m = re.search(r'<window [^>]*id="%d"[^>]*>\s*<style[^>]*/>' % padre, texto)
        if not m:
            raise SystemExit('no esta la ventana %d en wnd03.xml' % padre)
        texto = texto[:m.end()] + '\n        <child>%d</child>' % hijo + texto[m.end():]
    bloque = ('    <!-- aolat ordenar -->\n'
              '    <icon id="%d" dir="\\wnd01\\" normal="aolat_ordenar_n" focus="aolat_ordenar_f" '
              'down="aolat_ordenar_d" disable="aolat_ordenar_n" />\n' % ICONO
              + _boton(BOTON_PROP, 'AofOrdenarProp', 'Sort items')
              + _boton(BOTON_MOCHILA, 'AofOrdenarMochila', 'Sort items')
              + '    <!-- /aolat ordenar -->')
    fin = texto.rindex('</root>')
    return texto[:fin].rstrip() + '\n' + bloque + '\n' + texto[fin:]


def main():
    SHAPES.mkdir(parents=True, exist_ok=True)
    for estado in 'nfd':
        (SHAPES / ('aolat_ordenar_%s.shp' % estado)).write_bytes(icono(estado))
    crudo = WND03.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    nuevo = wnd03(crudo.decode('utf-8-sig'))
    WND03.write_bytes((b'\xef\xbb\xbf' if bom else b'') + nuevo.encode('utf-8'))
    print('aolat_ordenar_{n,f,d}.shp y wnd03.xml listos')


if __name__ == '__main__':
    main()
