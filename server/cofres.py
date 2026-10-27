"""Cofres del banco que se alquilan con una Safe Key (Coffer 1..6).

Sacado del cliente (bank.lua y Angel.exe):
  - sendrentbank(indice, tipo) manda C2S 0x002F [u8 0x17][u32 indice][u32 tipo],
    con el indice del cofre desde 0 y el tipo RENTBANK_1_DAY=0, 7_DAY=1,
    30_DAY=2, FOREVER=3.
  - Las casillas del banco van por el control de la ventana menos 2100: las
    1..25 son el banco de siempre y el cofre n (1..6) son las 26+15*(n-1) ..
    40+15*(n-1).
  - isbankrent / canusebankbag (0x58FF10) dan el cofre por alquilado si en la
    casilla 115+n del banco hay un objeto: ahi se deja la llave gastada, y
    getbankbagmsg ensena su caducidad (el +47 de la entrada, ver
    inventario.marcar_caducidad_holy) o "[Use for ever]".

Al caducar se puede seguir sacando lo que haya, pero no guardar (lo dice la
descripcion de la llave).
"""
import struct
import time

CASILLAS_BANCO = 25
CASILLAS_COFRE = 15
COFRES = 6
SUBTIPO_ALQUILER = 0x17

# tipo de alquiler -> {llave: dias}; 0 dias = para siempre
LLAVES = {
    0: {1999: 1, 8452: 1, 79744: 1},
    1: {2000: 7, 19243: 7},
    2: {2001: 30, 79743: 30, 4485: 90, 4486: 180},
    3: {2734: 0, 79742: 0},
}


def casilla_llave(cofre: int) -> int:
    return 115 + int(cofre)


def casillas_de(cofre: int) -> range:
    inicio = CASILLAS_BANCO + 1 + CASILLAS_COFRE * (int(cofre) - 1)
    return range(inicio, inicio + CASILLAS_COFRE)


def es_casilla_llave(casilla: int) -> bool:
    return casilla_llave(1) <= int(casilla) <= casilla_llave(COFRES)


def cofre_de_casilla(casilla: int):
    c = int(casilla)
    if CASILLAS_BANCO < c <= CASILLAS_BANCO + CASILLAS_COFRE * COFRES:
        return (c - CASILLAS_BANCO - 1) // CASILLAS_COFRE + 1
    return None


def _clave(cofre):
    return -10000 - casilla_llave(cofre)


def fin_de(p, cofre):
    """None si no esta alquilado; 0 si es para siempre; si no, el instante en que caduca."""
    if casilla_llave(cofre) not in (getattr(p, 'banco', None) or {}):
        return None
    m = (getattr(p, 'mejoras', None) or {}).get(_clave(cofre)) or {}
    return float(m.get('cofre_fin') or 0)


def vigente(p, cofre, ahora=None) -> bool:
    fin = fin_de(p, cofre)
    return fin is not None and (fin == 0 or fin > (ahora or time.time()))


def se_puede_guardar(p, casilla: int, ahora=None) -> bool:
    if 1 <= int(casilla) <= CASILLAS_BANCO:
        return True
    cofre = cofre_de_casilla(casilla)
    return cofre is not None and vigente(p, cofre, ahora)


def guardables(p, ahora=None) -> list:
    """Las casillas del banco donde se puede guardar ahora, en orden."""
    out = list(range(1, CASILLAS_BANCO + 1))
    for cofre in range(1, COFRES + 1):
        if vigente(p, cofre, ahora):
            out.extend(casillas_de(cofre))
    return out


def alquilar(ses, cuerpo, ahora=None):
    """El boton Rent de la ventana del cofre."""
    import app
    import clases
    import cuentas
    import inventario
    ahora = ahora or time.time()
    p = ses.personaje
    indice, tipo = struct.unpack_from('<II', cuerpo, 1)
    cofre = indice + 1

    def aviso(texto):
        ses.enviar(clases.aviso(texto, tipo=0))

    if not 1 <= cofre <= COFRES or tipo not in LLAVES:
        aviso('This coffer cannot be rented.')
        return
    tope = app._tope_bolsa(ses.inventario)
    casilla = next((s for s, it in sorted(ses.inventario.items())
                    if int(it) in LLAVES[tipo] and 20 <= s <= tope), None)
    if casilla is None:
        aviso("You need a Safe's Key in your backpack to rent this coffer.")
        return
    llave = int(ses.inventario[casilla])
    dias = LLAVES[tipo][llave]
    previo = fin_de(p, cofre)
    if previo == 0:
        aviso('This coffer is already rented forever.')
        return
    if dias == 0:
        fin = 0
    else:
        fin = max(ahora, previo or 0) + dias * 86400
    app._sacar(ses, casilla, 1)
    if p.banco is None:
        p.banco = {}
    if getattr(p, 'mejoras', None) is None:
        p.mejoras = {}
    p.banco[casilla_llave(cofre)] = (llave, 1)
    p.mejoras[_clave(cofre)] = {'cofre_fin': fin, 'cofre_item': llave}
    ses.enviar(*app._refrescar(ses, [casilla]),
               inventario.banco_poner(p.char_id, casilla_llave(cofre), llave, 1,
                                      dueno=p.entity_id, mejoras=p.mejoras))
    if getattr(ses, 'usuario', None):
        cuentas.guardar_banco(ses.usuario, p.char_id, p.banco)
        app._guardar_bolsa(ses, p.char_id)
    if fin == 0:
        aviso('Coffer %d rented forever.' % cofre)
    else:
        aviso('Coffer %d rented until %s.' % (cofre, time.strftime('%Y-%m-%d %H:%M', time.localtime(fin))))
    app.log.info('[%s] cofre %d alquilado con %s (%s dias) hasta %s',
                  getattr(ses, 'addr', '?'), cofre, llave, dias, fin or 'siempre')
