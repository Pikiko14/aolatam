"""Lag al spamear skills (17/11/2026): el GC recorria ~900.000 objetos precargados en cada recoleccion completa y
competiciones releia su JSON en cada tick del cron."""
import gc
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import competiciones  # noqa: E402


def test_congelar_el_heap_saca_lo_cargado_del_gc():
    basura = [{'x': i} for i in range(1000)]
    try:
        app._congelar_heap('test')
        assert gc.get_freeze_count() >= len(basura)
    finally:
        gc.unfreeze()


def test_la_config_de_eventos_no_se_relee_si_no_cambia(monkeypatch):
    lecturas = []
    leer = pathlib.Path.read_text

    def contar(self, *a, **k):
        if self.name == 'competiciones_config.json':
            lecturas.append(1)
        return leer(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, 'read_text', contar)
    competiciones._CONFIG_EVENTOS[:] = [None, None]
    a = competiciones.config_eventos()
    b = competiciones.config_eventos()
    assert a == b and len(lecturas) == 1
    a['modo_pruebas'] = 'tocado'                          # quien la modifique no ensucia la cache
    assert competiciones.config_eventos().get('modo_pruebas') != 'tocado'
