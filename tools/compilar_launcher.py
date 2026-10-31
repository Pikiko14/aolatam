"""Compila el launcher propio (launcher/*.cs) con el csc de .NET Framework 4.8 que trae Windows: no hay que instalar nada.

    python tools/compilar_launcher.py --ip <IP-del-VPS>            # -> parches/launcher_propio/AngelsLauncher.exe
    python tools/compilar_launcher.py --ip 127.0.0.1 --probar      # compila y lo prueba de punta a punta (sin tocar tu cliente)

Sin --ip se usa AO_PARCHE_HOST (la IP del servidor no se guarda en el repositorio). El exe va en parches/launcher_propio/:
el servidor lo anuncia en /launcher.json y lo sirve, asi que los jugadores que ya lo tienen se actualizan solos al subirlo
al VPS (parches/launcher_propio/AngelsLauncher.exe). A un jugador nuevo se le da ese mismo exe para su carpeta del juego.

--probar: levanta un servidor HTTP de mentira con un launcher.json y un update27.pak, monta una carpeta de juego con un
angel.dat falso, un update28.pak que solo lleva archivos del parche (el launcher debe retirarlo) y un update29.pak con un
archivo ajeno (debe dejarlo), y corre el exe con --prueba: tiene que bajar el pak, verificarlo y escribir la version.
"""
import argparse
import hashlib
import http.server
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FUENTES = RAIZ / 'launcher'
SALIDA = RAIZ / 'parches' / 'launcher_propio'
EXE = 'AngelsLauncher.exe'
FRAMEWORK = pathlib.Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET' / 'Framework64' / 'v4.0.30319'
# Sube este numero al cambiar el launcher: los jugadores lo reciben solos (por el sha256, no por el numero).
VERSION_LAUNCHER = '1.0.0'


def _cadena(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def compilar(ip, puerto, titulo, subtitulo, destino=SALIDA):
    csc = FRAMEWORK / 'csc.exe'
    if not csc.exists():
        raise SystemExit('No esta %s (hace falta .NET Framework 4.x, que viene con Windows 10/11).' % csc)
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        config = pathlib.Path(tmp) / 'Config.cs'
        config.write_text(
            '// Generado por tools/compilar_launcher.py. No editar.\n'
            'namespace AngelsLauncher {\n static class Config {\n'
            '  public const string Servidor = %s;\n  public const int Puerto = %d;\n'
            '  public const string Titulo = %s;\n  public const string Subtitulo = %s;\n'
            '  public const string VersionLauncher = %s;\n  public const string ArchivoLauncher = %s;\n }\n}\n'
            % (_cadena(ip), int(puerto), _cadena(titulo), _cadena(subtitulo), _cadena(VERSION_LAUNCHER), _cadena(EXE)),
            encoding='utf-8')
        args = [str(csc), '/nologo', '/target:winexe', '/optimize+', '/platform:anycpu',
                '/out:' + str(destino / EXE),
                '/r:System.dll', '/r:System.Drawing.dll', '/r:System.Windows.Forms.dll',
                '/r:' + str(FRAMEWORK / 'System.Web.Extensions.dll')]
        icono = FUENTES / 'icono.ico'
        if icono.exists():
            args.append('/win32icon:' + str(icono))
        args += [str(f) for f in sorted(FUENTES.glob('*.cs'))] + [str(config)]
        r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode:
            print(r.stdout, r.stderr)
            raise SystemExit('csc fallo (codigo %d)' % r.returncode)
    exe = destino / EXE
    print('compilado %s (%d KB) -> servidor %s:%d' % (exe.relative_to(RAIZ), exe.stat().st_size // 1024, ip, puerto))
    return exe


def probar(exe):
    sys.path.insert(0, str(RAIZ / 'server'))
    import parche
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        web, juego = tmp / 'web', tmp / 'juego'
        web.mkdir()
        juego.mkdir()
        nuestros = {'MAP\\MAP900.MPC': b'mapa nuevo', 'SETTING\\ENG\\ITEM9.XML': b'<root/>'}
        pak = parche.armar_pak(nuestros)
        (web / 'update27.pak').write_bytes(pak)
        (web / 'launcher.json').write_text(json.dumps({
            'version': '8.5.1.99', 'pak': 'update27.pak', 'bytes': len(pak), 'sha256': hashlib.sha256(pak).hexdigest(),
            'archivos': sorted(nuestros) + ['SHAPE\\LOGO\\ZZ_FIN.TXT'],
            'noticias': [{'fecha': '2026-10-31', 'titulo': 'Prueba', 'texto': 'Hola'}]}), encoding='utf-8')
        (juego / 'angel.dat').write_bytes(b'MZ falso')
        (juego / 'update27.pak').write_bytes(parche.armar_pak({'MAP\\MAP900.MPC': b'mapa viejo'}))
        (juego / 'update28.pak').write_bytes(parche.armar_pak({'MAP\\MAP900.MPC': b'otro viejo'}))
        (juego / 'update29.pak').write_bytes(parche.armar_pak({'MAP\\MAP001.MPC': b'ajeno'}))
        (juego / 'reg.ini').write_bytes(b'[PROFILE]\r\nGameName = Angels Online\r\nVersion = 8.5.1.0\r\n')
        shutil.copy(exe, juego / EXE)

        class Manejador(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(web), **k)

            def log_message(self, *a):
                pass

        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Manejador)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        (juego / 'launcher.ini').write_text('Servidor = 127.0.0.1\nPuerto = %d\n' % srv.server_address[1])
        try:
            r = subprocess.run([str(juego / EXE), '--prueba'], capture_output=True, text=True, timeout=120)
        finally:
            srv.shutdown()
        print(r.stdout.strip())
        fallos = []
        if r.returncode != 0:
            fallos.append('salio con %d' % r.returncode)
        if (juego / 'update27.pak').read_bytes() != pak:
            fallos.append('update27.pak no es el del servidor')
        if (juego / 'update28.pak').exists():
            fallos.append('no retiro update28.pak (solo llevaba archivos del parche)')
        if not (juego / 'update29.pak').exists():
            fallos.append('retiro update29.pak, que llevaba un archivo ajeno')
        reg = (juego / 'reg.ini').read_bytes()
        if b'Version = 8.5.1.99' not in reg or b'\r' in reg:
            fallos.append('reg.ini sin la version nueva o con CRLF: %r' % reg)
        print('PRUEBA ' + ('OK' if not fallos else 'FALLO: ' + '; '.join(fallos)))
        return not fallos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ip', default=os.environ.get('AO_PARCHE_HOST'))
    ap.add_argument('--puerto', type=int, default=2121)
    ap.add_argument('--titulo', default='Angels Online')
    ap.add_argument('--subtitulo', default='Latam')
    ap.add_argument('--probar', action='store_true')
    a = ap.parse_args()
    if not a.ip:
        raise SystemExit('Falta --ip (o la variable AO_PARCHE_HOST): a que servidor mira el launcher.')
    exe = compilar(a.ip, a.puerto, a.titulo, a.subtitulo)
    if a.probar and not probar(exe):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
