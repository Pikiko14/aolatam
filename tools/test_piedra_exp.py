"""Exp Stone / Exp Diamond: se coloca en la mascota, guarda un % de cada
combate hasta su tope y el boton de la ventana se lo pasa al dueño."""
import pathlib
import struct
import sys
import types

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import cuentas
import inventario as inv
import mascotas as ms

PIEDRA8 = 4455      # 8 Carat Exp Stone: 800000, 35%


def ficha():
    return {'nombre': 'Pet', 'sprite': 1, 'nivel': 10, 'exp': 0, 'fuera': True, 'ranura': 30}


def test_la_piedra_se_coloca_no_da_exp():
    assert inv.uso_en_mascota(PIEDRA8) == {'diamante': {'tope': 800000, 'pct': 35}}
    assert inv.uso_en_mascota(5707) == {'diamante': {'tope': 100000, 'pct': 60}}


def test_guarda_el_porcentaje_hasta_el_tope():
    f = ficha()
    assert ms.poner_diamante(f, PIEDRA8, 1000, 35)
    assert not ms.poner_diamante(f, PIEDRA8, 1000, 35)
    assert ms.cargar_diamante(f, 2000) == 700
    assert ms.cargar_diamante(f, 2000) == 300
    assert ms.cargar_diamante(f, 2000) == 0
    assert f['diamante']['exp'] == 1000


def test_el_cliente_ve_la_piedra():
    f = ficha()
    ms.poner_diamante(f, PIEDRA8, 800000, 35)
    ms.cargar_diamante(f, 1000)
    pk = ms.armar(f)
    assert struct.unpack_from('<IIH', pk, 2 + 180) == (350, 800000, 35)
    e = ms.entrada(bytes(ms.TAM_ENTRADA), f)
    assert struct.unpack_from('<II', e, 140) == (350, 800000)
    assert struct.unpack_from('<H', e, 220) == (35,)


def test_sin_piedra_no_se_escribe_nada():
    pk = ms.armar(ficha())
    assert pk[2 + 180:2 + 190] == bytes(10)


def test_el_boton_pasa_la_exp_al_dueno_aunque_no_este_llena(monkeypatch):
    dadas = []
    monkeypatch.setattr(app, '_dar_exp_y_creditos', lambda ses, exp=0, creditos=0: dadas.append(exp))
    monkeypatch.setattr(app, '_refrescar', lambda ses, ranuras: [])
    monkeypatch.setattr(cuentas, 'guardar_mascota', lambda *a: None)
    f = ficha()
    ms.poner_diamante(f, PIEDRA8, 800000, 35)
    ms.cargar_diamante(f, 1000)
    ses = types.SimpleNamespace(usuario='u', paquetes=[],
                                personaje=types.SimpleNamespace(char_id=1, mascota=f, mascotas={}))
    ses.enviar = lambda *pk: ses.paquetes.extend(pk)
    app._sacar_exp_del_diamante(ses, 'test')
    assert dadas == [350] and 'diamante' not in f
    app._sacar_exp_del_diamante(ses, 'test')
    assert dadas == [350]
