"""Exportacion de mapas de Dos Coronas desde el editor: .json (capas en RLE) y .lua (tabla `return { ... }`)."""
import json
import os
import re

PALABRAS = {'end', 'and', 'or', 'not', 'if', 'then', 'else', 'elseif', 'for', 'in', 'do', 'while', 'function', 'local', 'return', 'nil', 'true', 'false', 'repeat', 'until', 'break', 'goto'}


def a_lua(v, ind=0):
    pad = '  ' * (ind + 1)
    if v is None:
        return 'nil'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        return repr(v) if v != int(v) else str(int(v))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        s = v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return '"' + s + '"'
    if isinstance(v, list):
        if all(not isinstance(x, (dict, list)) for x in v):
            return '{ ' + ', '.join(a_lua(x) for x in v) + ' }'
        return '{\n' + ',\n'.join(pad + a_lua(x, ind + 1) for x in v) + '\n' + '  ' * ind + '}'
    if isinstance(v, dict):
        partes = []
        for k, x in v.items():
            if isinstance(k, str) and re.fullmatch(r'-?\d+', k):
                kk = '[%d]' % int(k)
            elif re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k) and k not in PALABRAS:
                kk = k
            else:
                kk = '[%s]' % a_lua(k)
            partes.append(pad + kk + ' = ' + a_lua(x, ind + 1))
        return '{\n' + ',\n'.join(partes) + '\n' + '  ' * ind + '}'
    raise TypeError(type(v))


def guardar(j, nombre, carpeta):
    """j = mapa de Dos Coronas con las capas en RLE (suelo_rle, bioma_rle, lado_rle, bloque_rle) y el resto de campos. Escribe .json y .lua."""
    nombre = re.sub(r'[^0-9A-Za-z_\-]', '', nombre) or 'mapa'
    rj = os.path.join(carpeta, nombre + '.json')
    with open(rj, 'w', encoding='utf-8') as f:
        f.write(json.dumps(j, ensure_ascii=False))
    cab = [
        '-- GENERADO por el editor de mapas (fao-editor-mapas). Mapa de Dos Coronas "%s", %dx%d.' % (nombre, j['w'], j['h']),
        '-- Capas de casillas en RLE: { valor, repeticiones, valor, repeticiones, ... } sobre la lista plana y*w+x (x de izquierda a derecha, y de arriba a abajo, desde 0).',
        '-- suelo_rle -> suelos[valor + 1], bioma_rle -> biomas[valor + 1], lado_rle -> lados[valor + 1]; bloque_rle: 1 = bloqueada, 0 = libre.',
        '-- Las claves numericas de los diccionarios sueltos (ej. cont, alto) vuelven como numeros.',
    ]
    rl = os.path.join(carpeta, nombre + '.lua')
    with open(rl, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(cab) + '\nreturn ' + a_lua(j) + '\n')
    return dict(ok=True, json=rj, lua=rl, bytes=os.path.getsize(rl))
