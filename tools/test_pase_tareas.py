"""Tareas del Angel Pass que se pueden hacer en el servidor (tools/pase_tareas.py, 15/11/2026): diaria la Torre de Babel,
semanal la Raid, y el resto reglas que el servidor ya cuenta."""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import pase
import pase_tareas

# las reglas con contador en el servidor (app._pase_evento y quien lo llama)
CONTADAS = {'打怪類', '抓寵類', '融合道具類', '澆水農作物類', '施肥農作物類', '採收農作物類', '種植農作物類',
            '參與圖騰戰類', '登入遊戲類', '完成通行證任務類', pase_tareas.BABEL, pase_tareas.RAID}


def _grupos():
    t = pase.temporada()
    return {k: pase._grupo(t[k]) for k in ('每日固定任務群組ID', '每日隨機任務群組ID', '每週固定任務群組ID', '每週隨機任務群組ID')}


def test_el_servidor_lee_las_tareas_del_parche():
    assert pase._ultimo('battlepasstask.xml') == pase_tareas.DESTINO_TAREAS


def test_todas_las_tareas_de_la_temporada_se_pueden_hacer():
    for clave, ids in _grupos().items():
        assert ids, clave
        for i in ids:
            assert pase.tareas()[i]['規則'] in CONTADAS, (clave, i, pase.tareas()[i])


def test_babel_diaria_y_raid_semanal():
    g = _grupos()
    diarias = [pase.tareas()[i]['規則'] for i in g['每日固定任務群組ID']]
    semanales = [pase.tareas()[i]['規則'] for i in g['每週固定任務群組ID']]
    assert pase_tareas.BABEL in diarias and pase_tareas.RAID in semanales


def test_los_textos_de_babel_y_raid():
    t = pase_tareas.DESTINO_TEXTOS.read_bytes().decode('utf-8')
    for n, texto in pase_tareas.TEXTOS.items():
        assert re.search(r'編號="%d" 文字="%s"' % (n, re.escape(texto)), t), n


def test_entrar_a_babel_y_a_la_raid_avanza_su_tarea():
    est = pase.Estado(1)
    est.al_dia()
    tocadas, exp = est.contar(pase_tareas.BABEL)
    assert tocadas and exp == 20
    tocadas, exp = est.contar(pase_tareas.RAID)
    assert tocadas and exp == 70


def test_tareas_viejas_se_vuelven_a_sortear():
    est = pase.Estado(1)
    est.al_dia()
    est.listas[2] = [[55, 0]]            # una tarea de las de antes (生產類), ya no esta
    est.listas[4] = [[80, 0]]
    assert est.al_dia() == [1, 2]
    assert all(par[0] in pase.tareas() for lista in (1, 2, 3, 4) for par in est.listas[lista])


def test_las_que_ya_no_estan_se_cambian_y_el_resto_guarda_su_progreso():
    est = pase.Estado(1)
    est.al_dia()
    azar = est.listas[4][0][0]
    est.listas[4][0][1] = 7
    est.listas[3][0][1] = 1
    est.listas[4].append([999, 3])           # una que se quito de la temporada
    assert est.al_dia() == [2]
    assert [azar, 7] in est.listas[4] and est.listas[3][0][1] == 1
    assert all(par[0] in pase.tareas() for par in est.listas[4])
    assert len(est.listas[4]) == int(pase.temporada()['每週隨機任務數量'])


def test_sin_mascotas_ni_fusion():
    for clave, ids in _grupos().items():
        for i in ids:
            assert pase.tareas()[i]['規則'] not in ('抓寵類', '融合道具類'), (clave, i)


def test_al_cumplir_una_tarea_se_repinta_su_periodo():
    est = pase.Estado(1)
    est.al_dia()
    tocadas, _ = est.contar(pase_tareas.BABEL)
    assert pase.periodos_cumplidos(tocadas) == [1]
    assert pase.periodos_cumplidos([(4, 68, 1)]) == []
    assert pase.periodos_cumplidos([(4, 68, 200)]) == [2]
