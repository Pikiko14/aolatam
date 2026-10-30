"""Logros en el momento, sin tener que volver a entrar.

Los de estado (oro, stats, nivel...) no tienen evento propio: los revisa el
bucle de cada sesion (app._logros_tick). Y el de cada baja se mira despues de
la EXP de esa misma baja, no antes.
"""
import asyncio
import pathlib
import sys
import types

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import login


def sesion(oro=0, nivel=1):
    p = login.Personaje(nivel=nivel, oro=oro)
    ses = types.SimpleNamespace(usuario=None, personaje=p, inventario={}, oro=oro, paquetes=[])
    ses.enviar = lambda *pk: ses.paquetes.extend(pk)
    return ses


def avisos(ses):
    return b''.join(ses.paquetes)


def test_el_oro_da_su_logro_sin_reconectar():
    ses = sesion(oro=600000)
    ses._logros_en_vivo = True
    assert app._logros_tick(ses, ahora=1000.0)
    assert b'Money- 500,000' in avisos(ses)


def test_no_revisa_antes_de_entrar_ni_cargando_mapa():
    ses = sesion(oro=600000)
    assert not app._logros_tick(ses, ahora=1000.0)
    ses._logros_en_vivo, ses.mapa_cargando = True, True
    assert not app._logros_tick(ses, ahora=1000.0)
    assert not ses.paquetes


def test_respeta_el_intervalo():
    ses = sesion()
    ses._logros_en_vivo = True
    assert app._logros_tick(ses, ahora=1000.0)
    assert not app._logros_tick(ses, ahora=1000.0 + app.INTERVALO_LOGROS - 0.1)
    assert app._logros_tick(ses, ahora=1000.0 + app.INTERVALO_LOGROS)


def test_la_baja_se_revisa_despues_de_su_exp(monkeypatch):
    ses = sesion(nivel=10)
    vistos = []
    monkeypatch.setattr(app, '_pase_evento', lambda *a, **k: None)
    monkeypatch.setattr(app, '_aliua_baja', lambda *a, **k: None)
    monkeypatch.setattr(app, '_logros_actualizar',
                        lambda s, addr=None, enviar=False, silencioso=False: vistos.append(s.personaje.nivel))

    async def baja():
        app._logros_muerte(ses, 'test', 0)
        ses.personaje.nivel = 11          # la subida de nivel de esta baja
        await asyncio.sleep(0)

    asyncio.run(baja())
    assert vistos == [11]


def test_logros_activos_en_false_apaga_todo_sin_perder_los_contadores(monkeypatch):
    """configuracion.LOGROS_ACTIVOS = False: ni evalua ni otorga logros nuevos (ni el aviso,
    ni el Super BC del primer titulo, ni el 0x0155), pero _logros_contar sigue sumando el
    contador para no perder progreso mientras esta apagado."""
    import configuracion
    monkeypatch.setattr(configuracion, 'LOGROS_ACTIVOS', False)
    ses = sesion(oro=600000)
    ses._logros_en_vivo = True
    assert app._logros_tick(ses, ahora=1000.0)   # el tick corre igual...
    assert not ses.paquetes                      # ...pero no se otorga ni se avisa nada

    ses2 = sesion()
    monkeypatch.setattr(app, '_pase_de_logros', lambda *a, **k: None)
    app._logros_contar(ses2, 'prueba:1', 1)
    assert ses2.personaje.logros_cont['prueba:1'] == 1
    assert not ses2.paquetes

    monkeypatch.setattr(configuracion, 'LOGROS_ACTIVOS', True)
    ses.paquetes.clear()
    assert app._logros_tick(ses, ahora=1000.0 + app.INTERVALO_LOGROS)
    assert b'Money- 500,000' in avisos(ses)       # vuelve a funcionar normal
