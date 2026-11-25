"""Las ventanas de los eventos sociales (25/11/2026): "que sea con accion, ej. los duelos: clic en el personaje, duelo, y
ahi colocar el monto; que tengamos un panel de duelos y que se apueste por los demas antes que comiencen" y "para los
usuarios normales nada de comandos".

  * "Duel" en el menu de clic derecho sobre un jugador (565, como "Invite to raid"): el 59661.
  * 58900: la ventanita del duelo. Al retar: "Challenge X", la casilla del oro y Challenge / Cancel. Al que retan:
    "X challenges you for N Gold" y Accept / Decline. La llena server/lua/sociales.lua.
  * 58920: el panel "Events" (boton 59008 de la barra, a la izquierda del de las misiones). "Que se vea mas elaborado,
    con tab buttons" (25/11/2026): cuatro pestanas (Duels, Hunted Hunter, Weekly Vote, Treasure Hunt). Cada una con su
    fondo (cabecera con su icono y color, el contenido y "HOW IT WORKS" abajo); el Lua enseña el grupo de la pestana
    elegida y enciende su boton. La quinta, Calendar ("que salga una 5 tab que sea el calendario de aa, hbf, moba y
    demas"): un boton por dia y los eventos de ese dia con su hora y si ya pasaron, estan en marcha o cuanto falta.

Ids: duelo 58900..58907; el panel 58920 con sus hijos en 57100..57169 e iconos 57170..57179; iconos del duelo
58950..58955; boton de la barra 59008, opcion del menu 59661.

    python tools/ventana_sociales.py [--vista CARPETA]
"""
import pathlib
import re
import sys
from xml.sax.saxutils import quoteattr as _qa

from PIL import Image, ImageDraw, ImageEnhance

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import ventana_pet_defense as vp  # noqa: E402
import estilo_moderno as em  # noqa: E402
from icono_subasta import ALTO, ANCHO, SALIDA, a_shp, al_estilo_nativo  # noqa: E402

MARCA = 'aolat eventos sociales'
MARCA_01 = 'aolat eventos sociales barra'
MENU_JUGADOR, BOTON_MENU = 565, 59661
BOTON_BARRA, X_BARRA, Y_BARRA, NOMBRE_BOTON = 59008, 75, -127, 'aolat_ev'

# --- la ventanita del duelo
V_DU, DU_L1, DU_L2, DU_ORO_L, DU_ORO, DU_OK, DU_NO, DU_FONDO = 58900, 58901, 58902, 58903, 58904, 58905, 58906, 58907
DW, DH = 260, 112
# --- el panel con pestanas
V_SO, W, H = 58920, 500, 420
TABS = (57100, 57101, 57102, 57103, 57109)
ESTADO = 57104                                     # la linea de estado de la cabecera
REGLA = 57105                                      # + 0..3: HOW IT WORKS
# duelos
D_APUESTA_L, D_APUESTA, D_AYUDA, D_FILA, D_A, D_B, D_SIN = 57110, 57111, 57112, 57113, 57118, 57123, 57128
N_DUELOS = 5
# cazador
H_LINEA, H_BOTON, N_CAZA = 57130, 57136, 6
# votacion
V_INFO, V_OPCION, V_MIO, N_OPCIONES = 57140, 57141, 57146, 5
# tesoro
T_LINEA, N_TESORO = 57150, 6
FONDOS = (57160, 57161, 57162, 57163, 57164)
# calendario
C_DIA, C_FILA, C_EST, C_PIE, N_FILAS = 57200, 57210, 57230, 57250, 14
DIA_W, DIA_X0, DIA_PASO = 64, 10, 68
C_FILA_Y0, C_FILA_PASO = 126, 18
# iconos
I_FONDOS = (57170, 57171, 57172, 57173, 57177)
I_DIA_SI, I_DIA_NO = 57178, 57179
I_TAB_SI, I_TAB_NO, I_B454, I_B136 = 57174, 57175, 57176, 57091     # 57091: el verde de 136 de Challenges
I_DU_FONDO, I_B90, I_B80 = 58950, 58952, 58953        # 58953: tambien lo usa Challenges
I_B90_ROJO = 58955

TAB_W, TAB_X0, TAB_PASO = 94, 8, 97
FILA_Y0, FILA_PASO = 126, 26
OPCION_Y0, OPCION_PASO = 124, 26
LINEA_Y0, LINEA_PASO = 104, 22
REGLAS_Y = H - 86

