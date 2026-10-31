# Launcher propio de Angels Online

Reemplaza al `START.EXE` de IGG. Es un `.exe` de ~30 KB escrito en C# (WinForms, .NET Framework 4.8, que viene con
Windows 10/11): no necesita instalar nada, ni para compilarlo ni para usarlo.

## Qué hace

1. Pide `GET /launcher.json` al servidor de parches (el mismo puerto 2121 del VPS, que también habla HTTP): la versión
   del parche, su tamaño y su sha256, las noticias (`data/noticias.json`) y su propia versión.
2. Si hay un launcher nuevo, se baja, se reemplaza y se reinicia solo.
3. Retira (a `respaldo_launcher\`) los `update28..update31.pak` que dejó el `START.EXE`: llevaban versiones viejas del
   parche y, con un número más alto, pisaban al nuevo. Solo los toca si **todo** lo que llevan es del parche.
4. Si el `update27.pak` del jugador no es el del servidor, lo baja **entero** a un temporal, comprueba tamaño y
   sha256, y solo entonces cambia el viejo. Si la descarga se corta o llega dañada, el cliente queda como estaba.
5. Escribe la versión en `reg.ini` (con saltos de línea LF) y lanza `angel.dat` en la carpeta del juego.

Todas las versiones van siempre a `update27.pak`: **se acabó el límite de update28..update31**.

## Compilar

```
python tools/compilar_launcher.py --ip <IP-del-VPS>
python tools/compilar_launcher.py --ip 127.0.0.1 --probar     # y lo prueba de punta a punta, sin tocar tu cliente
```

Sale `parches/launcher_propio/AngelsLauncher.exe` (no va a git). La IP no se guarda en el repositorio: se pasa al
compilar (o con la variable `AO_PARCHE_HOST`). Opcionales: `--puerto`, `--titulo`, `--subtitulo`.

Al cambiar el launcher, sube `VERSION_LAUNCHER` en `tools/compilar_launcher.py`. Los jugadores se actualizan solos en
cuanto el exe nuevo esté en el VPS (`tools/subir_mapa.py` lo sube si existe).

## Repartirlo

Al jugador se le da `AngelsLauncher.exe` para que lo copie en la carpeta del juego (la que tiene `angel.dat`) y lo use
en vez de `START.EXE`. Un `launcher.ini` opcional al lado cambia a dónde mira:

```
Servidor = 77.42.52.122
Puerto = 2121
```

## Archivos

| Archivo | Qué es |
|---|---|
| `Programa.cs` | arranque y modo `--prueba` (sin ventana) |
| `Actualizador.cs` | manifiesto, descarga verificada, auto-actualización, limpieza de paks, `reg.ini`, lanzar el juego |
| `Pak.cs` | lector del directorio de un `.pak` (para saber qué lleva cada update28..31) |
| `Ventana.cs` | la ventana, dibujada a mano: fondo animado, noticias, progreso y botones |
| `icono.ico` | el icono |
| `server/cliente_local.py` | `_manifiesto_launcher`: el `/launcher.json` que sirve el servidor |
