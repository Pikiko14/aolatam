"""Materiales vendibles por cantidad en el puesto.

item.xml e item2.xml marcan como categoria 彈藥 (municion) unos 440 materiales: minas, lingotes, maderas,
crisalidas, ingredientes de cocina... El cliente trata la municion como un paquete unico (el numero que
sale en el nombre, 'Chili Fish Meat(6)', es lo que lleva dentro) y en el puesto solo la vende entera, sin
dejar elegir cuantas unidades. Este script los pasa a 一般 (apilables normales) en copias de esos dos
archivos que va a parches/extras/, y server/parche.py las mete en update27.pak. La municion de verdad
(las que traen estadisticas de ataque) se queda como esta.

Uso:
    python tools/parche_materiales.py [ruta del cliente]
    python tools/generar_parche.py
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import cliente_local
import parche

BS = chr(92)
ARCHIVOS = (BS.join(['SETTING', 'ENG', 'ITEM.XML']), BS.join(['SETTING', 'ENG', 'ITEM2.XML']))
SALIDA = RAIZ / 'parches' / 'extras'


def es_municion_real(fila: str) -> bool:
    return '平均攻擊' in fila or '攻擊變數' in fila or '動態資料1' in fila


def vigente(ruta_cli: pathlib.Path, nombre: str) -> str:
    pak = cliente_local.indice_paks(ruta_cli)[nombre]
    crudo = pak.read_bytes()
    return parche._leer(crudo, parche._directorio(crudo)[nombre]).decode('utf-8')


def main():
    ruta = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r'C:\AO\Angels Online')
    for nombre in ARCHIVOS:
        texto = vigente(ruta, nombre)
        cambiadas = 0

        def cambiar(m):
            nonlocal cambiadas
            fila = m.group(0)
            if '物品類別="彈藥"' not in fila or es_municion_real(fila):
                return fila
            cambiadas += 1
            return fila.replace('物品類別="彈藥"', '物品類別="一般"', 1)

        texto = re.sub(r'<道具\s[^>]*>', cambiar, texto)
        destino = SALIDA / pathlib.Path(*nombre.lower().split(BS))
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(texto.encode('utf-8'))
        print(nombre, 'filas cambiadas:', cambiadas, '->', destino)


if __name__ == '__main__':
    main()
