"""Hardiness (耐久) del equipo: se gasta peleando y se repara en los NPC de reparacion.

Hasta el 16/11/2026 era solo un numero ("no funciona el hardiness"): el servidor mandaba siempre el maximo de item.xml.
Ahora, como el oficial (eleccion del usuario):

  * el arma pierde 1 cada GOLPES_ARMA golpes que da el jugador, y una pieza de armadura al azar 1 cada GOLPES_ARMADURA
    golpes que recibe;
  * a 0 la pieza esta rota: no da stats (inventario.bonos_de_equipo) hasta repararla;
  * se repara en la ventana WND_REPAIR (0x004F, la abren Repair Angel / Repair Expert / Repair Robot y el Spacious Iron
    Room). Sacado del cliente (angel.dat):
      - repair.lua: OnRepairOne -> game.repairone (00589e20 -> 0061e330): c2s 0x003B [8 bytes de instancia de la fila]
                    OnRepairAll -> game.repairall (00589e50 -> 0061e430): c2s 0x003C sin cuerpo
      - la lista (00660xxx) pone las piezas con Hardiness actual (+0x2c) < maximo (+0x5c), y el precio lo calcula el
        propio cliente en 00660eb0: (maximo - actual) / maximo * 價格 * 0.05, truncado. Se cobra lo mismo.

El Hardiness gastado vive en personaje.mejoras[ranura]['dur'] (viaja con la pieza al moverla y se guarda con las
mejoras); sin 'dur' esta entero.
"""
import logging
import random

import inventario as inv

log = logging.getLogger('durabilidad')

GOLPES_ARMA = 10
GOLPES_ARMADURA = 10
COSTE_REPARAR = 0.05                    # 0x8c2520 del cliente

RANURAS_ARMA = (inv.RANURA_DERECHA, inv.RANURA_IZQUIERDA)


def _mejoras(ses):
    p = getattr(ses, 'personaje', None)
    if p is None:
        return {}
    if not isinstance(getattr(p, 'mejoras', None), dict):
        p.mejoras = {}
    return p.mejoras


def _estado(ses, r):
    m = _mejoras(ses)
    return m.get(r) or m.get(str(r))


def actual(ses, r) -> int:
    item = int((ses.inventario or {}).get(r) or 0)
    return inv.durabilidad_actual(item, _estado(ses, r)) if item else 0


def _poner(ses, r, valor):
    item = int(ses.inventario.get(r) or 0)
    tope = inv.durabilidad(item)
    m = _mejoras(ses)
    est = m.get(r)
    if est is None and str(r) in m:
        est = m[str(r)]
    if valor >= tope:
        if est is not None:
            est.pop('dur', None)
            if not est:
                m.pop(r, None)
                m.pop(str(r), None)
        return
    if est is None:
        est = m[r] = {}
    est['dur'] = max(0, int(valor))


def _gastables(ses, ranuras):
    bolsa = getattr(ses, 'inventario', None) or {}
    return [r for r in ranuras if bolsa.get(r) and inv.durabilidad(int(bolsa[r])) > 0 and actual(ses, r) > 0]


def _armaduras(ses):
    bolsa = getattr(ses, 'inventario', None) or {}
    return [r for r in bolsa if isinstance(r, int) and r < inv.PRIMERA_RANURA_BOLSA and r not in RANURAS_ARMA
            and r != inv.RANURA_ORO and not inv.es_mascota(int(bolsa[r] or 0))]


def _gastar(ses, ranuras, refrescar, guardar):
    tocadas = []
    for r in ranuras:
        antes = actual(ses, r)
        _poner(ses, r, antes - 1)
        tocadas.append(r)
        if antes - 1 == 0:
            log.info('%s: %s (%s) se rompio', getattr(ses.personaje, 'nombre', '?'), ses.inventario.get(r), r)
    if tocadas:
        refrescar(ses, tocadas, rota=any(actual(ses, r) == 0 for r in tocadas))
        guardar(ses)
    return tocadas


def golpe_dado(ses, refrescar, guardar):
    """Un golpe del jugador: cada GOLPES_ARMA, -1 a las armas que lleva."""
    ses.dur_golpes_dados = getattr(ses, 'dur_golpes_dados', 0) + 1
    if ses.dur_golpes_dados < GOLPES_ARMA:
        return []
    ses.dur_golpes_dados = 0
    return _gastar(ses, _gastables(ses, RANURAS_ARMA), refrescar, guardar)


def golpe_recibido(ses, refrescar, guardar):
    """Un golpe al jugador: cada GOLPES_ARMADURA, -1 a una pieza de armadura al azar."""
    ses.dur_golpes_recibidos = getattr(ses, 'dur_golpes_recibidos', 0) + 1
    if ses.dur_golpes_recibidos < GOLPES_ARMADURA:
        return []
    ses.dur_golpes_recibidos = 0
    piezas = _gastables(ses, _armaduras(ses))
    if not piezas:
        return []
    return _gastar(ses, [random.choice(piezas)], refrescar, guardar)


def coste(ses, r) -> int:
    item = int((ses.inventario or {}).get(r) or 0)
    tope = inv.durabilidad(item) if item else 0
    if not tope:
        return 0
    falta = tope - actual(ses, r)
    if falta <= 0:
        return 0
    precio = inv._col_item(item, 'price')                 # 價格 de item.xml
    return max(1, int(falta / tope * precio * COSTE_REPARAR))      # el cliente pone 1 como minimo (00660a29)


def reparables(ses):
    bolsa = getattr(ses, 'inventario', None) or {}
    return [r for r in sorted(k for k in bolsa if isinstance(k, int))
            if bolsa.get(r) and not inv.es_mascota(int(bolsa[r])) and inv.durabilidad(int(bolsa[r])) > actual(ses, r)]


def reparar(ses, ranuras):
    """Repara esas ranuras si llega el oro. Devuelve (ranuras reparadas, oro gastado, faltaba_oro)."""
    total = sum(coste(ses, r) for r in ranuras)
    if total <= 0:
        return [], 0, False
    if int(getattr(ses, 'oro', 0) or 0) < total:
        return [], 0, True
    ses.oro = int(ses.oro) - total
    for r in ranuras:
        _poner(ses, r, inv.durabilidad(int(ses.inventario[r])))
    return list(ranuras), total, False
