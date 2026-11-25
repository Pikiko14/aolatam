"""El panel de las misiones diarias (25/11/2026): "que tengamos algun panel para las diarias".

Como las ventanas del Angel MOBA (tools/ventana_moba.py) y Pet Defense (de donde salen las piezas comunes): un DLG_1
con el contenido sobre un fondo propio en una hija BASE, la ULTIMA de la lista.

  * 58800: el titulo (y cuanto falta para el reinicio), la racha, las 3 diarias y las 3 semanales (texto, progreso y una
    barra WND_CLASS_PROGRESS como las de la raid) y el pie con los premios. Lo llena server/lua/misiones.lua.
  * El boton de la barra es el 59007, en el hueco que dejo el del MOBA (59006, quitado el 24/11/2026).

Ids: ventana y textos 58800..58839, iconos 58850..58852 (libres en wnd01..wnd05).

    python tools/ventana_misiones.py [--vista CARPETA]
"""
import pathlib
import re
import sys

from PIL import Image, ImageDraw, ImageEnhance

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import ventana_pet_defense as vp  # noqa: E402
from icono_subasta import ALTO, ANCHO, SALIDA, a_shp, al_estilo_nativo  # noqa: E402

MARCA = 'aolat misiones diarias'
V_MD, L_TITULO, L_RACHA, L_RACHA2, L_PIE, L_FONDO = 58800, 58801, 58802, 58803, 58804, 58805
L_TEXTO, L_ESTADO, L_BARRA = 58810, 58820, 58830          # + 0..5 (3 diarias y 3 semanales)
I_FONDO, I_BARRA = 58850, 58851
BOTON_BARRA, X_BARRA, Y_BARRA, NOMBRE_BOTON = 59007, 121, -127, 'aolat_md'
N_FILAS = 6
W, H = 420, 368
RACHA = (6, 24, W - 7, 62)
SECCION_Y = (68, 208)                 # "TODAY" y "THIS WEEK"
FILA_Y0 = (84, 224)
PASO = 40
BARRA_X, BARRA_W, BARRA_H = 14, W - 28, 6
ESTADO_W = 110


def fila_y(i):
    return FILA_Y0[i // 3] + PASO * (i % 3)


def fondo():
    im = vp._degradado(W, H, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, H - 1), outline=vp._rgba(vp.LINEA))
    d.rounded_rectangle(RACHA, radius=6, fill=vp._rgba(vp.SUPERFICIE), outline=vp._rgba(vp.LINEA))
    f = vp._fuente('segoeuib.ttf', 11)
    for y, texto in zip(SECCION_Y, ('TODAY', 'THIS WEEK')):
        d.text((10, y), texto, font=f, fill=vp.ORO)
        d.line((10 + int(d.textlength(texto, font=f)) + 8, y + 8, W - 10, y + 8), fill=vp._rgba(vp.LINEA))
    for i in range(N_FILAS):
        y = fila_y(i)
        d.rounded_rectangle((6, y - 2, W - 7, y + PASO - 6), radius=5, fill=vp._rgba(vp.SUPERFICIE_2))
        d.rounded_rectangle((BARRA_X - 1, y + 21, BARRA_X + BARRA_W, y + 22 + BARRA_H), radius=3,
                            fill=(6, 9, 16, 255), outline=vp._rgba(vp.LINEA))
    return im


