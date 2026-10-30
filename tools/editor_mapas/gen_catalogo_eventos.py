"""Regenera static/eventos_catalogo.js (nombres de acciones/condiciones y cuales entiende el servidor).

    python tools/editor_mapas/gen_catalogo_eventos.py
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import eventos as e

d = e._datos()
js = '// Generado desde server/plantillas/eventos.json y server/eventos.py (python tools/editor_mapas/gen_catalogo_eventos.py). No editar a mano.\n'
js += 'const EV_ACC_EN = %s;\n' % json.dumps({int(k): v for k, v in d['acciones'].items()}, ensure_ascii=False)
js += 'const EV_COND_EN = %s;\n' % json.dumps({int(k): v for k, v in d['condiciones'].items()}, ensure_ascii=False)
js += 'const EV_ACC_SERV = %s;\n' % json.dumps(sorted(e.SE_TRADUCEN))
js += 'const EV_COND_SERV = %s;\n' % json.dumps(sorted(e.SE_EVALUAN))
(pathlib.Path(__file__).parent / 'static' / 'eventos_catalogo.js').write_text(js, encoding='utf-8')
print('escrito static/eventos_catalogo.js')
