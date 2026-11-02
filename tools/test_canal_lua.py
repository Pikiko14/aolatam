"""El canal servidor -> Lua: el 0x01A0 (server/canal_lua.py) y el parche de angel.dat (tools/parche_canal_lua.py)."""
import pathlib
import struct
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import canal_lua
import parche_canal_lua

ANGEL = pathlib.Path('C:/AO/aoforever/angel_descomprimido.dat')


def test_el_paquete_es_opcode_texto_y_cero():
    pk = canal_lua.paquete('CreateDailyHelpWnd()')
    assert pk == struct.pack('<H', 0x01A0) + b'CreateDailyHelpWnd()\0'


def test_llamar_escapa_los_argumentos_como_literales_lua():
    pk = canal_lua.llamar('SubastaFila', 3, 'Espada "+4"\n', None, True, [1, 2], {'a': 1})
    assert pk[2:-1] == b'SubastaFila(3,"Espada \\"+4\\"\\n",nil,true,{1,2},{["a"]=1})'


def test_un_nombre_de_funcion_raro_no_se_manda():
    with pytest.raises(ValueError):
        canal_lua.llamar('os.exit(); x')


def test_solo_el_comando_lua():
    assert canal_lua.es_comando_gm('/lua CreateDailyHelpWnd()')
    assert canal_lua.codigo_del_comando(' /LUA  x = 1 ') == 'x = 1'
    assert not canal_lua.es_comando_gm('/luae') and not canal_lua.es_comando_gm('lua x')


def test_arroba_manda_un_archivo_de_server_lua():
    assert 'function SubastaAbrir' in canal_lua.codigo_del_comando('/lua @subasta')
    with pytest.raises(ValueError):
        canal_lua.codigo_del_comando('/lua @../app')


@pytest.mark.skipif(not ANGEL.exists(), reason='sin angel_descomprimido.dat en esta maquina')
def test_el_parche_registra_el_manejador_y_engancha_la_tabla():
    d = ANGEL.read_bytes()
    assert not parche_canal_lua.lleva_el_canal(d)
    nuevo = parche_canal_lua.parchear(d)
    assert parche_canal_lua.lleva_el_canal(nuevo)
    pe, tabla, secs = parche_canal_lua._secciones(nuevo)
    sec = secs[-1]
    base = parche_canal_lua._base(nuevo)
    cod = nuevo[sec['rptr']:sec['rptr'] + sec['vsz']]
    # El gancho salta a la seccion nueva y el resto del exe no cambia.
    o = parche_canal_lua._off(nuevo, parche_canal_lua.GANCHO_EN)
    destino = parche_canal_lua.GANCHO_EN + 5 + struct.unpack_from('<i', nuevo, o + 1)[0]
    assert nuevo[o] == 0xE9 and base + sec['va'] <= destino < base + sec['va'] + sec['vsz']
    cab = 0x400                                   # la cabecera si cambia: una seccion mas y SizeOfImage
    assert nuevo[cab:o] == d[cab:o] and nuevo[o + 6:len(d)] == d[o + 6:]
    # El gancho escribe el manejador (el principio de la seccion) en el hueco del 0x01A0.
    hueco = struct.pack('<II', 0x7B0 + 0x01A0 * 16, base + sec['va'])
    assert b'\xc7\x81' + hueco in cod
    assert cod.endswith(b'=servidor\0')
    with pytest.raises(SystemExit):
        parche_canal_lua.parchear(nuevo)          # dos veces no