PESTANAS = (('duelo', 'Duels', 'DUELS & BETS', 'Challenge anyone, bet on the others. The winner takes it all.',
             em.ic_espadas),
            ('caza', 'Hunted Hunter', 'HUNTED HUNTER', 'One player is the prey. Everyone else is hunting.',
             em.ic_diana),
            ('voto', 'Weekly Vote', 'WEEKLY VOTE', 'Choose the double EXP maps and the extra events.', em.ic_urna),
            ('tesoro', 'Treasure Hunt', 'TREASURE HUNT', 'Follow the clues and open the chest first.', em.ic_cofre),
            ('calendario', 'Calendar', 'EVENT CALENDAR', 'Every event of the week, in server time.', None))
ACENTO_CALENDARIO = (45, 212, 191)


def ic_calendario(d, cx, cy, c):
    d.rounded_rectangle((cx - 6, cy - 5, cx + 6, cy + 6), radius=1, outline=c, width=2)
    d.line((cx - 6, cy - 2, cx + 6, cy - 2), fill=c, width=2)
    for x in (-3, 3):
        d.line((cx + x, cy - 7, cx + x, cy - 4), fill=c, width=2)
    for x in (-3, 0, 3):
        d.point((cx + x, cy + 2), fill=c)


def _oscuro(c, t):
    return tuple(int(v * t) for v in c)


