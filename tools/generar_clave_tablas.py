"""Regenera cliente/src/clave_tablas.lua desde server/clave_cliente.py (Blowfish del AUTH)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import clave_cliente as c

P, S = c._horario()
out = pathlib.Path(__file__).resolve().parent.parent / 'cliente' / 'src' / 'clave_tablas.lua'
lineas = [
    '-- Tablas Blowfish con la clave del cliente (generadas por tools/generar_clave_tablas.py).',
    'local M = {}',
    'M.P = {%s}' % ','.join(str(x) for x in P),
]
for i, s in enumerate(S):
    lineas.append('M.S%d = {%s}' % (i, ','.join(str(x) for x in s)))
lineas.append('return M')
out.write_text('\n'.join(lineas) + '\n', encoding='utf-8')
print('escrito', out)
