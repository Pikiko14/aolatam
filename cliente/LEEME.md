# Cliente multiplataforma de Angels Online (prototipo)

Cliente escrito en Lua para [LÖVE](https://love2d.org) 11.4. Habla el mismo protocolo que el cliente de Windows y **lee los
recursos (mapas, sprites, ventanas, textos) de la carpeta del juego que ya tiene el jugador**: no incluye ni redistribuye
nada de IGG.

## Ejecutar

| Sistema | Comando |
|---|---|
| Windows | `love.exe angels-cliente.love` (o arrastra el `.love` sobre `love.exe`) |
| Linux | `love angels-cliente.love` |
| macOS | `open -a love angels-cliente.love` |

Desde el repositorio: `love cliente` (o `lovec.exe cliente` en Windows para ver la consola).
Para generar el paquete: `python -I tools/empaquetar_cliente.py` -> `dist/angels-cliente.love`.

La primera vez pide servidor (`host:puerto` del login, por defecto 16768), usuario, clave y la **carpeta del juego** (la que
tiene `data1.pak`, `update*.pak`...). Se guardan servidor, usuario y carpeta (nunca la clave) en `config.txt` del perfil de LÖVE.

## Cuentas y clave

El cifrado de la clave del cliente original no esta resuelto (`docs/07_LOGIN_REAL.md`, "Deuda conocida"). Este cliente manda
su propia huella (sha256 de usuario + clave), asi que:

- una cuenta **nueva** se crea en el primer ingreso (el servidor se queda con esa huella);
- una cuenta creada con el cliente de Windows **no** entra con clave desde este cliente, salvo que el servidor tenga
  `validar_password = 0` (`python tools/config_login.py validar_password 0`).

## Teclas

| Tecla | Accion |
|---|---|
| clic izquierdo | caminar; sobre un NPC, hablar; sobre un monstruo, atacar |
| Enter | abrir / enviar el chat |
| I | inventario |
| Alt+E | equipo |
| Q | registro de misiones |
| M | minimapa pequeno / grande |
| P | ventana de la mascota (cuando hay una invocada) |
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

El servidor guarda una huella salada del bloque de 32 B que manda el cliente (`cuentas.hash_de_auth`); la primera entrada de una cuenta la registra y las siguientes deben mandar el mismo bloque. Este cliente manda `sha256('angels-lua:' + usuario + ':' + clave)`, asi que:

- Funciona con la validacion de contrasena ENCENDIDA: una cuenta nueva se registra al primer ingreso; clave distinta -> "Clave incorrecta".
- Una cuenta creada con el cliente de Windows NO entra con este cliente (y al reves) hasta resolver el cifrado de clave del original.
