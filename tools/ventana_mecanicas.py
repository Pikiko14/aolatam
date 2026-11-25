"""Las ventanas de las mecanicas nuevas (25/11/2026), sin comandos para los jugadores:

  * 57000 "Challenges" (boton 59009 de la barra, a la izquierda del de Events) con tres pestanas:
      - Contracts: el tablon (6 por pagina, con Deliver / Cancel), y abajo publicar: Item/Boss, buscar por nombre,
        < > entre lo encontrado, cantidad, recompensa y Post.
      - Pet Tournament: tu mascota, el proximo torneo, tres botones de estrategia (inscribirse con ella) y Leave, y los
        resultados del ultimo torneo y tus combates.
      - Hardcore: tu estado, Start Hardcore y el ranking de la temporada.
  * 58960 "Tower Blessing": las tres bendiciones de la Torre de Babel roguelike (nombre = boton, lo bueno en verde y
    lo malo en rojo).
Lo llenan server/lua/mecanicas.lua y server/lua/roguelike.lua.

    python tools/ventana_mecanicas.py [--vista CARPETA]
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

MARCA = 'aolat mecanicas'
MARCA_01 = 'aolat mecanicas barra'
BOTON_BARRA, X_BARRA, Y_BARRA, NOMBRE_BOTON = 59009, 29, -127, 'aolat_ch'

V_CH, W, H = 57000, 440, 330
TABS = (57001, 57002, 57003)
AYUDA = 57004
# contratos
C_FILA, C_BOTON, C_ANT, C_SIG, C_PAG = 57010, 57016, 57022, 57023, 57024
C_TIPO, C_BUSCA, C_FIND, C_RANT, C_RSIG, C_RESULT = 57025, 57026, 57027, 57028, 57029, 57030
C_CANT_L, C_CANT, C_ORO_L, C_ORO, C_POST, C_TITULO = 57031, 57032, 57033, 57034, 57035, 57036
C_CAJAS = (57037, 57038, 57039)
# torneo
P_LINEA, P_ESTRATEGIA, P_SALIR, P_RES = 57040, 57045, 57048, 57050
# hardcore
H_LINEA, H_EMPEZAR, H_RANK = 57060, 57064, 57065
CH_FONDO = 57080
I_FONDO, I_B136, I_B30, I_CAJA_BUSCA, I_CAJA_CANT, I_CAJA_ORO = 57090, 57091, 57093, 57095, 57096, 57097
I_TAB_SI, I_TAB_NO = 57098, 57099           # pestana elegida / apagada (el Lua cambia el icono)
I_B80 = 58953                       # de tools/ventana_sociales.py

V_TB, TW, TH = 58960, 444, 150
TB_TITULO, TB_PIE, TB_NOMBRE, TB_BUENO, TB_MALO, TB_FONDO = 58961, 58962, 58963, 58966, 58969, 58972
I_TB_FONDO, I_B140 = 58973, 58974

CAJA_BUSCA, CAJA_CANT, CAJA_ORO = (100, 230, 124), (52, 276, 64), (190, 276, 114)


def _fondo(w, h):
    im = vp._degradado(w, h, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=vp._rgba(vp.LINEA))
    return im, d


# "Que se vean mas amigables y modernas" (25/11/2026): estilo_moderno (fondo con resplandor, tarjetas, botones con
# degradado y pestanas que se encienden).
def fondo_challenges():
    im = em.fondo(W, H)
    d = ImageDraw.Draw(im)
    d.rectangle((1, 1, W - 2, 23), fill=(16, 22, 38, 255))
    d.line((1, 24, W - 2, 24), fill=em.BORDE + (255,))
    em.tarjeta(im, (4, 27, W - 5, H - 4))
    return im


def fondo_bendicion():
    im = em.fondo(TW, TH)
    em.cabecera(im, (TW - 26, 9), '', em.ic_estrella, em.ORO)
    for i in range(3):
        x = 8 + i * 146
        em.tarjeta(im, (x, 30, x + 138, 114), em.ORO)
    return im


def caja(w):
    return em.casilla(w)


def icono_barra():
    """Un pergamino de encargo con un sello rojo y una pata de mascota."""
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (20, 24, 40, 255)

    def r(*xy):
        return [v * k for v in xy]
    d.polygon(r(6, 10, 30, 6, 34, 44, 10, 48), fill=(238, 222, 180, 255), outline=borde)
    for y in (16, 22, 28):
        d.line(r(12, y, 28, y - 3), fill=(120, 96, 60, 255), width=2 * k)
    d.ellipse(r(22, 32, 36, 46), fill=(200, 40, 50, 255), outline=borde, width=k)
    for (x, y) in ((26, 36), (32, 36), (25, 40), (33, 40)):
        d.ellipse(r(x - 1, y - 1, x + 1, y + 1), fill=(255, 220, 220, 255))
    d.ellipse(r(27, 39, 31, 43), fill=(255, 220, 220, 255))
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def piezas() -> dict:
    p = {'aolat_ch_fondo': fondo_challenges(), 'aolat_tb_fondo': fondo_bendicion(),
         'aolat_ch_caja1': caja(CAJA_BUSCA[2]), 'aolat_ch_caja2': caja(CAJA_CANT[2]), 'aolat_ch_caja3': caja(CAJA_ORO[2])}
    for nombre, w, color in (('aolat_ch_b136', 136, 'verde'), ('aolat_ch_b30', 30, 'azul'),
                             ('aolat_tb_b140', 138, 'oro')):
        for e in ('n', 'f', 's'):
            p['%s_%s' % (nombre, e)] = em.boton(w, 18, color, e)
    for e in ('n', 'f', 's'):
        p['aolat_ch_tabsi_' + e] = em.pestana(136, 18, True, e)
        p['aolat_ch_tabno_' + e] = em.pestana(136, 18, False, e)
    normal = al_estilo_nativo(icono_barra())
    p[NOMBRE_BOTON + '_n'] = normal
    p[NOMBRE_BOTON + '_f'] = ImageEnhance.Brightness(normal).enhance(1.25)
    return p


def _boton(wid, x, y, w, icono, funcion, titulo='', visible=True):
    return vp._w('WND_CLASS_BUTTON', wid, x, y, w, 18, ' title="%s" icon="%d" fcolor="%d" font="1"'
                 % (vp_escape(titulo), icono, vp.C_BLANCO), ('wsVisible="" ' if visible else '') + 'wsTab="" ssVCenter="" ssHCenter=""',
                 '        <OnCommand>%s</OnCommand>\n' % funcion)


def _edit(wid, x, y, w, numero=True, limite=9):
    return vp._w('WND_CLASS_EDIT', wid, x + 3, y + 2, w - 6, 14, ' fcolor="%d" font="1" tpos="1,0" limit="%d"'
                 % (vp.C_BLANCO, limite), 'wsVisible="" ' + ('esNumber="" ' if numero else '') + 'esVCenter="" wsTab=""')


def _texto(wid, x, y, w, color, titulo=''):
    return vp._texto(wid, x, y, w, color, titulo)


def bloque() -> str:
    xml = []

    def ventana(wid, titulo, w, h, hijos):
        xml.append(vp._dlg(wid, titulo, w, h, [c for c, _ in hijos]))
        xml.extend(x for _, x in hijos)

    hijos = [(TABS[i], _boton(TABS[i], 8 + 144 * i, 3, 136, I_TAB_SI if i == 0 else I_TAB_NO, 'OnCHPestana', t))
             for i, t in enumerate(('Contracts', 'Pet Tournament', 'Hardcore'))]
    hijos.append((AYUDA, _texto(AYUDA, 10, 29, W - 20, vp.C_TENUE)))
    # contratos
    for i in range(6):
        y = 48 + 22 * i
        hijos += [(C_FILA + i, _texto(C_FILA + i, 10, y, 334, vp.C_BLANCO)),
                  (C_BOTON + i, _boton(C_BOTON + i, 350, y - 1, 80, I_B80, 'OnCHFila'))]
    hijos += [(C_ANT, _boton(C_ANT, 10, 184, 30, I_B30, 'OnCHPagAnt', '<')),
              (C_SIG, _boton(C_SIG, 44, 184, 30, I_B30, 'OnCHPagSig', '>')),
              (C_PAG, _texto(C_PAG, 82, 186, 340, vp.C_TENUE)),
              (C_TITULO, _texto(C_TITULO, 10, 208, 300, vp.C_ORO, 'POST A CONTRACT')),
              (C_TIPO, _boton(C_TIPO, 10, 229, 80, I_B80, 'OnCHTipo', 'Item')),
              (C_BUSCA, _edit(C_BUSCA, *CAJA_BUSCA, numero=False, limite=16)),
              (C_FIND, _boton(C_FIND, 232, 229, 80, I_B80, 'OnCHBuscar', 'Find')),
              (C_RANT, _boton(C_RANT, 318, 229, 30, I_B30, 'OnCHResAnt', '<')),
              (C_RSIG, _boton(C_RSIG, 352, 229, 30, I_B30, 'OnCHResSig', '>')),
              (C_RESULT, _texto(C_RESULT, 10, 254, W - 20, vp.C_ACENTO)),
              (C_CANT_L, _texto(C_CANT_L, 10, 278, 40, vp.C_BLANCO, 'Qty:')),
              (C_CANT, _edit(C_CANT, *CAJA_CANT, limite=3)),
              (C_ORO_L, _texto(C_ORO_L, 128, 278, 60, vp.C_BLANCO, 'Reward:')),
              (C_ORO, _edit(C_ORO, *CAJA_ORO, limite=9)),
              (C_POST, _boton(C_POST, 350, 275, 80, I_B80, 'OnCHPublicar', 'Post'))]
    for cid, (x, y, w), iid in zip(C_CAJAS, (CAJA_BUSCA, CAJA_CANT, CAJA_ORO), (I_CAJA_BUSCA, I_CAJA_CANT, I_CAJA_ORO)):
        hijos.append((cid, vp._w('WND_CLASS_BASE', cid, x, y, w, 18, ' icon="%d"' % iid)))
    # torneo
    for i in range(5):
        hijos.append((P_LINEA + i, _texto(P_LINEA + i, 10, 48 + 18 * i, W - 20, vp.C_BLANCO)))
    for i, t in enumerate(('Aggressive', 'Defensive', 'Tricky')):
        hijos.append((P_ESTRATEGIA + i, _boton(P_ESTRATEGIA + i, 8 + 144 * i, 142, 136, I_B136, 'OnCHEstrategia', t,
                                               visible=False)))
    hijos.append((P_SALIR, _boton(P_SALIR, 350, 166, 80, I_B80, 'OnCHSalirTorneo', 'Leave', visible=False)))
    for i in range(8):
        hijos.append((P_RES + i, _texto(P_RES + i, 10, 194 + 16 * i, W - 20, vp.C_TENUE)))
    # hardcore
    for i in range(4):
        hijos.append((H_LINEA + i, _texto(H_LINEA + i, 10, 48 + 18 * i, W - 20, vp.C_BLANCO)))
    hijos.append((H_EMPEZAR, _boton(H_EMPEZAR, 152, 126, 136, I_B136, 'OnCHHardcore', 'Start Hardcore', visible=False)))
    for i in range(10):
        hijos.append((H_RANK + i, _texto(H_RANK + i, 10, 156 + 16 * i, W - 20, vp.C_TENUE)))
    hijos.append((CH_FONDO, vp._w('WND_CLASS_BASE', CH_FONDO, 0, 0, W, H, ' icon="%d"' % I_FONDO)))
    ventana(V_CH, 'Challenges', W, H, hijos)

    tb = [(TB_TITULO, _texto(TB_TITULO, 10, 8, TW - 20, vp.C_ORO))]
    for i in range(3):
        x = 8 + i * 146
        tb += [(TB_NOMBRE + i, _boton(TB_NOMBRE + i, x, 38, 138, I_B140, 'OnTorreBendicion')),
               (TB_BUENO + i, _texto(TB_BUENO + i, x + 6, 66, 128, vp.C_ACENTO)),
               (TB_MALO + i, _texto(TB_MALO + i, x + 6, 86, 128, vp.C_ROJO))]
    tb += [(TB_PIE, _texto(TB_PIE, 10, 124, TW - 20, vp.C_TENUE)),
           (TB_FONDO, vp._w('WND_CLASS_BASE', TB_FONDO, 0, 0, TW, TH, ' icon="%d"' % I_TB_FONDO))]
    ventana(V_TB, 'Tower Blessing', TW, TH, tb)

    iconos = [vp._icono(I_FONDO, 'aolat_ch_fondo'), vp._icono(I_TB_FONDO, 'aolat_tb_fondo'),
              vp._icono(I_CAJA_BUSCA, 'aolat_ch_caja1'), vp._icono(I_CAJA_CANT, 'aolat_ch_caja2'),
              vp._icono(I_CAJA_ORO, 'aolat_ch_caja3')]
    for iid, nombre in ((I_B136, 'aolat_ch_b136'), (I_B30, 'aolat_ch_b30'), (I_B140, 'aolat_tb_b140'),
                        (I_TAB_SI, 'aolat_ch_tabsi'), (I_TAB_NO, 'aolat_ch_tabno')):
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
    """El boton 59009 en la barra, tras el de Events (59008). Idempotente."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'), MARCA_01)
    texto = re.sub(r'\n[ \t]*<child>%d</child>' % BOTON_BARRA, '', texto)
    m = re.search(r'([ \t]*)<child>59008</child>', texto)
    if not m:
        raise SystemExit('no esta el boton de Events (59008) en wnd01.xml: antes tools/ventana_sociales.py')
    texto = texto[:m.end()] + '\n' + m.group(1) + '<child>%d</child>' % BOTON_BARRA + texto[m.end():]
    extra = ('    <!-- %s -->\n' % MARCA_01
             + '    <window class="WND_CLASS_BUTTON" range="%d,%d,40,56" id="%d" icon="%d" tooltip="10043" '
               'tooltext="Challenges">\n        <style wsVisible="" wsTab="" />\n'
               '        <OnCommand>OnCommandChallenges</OnCommand>\n    </window>\n'
             % (X_BARRA, Y_BARRA, BOTON_BARRA, BOTON_BARRA)
             + vp._icono(BOTON_BARRA, NOMBRE_BOTON + '_n', NOMBRE_BOTON + '_f', NOMBRE_BOTON + '_n')
             + '    <!-- /%s -->\n' % MARCA_01)
    fin = texto.rindex('</root>')
    return (texto[:fin] + extra + texto[fin:]).replace('\n', nl)


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
    print('ventanas de las mecanicas: piezas', len(piezas()))


def vp_escape(t):
    return _qa(str(t))[1:-1]


if __name__ == '__main__':
    main()