def _icono_grande(icono, color, lado=40):
    """El icono de la cabecera: dibujado a 18 px y ampliado, sobre un circulo de su color."""
    k = 4
    im = Image.new('RGBA', (lado * k, lado * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, lado * k - 1, lado * k - 1), fill=_oscuro(color, 0.32) + (255,), outline=tuple(color) + (255,),
              width=2 * k)
    peq = Image.new('RGBA', (18, 18), (0, 0, 0, 0))
    icono(ImageDraw.Draw(peq), 9, 9, tuple(color) + (255,))
    grande = peq.resize((int(lado * 0.55) * k, int(lado * 0.55) * k), Image.BICUBIC)
    im.alpha_composite(grande, ((lado * k - grande.width) // 2, (lado * k - grande.height) // 2))
    return im.resize((lado, lado), Image.LANCZOS)


def fondo_pestana(i):
    clave, _tab, titulo, sub, icono = PESTANAS[i]
    acento = em.ACENTOS.get(clave, ACENTO_CALENDARIO)
    icono = icono or ic_calendario
    im = em.fondo(W, H)
    d = ImageDraw.Draw(im)
    d.rectangle((1, 1, W - 2, 27), fill=(16, 22, 38, 255))
    d.line((1, 28, W - 2, 28), fill=em.BORDE + (255,))
    # la cabecera: tarjeta con un velo de su color que se apaga hacia la derecha
    caja = (6, 32, W - 7, 88)
    em.tarjeta(im, caja, acento)
    velo = Image.new('RGBA', (caja[2] - caja[0] - 8, caja[3] - caja[1] - 6))
    vd = ImageDraw.Draw(velo)
    for x in range(velo.width):
        a = max(0.0, 0.22 * (1 - x / (velo.width * 0.7)))
        vd.line((x, 0, x, velo.height), fill=tuple(acento) + (int(255 * a),))
    base = im.crop((caja[0] + 4, caja[1] + 3, caja[0] + 4 + velo.width, caja[1] + 3 + velo.height))
    base.alpha_composite(velo)
    im.paste(base, (caja[0] + 4, caja[1] + 3))
    im.alpha_composite(_icono_grande(icono, acento), (16, 40))
    d = ImageDraw.Draw(im)
    d.text((66, 36), titulo, font=vp._fuente('segoeuib.ttf', 15), fill=tuple(acento))
    d.text((66, 55), sub, font=vp._fuente('segoeui.ttf', 11), fill=em.TEXTO_TENUE)
    # el contenido
    if clave == 'calendario':                         # sin HOW IT WORKS: la lista llega hasta abajo
        em.tarjeta(im, (6, 94, W - 7, H - 6))
        d = ImageDraw.Draw(im)
        for k in range(0, N_FILAS, 2):            # una si, una no
            y = C_FILA_Y0 + C_FILA_PASO * k
            em.fila(d, (10, y - 2, W - 11, y + 15), radio=4)
        return im
    em.tarjeta(im, (6, 94, W - 7, REGLAS_Y - 6))
    d = ImageDraw.Draw(im)
    if clave == 'duelo':
        im.alpha_composite(em.casilla(104), (76, 100))
        for k in range(N_DUELOS):
            y = FILA_Y0 + FILA_PASO * k
            em.fila(d, (10, y - 4, W - 11, y + 18))
    elif clave in ('caza', 'tesoro'):
        n = N_CAZA if clave == 'caza' else N_TESORO
        for k in range(n):
            y = LINEA_Y0 + LINEA_PASO * k
            em.fila(d, (10, y - 3, W - 11, y + 16))
    # HOW IT WORKS
    em.tarjeta(im, (6, REGLAS_Y, W - 7, H - 6), em.ORO)
    em.cabecera(im, (14, REGLAS_Y + 4), 'HOW IT WORKS', em.ic_estrella, em.ORO, tam=10)
    return im


def fondo_duelo():
    im = em.fondo(DW, DH)
    em.tarjeta(im, (4, 3, DW - 5, DH - 4), em.ACENTOS['duelo'])
    im.alpha_composite(em.casilla(136), (60, 52))
    return im


def icono_barra():
    """Dos espadas cruzadas sobre una moneda de oro."""
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (20, 24, 40, 255)

    def r(*xy):
        return [v * k for v in xy]
    d.ellipse(r(10, 22, 30, 42), fill=(250, 204, 21, 255), outline=borde, width=k)
    d.ellipse(r(14, 26, 26, 38), outline=(180, 120, 20, 255), width=k)
    for (x0, y0, x1, y1) in ((7, 8, 31, 36), (33, 8, 9, 36)):
        d.line(r(x0, y0, x1, y1), fill=borde, width=6 * k)
        d.line(r(x0, y0, x1, y1), fill=(226, 232, 240, 255), width=3 * k)
    for (x, y) in ((27, 32), (13, 32)):
        d.line(r(x - 5, y - 1, x + 5, y + 1), fill=(120, 72, 30, 255), width=3 * k)
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def piezas() -> dict:
    p = {'aolat_du_fondo': fondo_duelo()}
    for i in range(len(PESTANAS)):
        p['aolat_ev_fondo%d' % (i + 1)] = fondo_pestana(i)
    for nombre, w, color in (('aolat_ev_b90', 90, 'verde'), ('aolat_ev_b90r', 90, 'rojo'),
                             ('aolat_ev_b80', 80, 'verde'), ('aolat_ev_b454', W - 20, 'azul')):
        for e in ('n', 'f', 's'):
            p['%s_%s' % (nombre, e)] = em.boton(w, 18, color, e)
    for e in ('n', 'f', 's'):
        p['aolat_ev_tabsi_' + e] = em.pestana(TAB_W, 18, True, e)
        p['aolat_ev_tabno_' + e] = em.pestana(TAB_W, 18, False, e)
        p['aolat_ev_diasi_' + e] = em.pestana(DIA_W, 18, True, e)
        p['aolat_ev_diano_' + e] = em.pestana(DIA_W, 18, False, e)
    normal = al_estilo_nativo(icono_barra())
    p[NOMBRE_BOTON + '_n'] = normal
    p[NOMBRE_BOTON + '_f'] = ImageEnhance.Brightness(normal).enhance(1.25)
    return p


def _boton_texto(wid, x, y, w, icono, funcion, titulo='', visible=True):
    return vp._w('WND_CLASS_BUTTON', wid, x, y, w, 18, ' title="%s" icon="%d" fcolor="%d" font="1"'
                 % (vp_escape(titulo), icono, vp.C_BLANCO),
                 ('wsVisible="" ' if visible else '') + 'wsTab="" ssVCenter="" ssHCenter=""',
                 '        <OnCommand>%s</OnCommand>\n' % funcion)


def _edit(wid, x, y, w, limite=9):
    return vp._w('WND_CLASS_EDIT', wid, x, y, w, 14, ' fcolor="%d" font="1" tpos="1,0" limit="%d"'
                 % (vp.C_BLANCO, limite), 'wsVisible="" esNumber="" esVCenter="" wsTab=""')


def bloque() -> str:
    xml = []

    def ventana(wid, titulo, w, h, hijos):
        xml.append(vp._dlg(wid, titulo, w, h, [c for c, _ in hijos]))
        xml.extend(x for _, x in hijos)

    ventana(V_DU, 'Duel', DW, DH, [
        (DU_L1, vp._texto(DU_L1, 10, 8, DW - 20, vp.C_ORO)),
        (DU_L2, vp._texto(DU_L2, 10, 28, DW - 20, vp.C_TENUE)),
        (DU_ORO_L, vp._texto(DU_ORO_L, 14, 54, 44, vp.C_BLANCO, 'Gold:')),
        (DU_ORO, _edit(DU_ORO, 64, 54, 128)),
        (DU_OK, _boton_texto(DU_OK, 34, 84, 90, I_B90, 'OnDueloOk', 'Challenge')),
        (DU_NO, _boton_texto(DU_NO, 136, 84, 90, I_B90_ROJO, 'OnDueloNo', 'Cancel')),
        (DU_FONDO, vp._w('WND_CLASS_BASE', DU_FONDO, 0, 0, DW, DH, ' icon="%d"' % I_DU_FONDO)),
    ])
    hijos = [(TABS[i], _boton_texto(TABS[i], TAB_X0 + TAB_PASO * i, 5, TAB_W, I_TAB_SI if i == 0 else I_TAB_NO,
                                    'OnSocialPestana', PESTANAS[i][1]))
             for i in range(len(PESTANAS))]
    hijos.append((ESTADO, vp._texto(ESTADO, 66, 71, W - 80, vp.C_BLANCO)))
    for i in range(4):
        hijos.append((REGLA + i, vp._texto(REGLA + i, 16, REGLAS_Y + 22 + 15 * i, W - 32, vp.C_TENUE)))
    # duelos
    hijos += [(D_APUESTA_L, vp._texto(D_APUESTA_L, 14, 102, 60, vp.C_BLANCO, 'Your bet:')),
              (D_APUESTA, _edit(D_APUESTA, 79, 102, 98)),
              (D_AYUDA, vp._texto(D_AYUDA, 190, 102, W - 202, vp.C_TENUE))]
    for i in range(N_DUELOS):
        y = FILA_Y0 + FILA_PASO * i
        hijos += [(D_FILA + i, vp._texto(D_FILA + i, 16, y, W - 222, vp.C_BLANCO)),
                  (D_A + i, _boton_texto(D_A + i, W - 204, y - 2, 90, I_B90, 'OnSocialApostarA', visible=False)),
                  (D_B + i, _boton_texto(D_B + i, W - 108, y - 2, 90, I_B90, 'OnSocialApostarB', visible=False))]
    hijos.append((D_SIN, vp._texto(D_SIN, 16, FILA_Y0, W - 32, vp.C_TENUE)))
    # cazador
    for i in range(N_CAZA):
        hijos.append((H_LINEA + i, vp._texto(H_LINEA + i, 16, LINEA_Y0 + LINEA_PASO * i, W - 32, vp.C_BLANCO)))
    hijos.append((H_BOTON, _boton_texto(H_BOTON, (W - 136) // 2, LINEA_Y0 + LINEA_PASO * N_CAZA + 6, 136, I_B136,
                                        'OnSocialCaza', 'Join', visible=False)))
    # votacion
    hijos.append((V_INFO, vp._texto(V_INFO, 16, 102, W - 32, vp.C_TENUE)))
    for i in range(N_OPCIONES):
        hijos.append((V_OPCION + i, _boton_texto(V_OPCION + i, 10, OPCION_Y0 + OPCION_PASO * i, W - 20, I_B454,
                                                 'OnSocialVotar', visible=False)))
    hijos.append((V_MIO, vp._texto(V_MIO, 16, OPCION_Y0 + OPCION_PASO * N_OPCIONES + 4, W - 32, vp.C_ORO)))
    # tesoro
    for i in range(N_TESORO):
        hijos.append((T_LINEA + i, vp._texto(T_LINEA + i, 16, LINEA_Y0 + LINEA_PASO * i, W - 32,
                                             vp.C_ORO if i == 0 else vp.C_BLANCO)))
    # calendario
    for i, dia in enumerate(('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')):
        hijos.append((C_DIA + i, _boton_texto(C_DIA + i, DIA_X0 + DIA_PASO * i, 100, DIA_W, I_DIA_NO, 'OnSocialDia',
                                              dia, visible=False)))
    for i in range(N_FILAS):
        y = C_FILA_Y0 + C_FILA_PASO * i
        hijos += [(C_FILA + i, vp._texto(C_FILA + i, 16, y, W - 150, vp.C_BLANCO)),
                  (C_EST + i, vp._texto(C_EST + i, W - 130, y, 116, vp.C_ACENTO))]
    hijos.append((C_PIE, vp._texto(C_PIE, 16, C_FILA_Y0 + C_FILA_PASO * N_FILAS + 4, W - 32, vp.C_TENUE)))
    for i, f in enumerate(FONDOS):                     # los fondos, debajo de todo
        hijos.append((f, vp._w('WND_CLASS_BASE', f, 0, 0, W, H, ' icon="%d"' % I_FONDOS[i])))
    ventana(V_SO, 'Events', W, H, hijos)

    iconos = [vp._icono(I_DU_FONDO, 'aolat_du_fondo')]
    iconos += [vp._icono(I_FONDOS[i], 'aolat_ev_fondo%d' % (i + 1)) for i in range(len(PESTANAS))]
    for iid, nombre in ((I_B90, 'aolat_ev_b90'), (I_B90_ROJO, 'aolat_ev_b90r'), (I_B80, 'aolat_ev_b80'),
                        (I_B454, 'aolat_ev_b454'),
                        (I_TAB_SI, 'aolat_ev_tabsi'), (I_TAB_NO, 'aolat_ev_tabno'),
                        (I_DIA_SI, 'aolat_ev_diasi'), (I_DIA_NO, 'aolat_ev_diano')):
        iconos.append(vp._icono(iid, nombre + '_n', nombre + '_f', nombre + '_s'))
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA, ''.join(xml), ''.join(iconos), MARCA)


def _quitar_marca(texto, marca):
    return re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\n' % (marca, marca), '', texto, flags=re.S)


def wnd03(texto: str) -> str:
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'), MARCA)
    fin = texto.rindex('</root>')
    return (texto[:fin] + bloque() + texto[fin:]).replace('\n', nl)


def wnd01(texto: str) -> str:
    """El boton 59008 en la barra (tras el de las misiones, 59007) y "Duel" (59661) en el menu del jugador (565)."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'), MARCA_01)
    texto = re.sub(r'\n[ \t]*<child>(%d|%d)</child>' % (BOTON_BARRA, BOTON_MENU), '', texto)
    m = re.search(r'([ \t]*)<child>59007</child>', texto)
    if not m:
        raise SystemExit('no esta el boton de las misiones (59007) en wnd01.xml')
    texto = texto[:m.end()] + '\n' + m.group(1) + '<child>%d</child>' % BOTON_BARRA + texto[m.end():]
    m = re.search(r'<window [^>]*\bid="%d"[^>]*>\s*<style[^>]*/>' % MENU_JUGADOR, texto)
    if not m:
        raise SystemExit('no esta el menu del jugador (%d) en wnd01.xml' % MENU_JUGADOR)
    texto = texto[:m.end()] + '\n        <child>%d</child>' % BOTON_MENU + texto[m.end():]
    extra = ('    <!-- %s -->\n' % MARCA_01
             + '    <window class="WND_CLASS_BUTTON" range="%d,%d,40,56" id="%d" icon="%d" tooltip="10043" '
               'tooltext="Events">\n        <style wsVisible="" wsTab="" />\n'
               '        <OnCommand>OnCommandEventos</OnCommand>\n    </window>\n'
             % (X_BARRA, Y_BARRA, BOTON_BARRA, BOTON_BARRA)
             + vp._icono(BOTON_BARRA, NOMBRE_BOTON + '_n', NOMBRE_BOTON + '_f', NOMBRE_BOTON + '_n')
             + '    <window class="WND_CLASS_BUTTON" range="2,175,110,12" id="%d" fcolor="106" font="1" '
               'title="Duel">\n        <style ssVCenter="" ssHCenter="" wsTab="" />\n'
               '        <OnCommand>OnClickChatOptionDuelo</OnCommand>\n    </window>\n' % BOTON_MENU
             + '    <!-- /%s -->\n' % MARCA_01)
    fin = texto.rindex('</root>')
    return (texto[:fin] + extra + texto[fin:]).replace('\n', nl)


def vp_escape(t):
    return _qa(str(t))[1:-1]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--vista', help='carpeta donde dejar las piezas en .png para mirarlas')
    a = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, im in piezas().items():
        (SALIDA / (nombre + '.shp')).write_bytes(a_shp(im))
        if a.vista:
            pathlib.Path(a.vista).mkdir(parents=True, exist_ok=True)
            im.save(pathlib.Path(a.vista) / (nombre + '.png'))
    vp._reescribir(vp.ENG / 'wnd01.xml', wnd01)
    vp._reescribir(vp.ENG / 'wnd03.xml', wnd03)
    print('ventanas de los eventos sociales: piezas', len(piezas()))


if __name__ == '__main__':
    main()
