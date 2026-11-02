""""los tp a los mapa de las expansiones podriamos ocultarlos y que se activen en base a ese arreglo??"."""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import parche_tp_expansiones as ptp


def _stages(jm):
    return {int(s) for s in re.findall(r'場景編號="(\d+)"', jm)}


def test_no_quedan_destinos_de_mapas_apagados(mapas_apagados_configurados):
    jm, jc, quitados, clases, original = ptp.generar()
    assert quitados > 0 and not _stages(jm) & set(mapas_apagados_configurados)
    assert 41 in _stages(jm) and 3 in _stages(jm)                  # Angel Lyceum y Holy City siguen
    assert 'Atlantis' in clases and 'Desert' in clases and 'Heart Of Eden' not in clases


def test_los_del_sunshine_palace_tambien_salen(mapas_apagados_configurados):
    """Hermit Wetland, Flower Corridor y Sunshine Palace (129-131): "estos tres mapas fuera tambien" (02/11/2026)."""
    jm, *_ = ptp.generar()
    assert not _stages(jm) & {129, 130, 131}


def test_se_renumera_sin_huecos_y_se_guarda_el_numero_original(mapas_apagados_configurados):
    jm, jc, quitados, clases, original = ptp.generar()
    numeros = [int(n) for n in re.findall(r'<跳地圖 編號="(\d+)"', jm)]
    assert numeros == list(range(1, len(numeros) + 1))
    assert sorted(original) == numeros
    assert re.search(r'<跳地圖 編號="1" 場景編號="41"', jm) and original[1] == 1


def test_con_todo_abierto_no_se_quita_nada():
    jm, jc, quitados, clases, original = ptp.generar(apagados=set())
    assert quitados == 0 and clases == []
    assert all(nuevo == viejo for nuevo, viejo in original.items())
