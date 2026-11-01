"""Quita de la ventana de teletransporte (Superwing, Ring of Angel Wings, Angels GO!) los destinos de los mapas
apagados (configuracion.MAPAS_APAGADOS) y las categorias que se quedan vacias.

La lista sale de setting/eng/jumpmap.xml (cada destino: 編號, 場景編號 y sus 類別1..5) y el desplegable de
categorias de jumpmapclass.xml. A los destinos que quedan se les quitan las categorias que desaparecen (los mapas
129-131 son de Heart of Eden y salian tambien en Desert).

SE RENUMERA TODO SIN HUECOS (01/11/2026): el cliente usa el 編號 como POSICION en la lista, igual que en
exchange.xml (tools/canje_straw.py). Quitando filas sin renumerar quedaban categorias 1, 2, 12..18, 20 y destinos
con huecos, y el selector de Ctrl+T salia con mapas repetidos o fallaba al abrirse. Las categorias quedan 1..N (y
los 類別1..5 de cada destino apuntan al numero nuevo) y los destinos 1..M. Como el cliente le manda al servidor el
編號 del destino elegido (0x0151), se escribe tambien server/plantillas/angels_go_renumerado.json {nuevo: original}
para que el servidor siga resolviendolo con angels_go.json.

Al abrir una expansion (borrando su bloque de configuracion.py) y volver a correr esto, sus destinos vuelven.

    python tools/parche_tp_expansiones.py
    python tools/publicar_setting.py jumpmap.xml jumpmapclass.xml --sin-copiar      # parche + VPS
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import configuracion

ENG = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng'
SALIDA = RAIZ / 'parches' / 'extras' / 'setting' / 'eng'
# Categorias que no son una region y se quedan siempre: Show All.
SIEMPRE = {1}


def _filas(texto, etiqueta):
    return list(re.finditer(r'[ \t]*<%s 編號="(\d+)"[^>]*/>\r?\n' % etiqueta, texto))


def generar(apagados=None):
    """(jumpmap, jumpmapclass, destinos quitados, categorias quitadas) ya ajustados, como texto."""
    apagados = set(configuracion.MAPAS_APAGADOS if apagados is None else apagados)
    jm = (ENG / 'jumpmap.xml').read_bytes().decode('utf-8')
    jc = (ENG / 'jumpmapclass.xml').read_bytes().decode('utf-8')
    quitados, quedan_clases, principales = [], set(SIEMPRE), {}
    for m in _filas(jm, '跳地圖'):
        stage = int(re.search(r'場景編號="(\d+)"', m.group(0)).group(1))
        c1 = re.search(r'類別1="(\d+)"', m.group(0))
        if c1:
            principales.setdefault(int(c1.group(1)), set()).add(stage)
        if stage in apagados:
            quitados.append(m)
        else:
            quedan_clases |= {int(v) for v in re.findall(r'類別\d="(\d+)"', m.group(0))}
    # Una region con todos sus mapas propios (類別1) apagados se va aunque otro destino abierto la lleve de
    # segunda categoria (Desert en los 129-131 de Heart of Eden): igual que las pestanas del mapa.
    quedan_clases -= {c for c, st in principales.items() if st <= apagados and c not in SIEMPRE}
    for m in reversed(quitados):
        jm = jm[:m.start()] + jm[m.end():]

    def limpiar(m):                       # categorias que ya no existen fuera de los destinos que quedan
        fila = m.group(0)
        clases = [int(v) for v in re.findall(r'類別\d="(\d+)"', fila) if int(v) in quedan_clases]
        fila = re.sub(r'\s類別\d="\d+"', '', fila)
        extra = ''.join(' 類別%d="%d"' % (i, c) for i, c in enumerate(clases, 1))
        return re.sub(r'(\s*/>)', extra + r'\1', fila, count=1)
    jm = re.sub(r'<跳地圖 編號="\d+"[^>]*/>', limpiar, jm)

    clases_fuera = []
    for m in reversed(_filas(jc, '跳地圖類別')):
        if int(m.group(1)) not in quedan_clases:
            clases_fuera.append(re.search(r'類別名稱="([^"]*)"', m.group(0)).group(1))
            jc = jc[:m.start()] + jc[m.end():]

    # Renumerar sin huecos: categorias 1..N y destinos 1..M (ver la cabecera).
    nueva_clase = {int(m.group(1)): i for i, m in enumerate(_filas(jc, '跳地圖類別'), 1)}
    jc = re.sub(r'(<跳地圖類別 編號=")(\d+)(")', lambda m: '%s%d%s' % (m.group(1), nueva_clase[int(m.group(2))],
                                                                     m.group(3)), jc)
    jm = re.sub(r'(類別\d=")(\d+)(")', lambda m: '%s%d%s' % (m.group(1), nueva_clase[int(m.group(2))], m.group(3)),
                jm)
    original = {}

    def renumerar(m):
        nuevo = len(original) + 1
        original[nuevo] = int(m.group(2))
        return '%s%d%s' % (m.group(1), nuevo, m.group(3))
    jm = re.sub(r'(<跳地圖 編號=")(\d+)(")', renumerar, jm)
    return jm, jc, len(quitados), sorted(clases_fuera), original


RENUMERADO = RAIZ / 'server' / 'plantillas' / 'angels_go_renumerado.json'


def main():
    import json
    jm, jc, n, clases, original = generar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / 'jumpmap.xml').write_bytes(jm.encode('utf-8'))
    (SALIDA / 'jumpmapclass.xml').write_bytes(jc.encode('utf-8'))
    RENUMERADO.write_text(json.dumps({str(k): v for k, v in original.items()}, indent=1) + chr(10),
                          encoding='utf-8')
    print('destinos quitados: %d' % n)
    print('categorias quitadas: %s' % ', '.join(clases))
    print('categorias que quedan: %s' % ', '.join(re.findall(r'類別名稱="([^"]*)"', jc)))


if __name__ == '__main__':
    main()
