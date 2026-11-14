"""La pestana Bulk Sell de la tienda NPC (13/11/2026, "una opcion al lado de Sell que diga bulk sell, de la opcion de
vender todo: que todo el gear y las armas salgan seleccionados por defecto y el boton confirm sell lo venda").

La tienda es la 13401 de wnd04.xml (WND_CLASS_DLG_1 "Store"), con las pestanas Buy (13402 -> pagina 13404) y Sell
(13403 -> pagina 13405). Aqui se le anade:
  * 13406, el boton "Bulk" junto a Sell (OnNPCSale_ChaPage_Bulk);
  * 13407, su pagina (con el mismo fondo que la de vender, el icono 13402), oculta hasta pulsar la pestana:
      13408 la lista (una fila por objeto: "[x] nombre  precio G"; pulsar una fila la marca o desmarca),
      13410 su barra, 13414 el estado ("12 of 14 selected"), 13413 el total y 13409 el check que vende (con su
      rotulo 13415 "Confirm sell").
La logica es server/lua/venta_masiva.lua (llega por el canal 0x01A0 en el saludo) y la del servidor app._venta_masiva.

    python tools/parche_venta_masiva.py
    python tools/generar_parche.py
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import ventana_login as vl  # noqa: E402

RELATIVA = r'setting\eng\wnd04.xml'
MARCA = 'aolat venta masiva'
HIJOS = (13406, 13407)


def bloque(nl):
    lineas = [
        '<!-- %s -->' % MARCA,
        '<window class="WND_CLASS_BUTTON" id="13406" range="84,231,40,16" icon="3084" title="Bulk" fcolor="103" '
        'font="1" tooltip="10040" tooltext="Sell all your gear and weapons at once">',
        '    <style wsVisible="" bsHCenter="" bsVCenter="" wsTab="" />',
        '    <OnCommand>OnNPCSale_ChaPage_Bulk</OnCommand>',
        '</window>',
        '<window class="WND_CLASS_BASE" range="0,0,205,274" id="13407" icon="13402">',
        '    <child>13408</child>',
        '    <child>13414</child>',
        '    <child>13413</child>',
        '    <child>13415</child>',
        '    <child>13409</child>',
        '</window>',
        '<window class="WND_CLASS_LIST" id="13408" range="4,4,248,186" cols="1" rows="11" gapx="0" gapy="2" '
        'fcolor="103" font="1" bcolor="13400" tpos="2,1">',
        '    <style wsVisible="" lsVScroll="" lsCheck="" lsSCheck="" wsTab="" />',
        '    <child>13410</child>',
        '    <OnCommand>OnVentaMasivaFila</OnCommand>',
        '</window>',
        '<window class="WND_CLASS_SCROLLBAR" id="13410" range="249,-1,9,188" uicon="131" dicon="132" ticon="133" '
        'urange="0,0,9,10" drange="0,178,9,10" trange="0,10,9,168" thumbmin="8">',
        '    <style wsVisible="" csVScroll="" csSimple="" />',
        '</window>',
        '<window class="WND_CLASS_STATIC" id="13414" range="6,195,250,14" fcolor="103" font="1" title="">',
        '    <style wsVisible="" ssVCenter="" />',
        '</window>',
        '<window class="WND_CLASS_STATIC" id="13413" range="98,215,78,14" fcolor="103" font="1" title="0">',
        '    <style wsVisible="" ssVCenter="" ssRight="" />',
        '</window>',
        '<window class="WND_CLASS_STATIC" id="13415" range="150,256,80,14" fcolor="103" font="1" title="Confirm sell">',
        '    <style wsVisible="" ssVCenter="" ssRight="" />',
        '</window>',
        '<window class="WND_CLASS_BUTTON" id="13409" range="233,253,26,18" icon="1154" tooltip="10040" '
        'tooltext="Confirm sell">',
        '    <style wsVisible="" wsTab="" />',
        '    <OnCommand>OnVentaMasivaVender</OnCommand>',
        '</window>',
        '<!-- /%s -->' % MARCA,
    ]
    return ''.join('    ' + l + nl for l in lineas)


def wnd04():
    texto, bom, nl = vl._base(RELATIVA)
    texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\r?\n' % (MARCA, MARCA), '', texto, flags=re.S)
    m = vl._ventana(texto, 13401)
    fin = texto.index('</window>', m.end())
    hijos = texto[m.end():fin]
    # EL ORDEN IMPORTA: el juego pinta los hijos del ultimo al primero. Con el boton 13406 al final de la lista lo
    # tapaba la pagina de Sell (13405, 205 px de ancho) y salia un "Bu.." apagado (13/11/2026, "no se ve el bulk
    # sell"). El boton va junto a Buy/Sell, delante de las paginas; la pagina nueva detras de las otras dos.
    # Se quitan primero: la copia de extracted_paks puede traer ya los nuestros (se volco ahi el parche).
    hijos = re.sub(r'[ \t]*<child>(?:%s)</child>\r?\n?' % '|'.join(map(str, HIJOS)), '', hijos)
    for h, tras in ((13406, 13403), (13407, 13405)):
        hijos = hijos.replace('<child>%d</child>' % tras, '<child>%d</child>%s        <child>%d</child>' % (tras, nl, h), 1)
    texto = texto[:m.end()] + hijos + texto[fin:]
    fin = texto.rindex('</')
    texto = texto[:fin] + bloque(nl) + texto[fin:]
    vl._guardar(RELATIVA, texto, bom)
    return texto


if __name__ == '__main__':
    t = wnd04()
    print('wnd04.xml con la pestana Bulk Sell (%d bytes)' % len(t))
