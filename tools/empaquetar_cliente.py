"""Empaqueta el cliente multiplataforma (cliente/) en dist/angels-cliente.love.

    python -I tools/empaquetar_cliente.py

Un .love es un zip con main.lua en la raiz; se abre con LÖVE 11.4 (love angels-cliente.love) en Windows, Linux y macOS.
No lleva ningun recurso de IGG: el cliente los lee de la carpeta del juego del jugador. Las pruebas (tests/) no se incluyen.
"""
import pathlib
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / 'cliente'
DESTINO = RAIZ / 'dist' / 'angels-cliente.love'
EXCLUIR = ('tests/', '.tmp')


def main():
    DESTINO.parent.mkdir(exist_ok=True)
    n = 0
    with zipfile.ZipFile(DESTINO, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(ORIGEN.rglob('*')):
            rel = f.relative_to(ORIGEN).as_posix()
            if f.is_dir() or any(rel.startswith(e) or rel.endswith(e) for e in EXCLUIR):
                continue
            z.write(f, rel)
            n += 1
    print('escrito', DESTINO, '-', n, 'archivos,', DESTINO.stat().st_size, 'B')


if __name__ == '__main__':
    main()
