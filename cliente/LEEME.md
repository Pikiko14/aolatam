# Cliente propio · Angels Online Forever

Cliente **nuestro** en Lua/[LÖVE](https://love2d.org) 11.5. No usa ni reempaqueta `angel.dat`: habla el mismo protocolo
que el servidor y **lee mapas/sprites/XML de la carpeta del juego** que ya tiene el jugador (sin redistribuir arte de IGG).

Ventajas frente al `angel.dat` parcheado: multiplataforma, sin UPX ni secciones PE, login/UI propios, y se puede
evolucionar sin binarios de IGG.

## Ejecutar

| Sistema | Comando |
|---|---|
| Windows (repo) | `tools\jugar_cliente.cmd` (instala LÖVE con `tools\instalar_love.ps1` si falta) |
| Windows | `lovec.exe cliente` o `love.exe dist\angels-cliente.love` |
| Linux / macOS | `love cliente` / `open -a love dist/angels-cliente.love` |

Paquete: `python -I tools/empaquetar_cliente.py` → `dist/angels-cliente.love`.

La primera vez pide servidor (`host:puerto`, por defecto `127.0.0.1:16768`), usuario, clave y la **carpeta del juego**
(`C:/AO/Angels Online` por defecto). Se guardan servidor, usuario y carpeta (nunca la clave) en `config.txt` del perfil de LÖVE.

## Cuentas y clave

Este cliente cifra la clave con el **mismo Blowfish** que `angel.dat` (`d593b7880791f844`). Entra con las cuentas de la
web / Windows (PBKDF2 en el servidor). La cuenta hay que crearla en la web si `crear_cuenta_al_entrar=0`.

## Teclas

| Tecla | Accion |
|---|---|
| clic izquierdo | caminar; sobre un NPC, hablar; sobre un monstruo, atacar |
| Enter | abrir / enviar el chat |
| I | inventario |
| Alt+E | equipo |
| Q | registro de misiones |
| M | minimapa pequeno / grande |
| P | ventana de la mascota (ficha 0x015E; Stay/Follow/Attack = 0x003E) |
| `/grupo nombre`, `/salir`, `/g texto` | invitar al grupo, dejarlo y chat del grupo (Y / N responden) |
| `/w nombre texto` | susurro |
| F | lista de amigos (`/amigo nombre` invita; Y / N responden; Supr borra) |
| Pausa | silenciar / activar el sonido |
| F1..F12 | lanzar la ranura de la barra rapida |
| iconos del menu inferior | Prop (inventario), Quest Log, Friend y Map |
| doble clic (inventario) | usar o equipar el item |
| arrastrar (inventario) | mover o intercambiar casillas |
| clic en el inventario con la tienda abierta | vender 1 (Mayus: toda la pila) |
| 1..9, 0 (o clic en la barra) | lanzar el hechizo de esa ranura sobre el objetivo (o sobre uno mismo) |
| doble clic (banco abierto) | sacar del banco / guardar desde la mochila |
| `[` `]` | pagina de la tienda |
| Esc | cerrar tienda / chat; sin nada abierto, salir |

## Que falta (respecto al cliente de Windows)

Efectos visuales de las magias, mascotas, amigos y correo, grupos y gremios, minimapa y mapa de escena,
sonido y musica, y el resto de las ventanas. El tinte de color y las posiciones de las casillas de equipo son interpretaciones
deducidas de los datos y faltan por comparar con el original. Detalle en
`docs/PARIDAD_CLIENTE.md`.

Android / iOS: el codigo no depende de Windows, pero el indice de `.pak` usa `io.popen` (`dir` / `ls`) y no existe alli; hace
falta otro modo de listar la carpeta antes de empaquetarlo para movil.

## Pruebas

`love cliente --pruebas` corre 63 comprobaciones de la capa de red contra vectores que genera el servidor Python
(`python -I cliente/tests/generar_vectores.py`). Modos de prueba: `--sonda`, `--mapa`, `--hoja`, `--vestir`, `--cuadros`,
`--ventana` y los ganchos `AO_*` de `main.lua` (login automatico, atacar, hablar, comprar...).

## Login y contrasenas

Manda el AUTH de 73 B como Windows: usuario + bloque Blowfish de 32 B. El servidor descifra y valida contra `pw$...`.
Sin clave solo entra si `validar_password=0`.
