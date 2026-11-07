"""La pestana AOF de la ventana System (wnd05.xml, 07/11/2026): el chat con Enter y "Rebind keys..." de la barra.

"habilita desde la config una opcion llamada aof ahi mete la opcion de poder cambiar los key de f1 y asi a lo que
cada usuario quiera se guarde la config en su cliente local". La logica es server/lua/teclas.lua (canal 0x01A0) y
las teclas las cambia el exe con tools/parche_teclas_aof.py.

Lo que cambia en la ventana System (12002): una cuarta pestana "AOF" (59100) tras Sound / Display / Set ITF, que
pasa a no ser la ultima del grupo de radio, y su pagina (59101) con el fondo de la de Set ITF:
    59102  "Chat"                       59103  [x] Press Enter to chat (numbers and letters free for the bar)
    59104  "Quick bar keys"             59105  [Rebind keys...]
    59106  la explicacion
Y el dialogo 59110 "Rebind keys": 12 botones de texto (59120..59131, "Slot 1   F1"), el aviso de arriba (59111) y
Default (59132) / Close (59133). Su OnUpdate (cada frame) espera la tecla.

    python tools/parche_aof_ventana.py
"""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'wnd05.xml'
SALIDA = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd05.xml'

TAB, PAGINA, DIALOGO = 59100, 59101, 59110
SLOT0 = 59120

PAGINA_XML = '''    <!-- AOF: la pestana propia (tools/parche_aof_ventana.py, server/lua/teclas.lua) -->
    <window class="WND_CLASS_BUTTON" id="59100" appdata="59101" range="197,299,50,17" fcolor="101" font="1" icon="12003" check="12004" title="AOF">
        <style wsVisible="" bsVCenter="" bsHCenter="" bsRadio="" bsRadioEnd="" wsTab="" />
        <OnCommand>Setting_ChangePage</OnCommand>
    </window>
    <window class="WND_CLASS_BASE" id="59101" range="0,0,249,343" icon="12081">
        <style wsVisible="" />
        <child>59102</child>
        <child>59103</child>
        <child>59104</child>
        <child>59105</child>
        <child>59106</child>
    </window>
    <window class="WND_CLASS_STATIC" id="59102" range="11,10,1,1" fcolor="103" font="1" title="Chat">
        <style wsVisible="" />
    </window>
    <window class="WND_CLASS_BUTTON" id="59103" range="10,28,220,12" icon="0" check="2383" tpos="17,2" fcolor="103" font="1" title="Press Enter to chat">
        <style wsVisible="" bsCheck="" wsTab="" />
        <OnCommand>AofChatEnter</OnCommand>
    </window>
    <window class="WND_CLASS_STATIC" id="59104" range="11,56,1,1" fcolor="103" font="1" title="Quick bar keys">
        <style wsVisible="" />
    </window>
    <window class="WND_CLASS_BUTTON" id="59105" range="14,74,110,18" fcolor="101" font="1" icon="12006" title="Rebind keys...">
        <style wsVisible="" bsVCenter="" bsHCenter="" wsTab="" />
        <OnCommand>AofAbrirTeclas</OnCommand>
    </window>
    <window class="WND_CLASS_MSTATIC" id="59106" range="11,104,226,120" lines="8" words="36" fcolor="103" font="1" title="">
        <style wsVisible="" />
    </window>
    <window class="WND_CLASS_DLG_1" id="59110" range="0,0,210,338" title="Rebind keys" fcolor="104" font="1">
        <style wsVisible="" wsMoveable="" />
        <OnUpdate>AofTeclasUpdate</OnUpdate>
        <OnClose>AofCerrarTeclas</OnClose>
        <child>59111</child>
{hijos}
        <child>59132</child>
        <child>59133</child>
    </window>
    <window class="WND_CLASS_STATIC" id="59111" range="10,6,190,14" fcolor="103" font="1" title="Click a slot, then press a key.">
        <style wsVisible="" ssVCenter="" />
    </window>
{botones}
    <window class="WND_CLASS_BUTTON" id="59132" range="12,300,55,18" fcolor="101" font="1" icon="12006" title="Default">
        <style wsVisible="" bsVCenter="" bsHCenter="" wsTab="" />
        <OnCommand>AofTeclasDefecto</OnCommand>
    </window>
    <window class="WND_CLASS_BUTTON" id="59133" range="143,300,55,18" fcolor="101" font="1" icon="12006" title="Close">
        <style wsVisible="" bsVCenter="" bsHCenter="" wsTab="" />
        <OnCommand>AofCerrarTeclas</OnCommand>
    </window>
'''

BOTON_SLOT = '''    <window class="WND_CLASS_BUTTON" id="{id}" range="14,{y},180,18" icon="0" tpos="4,3" fcolor="103" font="1" title="Slot {n}">
        <style wsVisible="" wsTab="" />
        <OnCommand>AofElegirSlot</OnCommand>
    </window>'''


def generar(texto: str) -> str:
    if 'id="%d"' % TAB in texto:
        raise SystemExit('wnd05.xml ya lleva la pestana AOF')
    nl = '\r\n' if '\r\n' in texto else '\n'
    # 1. La ventana System: la pestana y su pagina como hijas.
    m = re.search(r'(<window class="WND_CLASS_DLG_1" id="12002"[^>]*>.*?)(\s*</window>)', texto, re.S)
    if not m or '<child>12081</child>' not in m.group(1):
        raise SystemExit('no encuentro la ventana System (12002)')
    texto = (texto[:m.end(1)] + nl + '        <child>%d</child>' % TAB + nl + '        <child>%d</child>' % PAGINA
             + texto[m.end(1):])
    # 2. Set ITF deja de ser la ultima del grupo de radio.
    m = re.search(r'<window class="WND_CLASS_BUTTON" id="12005"[^>]*>\s*<style[^>]*>', texto)
    if not m or 'bsRadioEnd=""' not in m.group(0):
        raise SystemExit('no encuentro la pestana Set ITF (12005)')
    texto = texto[:m.start()] + m.group(0).replace(' bsRadioEnd=""', '') + texto[m.end():]
    # 3. Las ventanas nuevas, antes del cierre del archivo.
    hijos = nl.join('        <child>%d</child>' % (SLOT0 + i) for i in range(12))
    botones = nl.join(BOTON_SLOT.format(id=SLOT0 + i, y=26 + 22 * i, n=i + 1) for i in range(12))
    nuevo = PAGINA_XML.replace('{hijos}', hijos).replace('{botones}', botones).replace('\n', nl)
    pos = texto.rindex('</root>')
    return texto[:pos] + nuevo + texto[pos:]


def main():
    crudo = ORIGEN.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo[3:].decode('utf-8') if bom else crudo.decode('utf-8')
    SALIDA.write_bytes((b'\xef\xbb\xbf' if bom else b'') + generar(texto).encode('utf-8'))
    print('escrito', SALIDA)


if __name__ == '__main__':
    main()
