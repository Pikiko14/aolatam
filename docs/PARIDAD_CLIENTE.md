# Cliente propio multiplataforma: lo que tiene que igualar al de Windows

Requisito: lo que se ve y se hace en el cliente nuevo (Linux, Mac, Windows...) debe ser **lo mismo que en el cliente de Windows de Angels Online**:
mismas funciones, mismos personajes, mismas pantallas. El servidor no cambia (es autoritativo); todo el trabajo esta en el cliente.

Este documento fija el alcance con cifras medidas y como se comprobara la paridad. Las cifras salen de `corpus/content.db`, de los paks del cliente
(`C:\AO\Angels Online`) y de `server/app.py`; las estimaciones de esfuerzo NO estan medidas.

## 1. Que hay que igualar (inventario medido)

### Protocolo
| | cantidad |
|---|---|
| Opcodes cliente->servidor que atiende `app.py` | 96 |
| Opcodes servidor->cliente que arma el servidor | ~104 |
| Manejadores del binario original (servidor->cliente) | 203 (`docs/tabla_s2c.md`) |

El cliente nuevo debe entender y mandar al menos lo que usa nuestro servidor (~100 + 96). El resto del original son funciones que el servidor aun no usa.

### Datos del juego (tablas de `content.db`)
item (30 000, mas item2..item9: ~170 000 filas en total), monster 19 205, magic 18 497, petattrib 11 500, drop_table 6 744, doll 6 273, npc 3 357,
quest 1 489, level 471, stage 445, shop 226, simpleai 130. El cliente nuevo las lee de los mismos XML de `setting/` del cliente instalado.

### Graficos (archivos en los paks: 133 546 en total, 5,07 GB)
| carpeta `shape/` | sprites | que es |
|---|---|---|
| chr | 75 442 | personajes y equipo (la mitad del arte) |
| magic | 22 858 | efectos de habilidades |
| stage | 13 862 | escenarios y objetos de mapa |
| mon | 6 923 | monstruos |
| item | 4 256 | iconos de objetos |
| wnd01 / wndstar | 1 410 / 133 | ventanas y adornos |
| skill / card / npc / face / pet | 1 362 / 496 / 493 / 264 / 235 | habilidades, cartas, NPC, caras, mascotas |
| smap | 650 | minimapa |
| effect, emot, bubble, cursor, font... | ~900 | efectos, emotes, burbujas de chat, cursores, tipografias |

Mapas: 558 `.mpc`. Interfaz: 567 XML en `setting/` (ventanas `wnd*.xml`, `wnddef.xml`, `theme.xml`, tres resoluciones). Sonido: 413 ogg y 576 wav, mas voces y musica.

### Pantallas y sistemas (los que usa el servidor hoy; cada uno es una casilla de la lista de paridad)
Login y seleccion de personaje, creacion, mapa y movimiento, chat (canales, susurro, burbujas), combate y barras de vida, habilidades y barra rapida,
inventario y equipo, tiendas y cambio de objetos, dialogos de NPC y misiones, grupo, gremio, mascotas, monturas, casas y muebles, cartas, mejoras de equipo,
Event Overview y bonos, Holy Arena, Totem War, minimapa y mapa del mundo, correo/social. Se completa con `tools/` y los `docs/*_2026-10-*.md`.

## 2. Como se comprobara que es lo mismo
El cliente de Windows es el **oraculo**. Tres pruebas, de mas barata a mas cara:

1. **Reproduccion de sesiones grabadas.** `server/grabador.py` y `tools/replay.py` guardan y reinyectan el trafico real. Se alimenta al cliente nuevo
   con la misma sesion que vio el original y se compara lo que dibuja en instantes marcados (diferencia de imagen contra capturas del original).
2. **Lista de paridad por pantalla.** Cada sistema de la seccion 1 se marca como: abre, muestra lo mismo, responde igual, textos y sonidos iguales.
3. **Comparacion lado a lado en vivo** con ambos clientes conectados al mismo servidor y al mismo personaje.

Criterio de aceptacion: la lista completa en verde y la reproduccion de sesiones sin diferencias de contenido (se aceptan diferencias de pixeles por
el motor grafico, no de lo que aparece).

## 3. Lo que falta descifrar antes de poder prometer la paridad
- **Contrasena:** como el cliente original deriva el hash que manda en el login. **NO esta resuelto** (`docs/07_LOGIN_REAL.md`, "Deuda conocida"; `tools/analizar_auth.py` no lo resolvio). El cliente Lua manda su propia huella: solo entra en cuentas creadas con el.
- **Animacion:** resuelta en lo basico (reposo, correr, atacar, morir; 5 direcciones + espejo); faltan sentarse, trabajar, montura y duales.
- **Personaje con equipo:** resuelto en lo basico (cuerpo base 999/1100, pelo 1001+/1101+, piezas por `doll`); el orden de capas y el tinte son deducidos y faltan por comparar.
- **Efectos de habilidades:** `shape/magic`, `effect` y su sincronizacion con los golpes.
- **Interfaz:** reglas de maquetacion de `wnd*.xml` por resolucion y tema.
- **Sonido:** que sonido va con cada accion.

## 4. Hitos (con criterio de salida)
| hito | resultado | se da por bueno cuando |
|---|---|---|
| 0 | Cliente actual bajo Wine/Proton en Linux y Mac | entra al juego y se ve y juega como en Windows |
| 1 | Visor de solo lectura | conecta, entra al mapa, dibuja terreno, objetos y personajes y se mueve |
| 2 | Juego basico | chat, combate, inventario, dialogos de NPC y misiones, comparado con el original |
| 3 | Interfaz completa | todas las ventanas de la seccion 1 |
| 4 | Paridad | lista completa en verde y sesiones grabadas sin diferencias |

