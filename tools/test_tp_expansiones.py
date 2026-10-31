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
    jm, jc, quitados, clases = ptp.generar()
    assert quitados > 0 and not _stages(jm) & set(mapas_apagados_configurados)
    assert 41 in _stages(jm) and 3 in _stages(jm)                  # Angel Lyceum y Holy City siguen
    assert 'Atlantis' in clases and 'Desert' in clases and 'Heart Of Eden' not in clases
    assert '類別2="6"' not in re.search(r'<跳地圖 [^>]*場景編號="129"[^>]*>', jm).group(0)


def test_los_numeros_de_los_que_quedan_no_cambian(mapas_apagados_configurados):
    jm, *_ = ptp.generar()
    assert re.search(r'<跳地圖 編號="1" 場景編號="41"', jm) and re.search(r'<跳地圖 編號="60" 場景編號="129"', jm)


def test_con_todo_abierto_no_se_quita_nada():
    jm, jc, quitados, clases = ptp.generar(apagados=set())
    assert quitados == 0 and clases == []
