"""Que mapa es cada stage: numero, nombre ingles y si el servidor lo sirve.

El nombre sale de setting/eng/stage.xml del cliente. Las columnas:

    poblado    tiene plantilla en el servidor (app.mapas_poblados())
    instancia  stage.xml lo marca como dinamico (plantillas/instancias.json)
    apagado    esta en configuracion.MAPAS_APAGADOS
    portales   tornados que llevan A ese stage en plantillas/portales.json

Uso:
    py -3 tools/listar_mapas.py                 # todos
    py -3 tools/listar_mapas.py lyceum          # busca en el nombre
    py -3 tools/listar_mapas.py 97 110          # por numero de stage
    py -3 tools/listar_mapas.py --poblados      # solo los que sirve el servidor
"""
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
PLANTILLAS = RAIZ / 'server' / 'plantillas'


def nombres():
    import paks_cliente
    paks_cliente.asegurar_extraidos()
    f = paks_cliente.DESTINO / 'setting' / 'eng' / 'stage.xml'
    return {int(e.get('編號')): e.get('名稱') or ''
            for e in ET.parse(f).getroot() if (e.get('編號') or '').isdigit()}


def main(args):
    import app
    poblados = app.mapas_poblados()
    inst = json.loads((PLANTILLAS / 'instancias.json').read_text(encoding='utf-8'))
    instancias = {int(k) for k, v in (inst.get('mapas') or {}).items() if v.get('dinamica')}
    entradas = {}
    for lista in (app._portales().get('mapas') or {}).values():
        for por in lista:
            if por.get('destino') is not None:
                entradas[int(por['destino'])] = entradas.get(int(por['destino']), 0) + 1

    solo_poblados = '--poblados' in args
    filtros = [a for a in args if a != '--poblados']
    numeros = {int(a) for a in filtros if a.isdigit()}
    textos = [a.lower() for a in filtros if not a.isdigit()]

    import configuracion
    print(f"{'stage':>5}  {'nombre':<36} {'plantilla':<32} {'inst':<4} {'apagado':<7} portales")
    for stage, nombre in sorted(nombres().items()):
        if solo_poblados and stage not in poblados:
            continue
        if numeros and stage not in numeros and not textos:
            continue
        if textos and not any(t in nombre.lower() for t in textos) and stage not in numeros:
            continue
        print(f"{stage:>5}  {nombre[:36]:<36} {poblados.get(stage, '-'):<32} "
              f"{'si' if stage in instancias else '':<4} "
              f"{'si' if configuracion.mapa_apagado(stage) else '':<7} {entradas.get(stage, 0)}")


if __name__ == '__main__':
    main(sys.argv[1:])