Si el hito 0 funciona, cubre Linux y Mac sin escribir cliente. El cliente propio se justificaria por moviles, navegador o independencia de Wine.

## 5. Legal (no es asesoria)
El arte y el sonido son de IGG. El cliente nuevo debe leer los archivos del cliente que cada jugador ya tiene instalado y no redistribuirlos.

## 6. Estado real del cliente Lua (`cliente/`, 28/10/2026)

Verificado en vivo contra un servidor de desarrollo aislado. "Probado" = se ejecuto y el servidor confirmo el efecto.

| area | estado | notas |
|---|---|---|
| Red, cifrado, Hello | hecho | 63 pruebas contra vectores del servidor Python |
| Login, clave propia, seleccion de personaje | hecho | clave: ver seccion 3; crear personajes probado (C2S 0x0003, 57 B) con vista previa |
| Mapa: terreno, objetos, orden por y | hecho (objetos 95 % dibujables en Aurora; el resto son luces y marcas invisibles) | v5 y v6 (celda de 7 B en v6; el byte 0 es el tileset directo). Bordes suaves entre suelos (degradado propio de 16 px, no las mascaras `brush.pNN` del original). Sombras bajo las entidades (elipse fija) y objetos animados (8 de 216 tipos en el Lyceum). Faltan agua animada y las costuras cada 16 casillas |
| NPC y monstruos: sprites, animacion, direccion | hecho | NPC sin archivo en los pak (p. ej. 40044) salen como punto |
| Personaje: cuerpo, pelo, equipo, tinte | parcial | tinte y orden de capas sin comparar con el original |
| Caminar, chat de canal y local | hecho | el chat local lo anota el cliente (el servidor no lo devuelve) |
| Combate: objetivo, ataque, danio, muerte, botin | probado | falta barra de objetivo con captura, magias y barra de habilidades |
| Inventario: ver, usar, equipar, mover, tooltip | probado | usar/equipar = C2S 0x002E; mover = 0x0012; el 0x001B se aplica |
| Equipo (Alt+E) | parcial | posicion de casillas medida a mano; solo lectura |
| Dialogo de NPC con retrato y opciones | probado | texto de `msg.xml`; falta la ventana de tienda de otros tipos (stall, mall) |
| Tienda: comprar y vender | probado | comprar = 0x0027, vender = 0x0028 con la instancia de 8 B; el precio mostrado sale de item.xml y el servidor cobra con su tabla |
| Misiones (Q) | parcial | contadores de paso en 0 |
| HUD con los marcos originales (158 personaje, 182 barra F1-F12, 269 minimapa, 116 menu, 134 chat) | probado | nombre, nivel, HP, MP, exp, F1-F12, chat translucido y menu clicable (Prop, Quest, Friend, Map). Faltan retrato, lista de skills del panel, pestanas del chat y SP |
| HUD (detalle anterior): |  | minimapa con la imagen de `shape/smap`; faltan buffs y el mapa de escena |
| Sonido y musica | parcial | musica por escena (`stage.xml` -> `music/NN.ogg`) y efectos: golpe (`hit`), subida de nivel, magia (`magicNNN` por 特效編號) y fallo; F5 silencia. Faltan sonidos de pasos, NPC, ambiente (`g*.ogg`, `b*.ogg`) y su tabla por evento |
| Barra de habilidades y lanzar magias | probado | 0x005B (24 ranuras) y C2S 0x0006 [magia u16][objetivo u32]; iconos de `skillicon.xml`; el MP baja; el enfriamiento mostrado es local |
| Efectos visuales de magias y golpes | probado | S2C 0x0011 fase 0 trae el id (特效編號 = Sequence de un objeto SP_CLASS_EFFECT en m01/m02/m03.obd); se reproducen los cuadros una vez sobre el objetivo (aditivo si SP_ATTRIB_WHITELIGHT). Visto el efecto 181 (aura de fuego). Faltan trayectorias de proyectiles y efectos de estado persistentes |
| Amigos: lista, invitar y aceptar (F) | probado | 0x0027, 0x0028, 0x0029, 0x002A, 0x002E y C2S 0x0019, 0x001B, 0x001C, 0x001E con dos clientes; en el login el servidor manda un 0x002E justo tras el estado en linea y el cliente muestra al amigo apagado (comportamiento del servidor, sin revisar) |
| Grupo: invitar, aceptar, lista con vida y mana, chat de grupo, salir | probado | 0x0017, 0x0018, 0x0023, 0x0024, 0x0025, 0x0026 y chat 0x0126; probado con dos clientes (faltan expulsar, ascender y deshacer desde la interfaz) |
| Chat privado (/w) | probado | C2S 0x0127 y S2C 0x0127; el emisor ve "[To nombre]" |
| Banco: ventana 2100, 25 casillas, sacar y guardar con doble clic | probado | S2C 0x004E (tipo*1000+n) y 0x001B con contenedor 2; C2S 0x002F [contenedor 16 sacar / 17 guardar][casilla][4 B]; probado con el Bank Clerk de Aurora (faltan los 6 cofres alquilables y el banco de gremio) |
| Mascotas: aparecen en el mundo (0x0050) y ventana con sus datos (0x0065, tecla P) | parcial | probado invocando un Water Elf Egg; su sprite 3037 no tiene definicion en los obd del cliente y sale como punto con nombre. Faltan ordenes (activo/ayuda/seguro), habilidades, renombrar y alimentar |
| Correo, gremios, banco, casas, mall, ligas | falta | |
| Android / iOS | falta | el indice de pak usa `io.popen` |

Lo que sigue, por utilidad: efectos de magias, banco, grupo y amigos, sonido.
