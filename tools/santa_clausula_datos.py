"""Los archivos del cliente para Santa Clausula (server/santa_clausula.py), 05/11/2026.

    python tools/santa_clausula_datos.py

Deja en parches/extras, de donde sale el parche de los jugadores:
  setting/eng/monster.xml   con su fila <npc 編號="23901" ...> (nombre, stats, sprite 111648)
  setting/npc.obd           con su [OBJECT] Sequence = 111648 (carpeta \\mon\\M9001\\ y sus 5 animaciones)
  shape/mon/m9001/111648_{wait,run,att,hurt,dead}.spr
y la misma fila en extracted_paks/update26/setting/eng/monster.xml, que es la que lee el servidor.

Los .spr son los de docs/santa_clausula/sprites (el Wham Ogre recoloreado, ver tools/spr_ewsp.py). Se puede correr
varias veces: no duplica nada.
"""
import pathlib
import shutil
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import santa_clausula as sc  # noqa: E402

EXTRACTED = RAIZ / 'extracted_paks' / 'update26' / 'setting'
EXTRAS = RAIZ / 'parches' / 'extras'
SPRITES = RAIZ / 'docs' / 'santa_clausula' / 'sprites'
ANIMS = ('wait', 'run', 'att', 'hurt', 'dead')


def _con_fila(texto: str) -> str:
    marca = '編號="%d"' % sc.NPC_TYPE
    lineas = texto.split('\r\n')
    lineas = [l for l in lineas if marca not in l]                 # fuera la vieja si la habia
    ultima = max(i for i, l in enumerate(lineas) if l.lstrip().startswith('<npc '))
    lineas.insert(ultima + 1, sc.fila_monster_xml())
    return '\r\n'.join(lineas)


def monster_xml():
    for base in (EXTRAS / 'setting' / 'eng' / 'monster.xml', EXTRACTED / 'eng' / 'monster.xml'):
        if base.is_file():
            origen = base
            break
    texto = _con_fila(origen.read_bytes().decode('utf-8'))
    for destino in (EXTRAS / 'setting' / 'eng' / 'monster.xml', EXTRACTED / 'eng' / 'monster.xml'):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(texto.encode('utf-8'))
    print('monster.xml: fila', sc.NPC_TYPE)


def npc_obd():
    origen = EXTRAS / 'setting' / 'npc.obd'
    if not origen.is_file():
        origen = EXTRACTED / 'npc.obd'
    datos = sin_santa(origen.read_bytes()) + b'\r\n' + sc.bloque_npc_obd().encode('ascii')
    print('npc.obd: Santa con el', sc.SPRITE)
    for destino in (EXTRAS / 'setting' / 'npc.obd', EXTRACTED / 'npc.obd'):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)


def sin_santa(datos: bytes) -> bytes:
    """El npc.obd sin el [OBJECT] de Santa (la carpeta \\mon\\M9001\\ es solo suya): asi no queda el del numero viejo,
    el 119001, que en char3.obd es una pieza de equipo y hacia crashear al cliente."""
    marca = ('Directory = \\mon\\%s\\' % sc.CARPETA).encode()
    partes = datos.split(b'[OBJECT]')
    texto = b'[OBJECT]'.join([partes[0]] + [p for p in partes[1:] if marca not in p])
    return texto.rstrip(b'\r\n') + b'\r\n'


def sprites():
    carpeta = EXTRAS / 'shape' / 'mon' / sc.CARPETA.lower()
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob('%d_*.spr' % sc.SPRITE_VIEJO):
        viejo.unlink()
    for a in ANIMS:
        shutil.copyfile(SPRITES / ('santa_%s.spr' % a), carpeta / ('%d_%s.spr' % (sc.SPRITE, a)))
    print('sprites en', carpeta.relative_to(RAIZ))


if __name__ == '__main__':
    monster_xml()
    npc_obd()
    sprites()