def barra():
    """El relleno de la barra de progreso: verde del juego, mas claro arriba."""
    im = Image.new('RGBA', (BARRA_W, BARRA_H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    arriba, abajo = (110, 231, 183), vp.ACENTO_OSCURO
    for y in range(BARRA_H):
        v = y / max(1, BARRA_H - 1)
        d.line((0, y, BARRA_W, y), fill=tuple(int(arriba[k] + (abajo[k] - arriba[k]) * v) for k in range(3)) + (255,))
    return im


def icono_barra():
    """El icono de la barra (40x56): un pergamino con tres lineas y un visto verde."""
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (20, 24, 40, 255)

    def r(*xy):
        return [v * k for v in xy]
    d.rounded_rectangle(r(7, 8, 33, 46), radius=3 * k, fill=(238, 222, 180, 255), outline=borde, width=k)
    d.rectangle(r(5, 6, 35, 11), fill=(196, 160, 96, 255), outline=borde, width=k)
    d.rectangle(r(5, 43, 35, 48), fill=(196, 160, 96, 255), outline=borde, width=k)
    for y in (17, 24, 31):
        d.line(r(12, y, 28, y), fill=(120, 96, 60, 255), width=2 * k)
    d.line(r(17, 37, 22, 42), fill=(16, 160, 100, 255), width=3 * k)
    d.line(r(22, 42, 34, 26), fill=(16, 160, 100, 255), width=3 * k)
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def piezas() -> dict:
    p = {'aolat_md_fondo': fondo(), 'aolat_md_barra': barra()}
    normal = al_estilo_nativo(icono_barra())
    p[NOMBRE_BOTON + '_n'] = normal
    p[NOMBRE_BOTON + '_f'] = ImageEnhance.Brightness(normal).enhance(1.25)
    return p


def bloque() -> str:
    hijos = [(L_TITULO, vp._texto(L_TITULO, 10, 4, W - 20, vp.C_BLANCO)),
             (L_RACHA, vp._texto(L_RACHA, RACHA[0] + 8, RACHA[1] + 4, RACHA[2] - RACHA[0] - 16, vp.C_ORO)),
             (L_RACHA2, vp._texto(L_RACHA2, RACHA[0] + 8, RACHA[1] + 20, RACHA[2] - RACHA[0] - 16, vp.C_TENUE))]
    for i in range(N_FILAS):
        y = fila_y(i)
        hijos += [(L_TEXTO + i, vp._texto(L_TEXTO + i, 14, y + 2, W - 40 - ESTADO_W, vp.C_BLANCO)),
                  (L_ESTADO + i, vp._texto(L_ESTADO + i, W - 14 - ESTADO_W, y + 2, ESTADO_W, vp.C_ACENTO, '',
                                           ' ssRight=""')),
                  (L_BARRA + i, vp._w('WND_CLASS_PROGRESS', L_BARRA + i, BARRA_X, y + 22, BARRA_W, BARRA_H,
                                      ' picon="%d"' % I_BARRA, 'wsVisible="" psHorizontal=""'))]
    hijos += [(L_PIE, vp._texto(L_PIE, 10, H - 22, W - 20, vp.C_TENUE)),
              (L_FONDO, vp._w('WND_CLASS_BASE', L_FONDO, 0, 0, W, H, ' icon="%d"' % I_FONDO))]
    xml = [vp._dlg(V_MD, 'Daily Missions', W, H, [c for c, _ in hijos])] + [x for _, x in hijos]
    iconos = [vp._icono(I_FONDO, 'aolat_md_fondo'), vp._icono(I_BARRA, 'aolat_md_barra')]
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA, ''.join(xml), ''.join(iconos), MARCA)


def _quitar_marca(texto):
    return re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\n' % (MARCA, MARCA), '', texto, flags=re.S)


def wnd03(texto: str) -> str:
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'))
    fin = texto.rindex('</root>')
    return (texto[:fin] + bloque() + texto[fin:]).replace('\n', nl)


def wnd01(texto: str) -> str:
    """El boton 59007 en la barra, tras el de Pet Defense (59005). Idempotente."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'))
    texto = re.sub(r'\n[ \t]*<child>%d</child>' % BOTON_BARRA, '', texto)
    m = re.search(r'([ \t]*)<child>59005</child>', texto)
    if not m:
        raise SystemExit('no esta el boton de Pet Defense (59005) en wnd01.xml')
    texto = texto[:m.end()] + '\n' + m.group(1) + '<child>%d</child>' % BOTON_BARRA + texto[m.end():]
    boton_xml = ('    <!-- %s -->\n' % MARCA
                 + '    <window class="WND_CLASS_BUTTON" range="%d,%d,40,56" id="%d" icon="%d" tooltip="10043" '
                   'tooltext="Daily Missions">\n        <style wsVisible="" wsTab="" />\n'
                   '        <OnCommand>OnCommandMisiones</OnCommand>\n    </window>\n'
                   % (X_BARRA, Y_BARRA, BOTON_BARRA, BOTON_BARRA)
                 + '    <icon id="%d" dir="\\wnd01\\" normal="%s_n" focus="%s_f" down="%s_n" disable="normal" />\n'
                   % (BOTON_BARRA, NOMBRE_BOTON, NOMBRE_BOTON, NOMBRE_BOTON)
                 + '    <!-- /%s -->\n' % MARCA)
    fin = texto.rindex('</root>')
    return (texto[:fin] + boton_xml + texto[fin:]).replace('\n', nl)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--vista', help='carpeta donde dejar las piezas en .png para mirarlas')
    a = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    p = piezas()
    for nombre, im in p.items():
        (SALIDA / (nombre + '.shp')).write_bytes(a_shp(im))
        if a.vista:
            pathlib.Path(a.vista).mkdir(parents=True, exist_ok=True)
            im.save(pathlib.Path(a.vista) / (nombre + '.png'))
    vp._reescribir(vp.ENG / 'wnd03.xml', wnd03)
    vp._reescribir(vp.ENG / 'wnd01.xml', wnd01)
    print('Misiones diarias: %d piezas' % len(p))


if __name__ == '__main__':
    main()
