# Editor de mapas del servidor (FAO .mpc + NPC y monstruos de AO)

Vive en `tools/editor_mapas/` del repo. Lee los **assets del cliente** (carpeta con `data1.pak`, `update*.pak` y `map\`): por defecto
`C:\AO\Angels Online`, o la variable `AO_CLIENTE`, o el primer argumento. Arranque: `tools\editor_mapas\abrir_editor.bat`
(o `py -3 tools/editor_mapas/editor_mapas.py "<carpeta del cliente>" 8770`; necesita Pillow y numpy).

## NPC y monstruos de AO (pestana "NPC/Monstruos AO", tecla N)
- El catalogo sale del cliente (`setting/eng/monster.xml` y `npc.xml`), con la miniatura de cada sprite.
- Al abrir `mapNNN` se leen los spawns de `server/plantillas/<mapa>.json` (el numero del .mpc es el stage del servidor).
- Clic en el mapa = colocar el elegido (solo en casillas libres); clic sobre uno = seleccionar y arrastrar; Supr = borrar; direccion 0..7.
- **Exportar .mpc** tambien escribe los spawns en la plantilla del servidor (o el boton "Exportar al servidor ahora" de la pestana).
  Las entidades que ya estaban conservan todos sus campos; solo cambian su casilla y direccion. Las nuevas reciben `entity_id` libre
  (de 900001 en adelante) y los monstruos llevan `nivel`. Antes de escribir deja `<mapa>.json.bak`.
- La `y` del servidor cuenta desde abajo del mapa (`tile y = alto - 1 - celda y`); el editor ya lo convierte.
- Hay que **reiniciar el servidor** para ver los cambios. Si el stage no tenia plantilla, se crea una y hay que registrarla en
  `login.PLANTILLAS_POR_STAGE`. Un NPC nuevo no trae dialogo: abrir su menu depende de lo que el servidor tenga para ese `npc_type`.

---

## Eventos en español (pestaña "Eventos")
- Constructor visual de la logica del mapa: un **evento** es "cuando pase X (disparador), si se cumple Y (condiciones), haz Z (acciones)". Todo en español, con la etiqueta de cada parametro.
- **+ Evento nuevo desde plantilla**: salida a otro mapa, dar objeto o oro al hacer clic, cobrar y dar, abrir tienda, contador de bajas de una mision, evento vacio.
- Cada condicion tiene "al reves" (反向) y cada disparador "basta con una" (旗標); se conserva el ALIAS/DEFINE del XML. Lo marcado con ⚠ **no lo ejecuta el servidor todavia** (se guarda igual).
- **Enlazar un objeto con un evento**: pestaña Seleccion, un solo objeto, campo **evento** (van en los 4 primeros bytes del registro extra del objeto; 0 = ninguno). Los NPC del servidor (0x0008) no llevan evento: su dialogo sale de `server/dialogos.py` por `npc_type`.
- "XML avanzado" abre el XML tal cual. Los nombres salen de `static/eventos_catalogo.js` (`python tools/editor_mapas/gen_catalogo_eventos.py` lo regenera desde `server/eventos.py`).
- Despues de exportar, `python tools/propagar_eventos.py` pasa los eventos de los mapas al servidor (`plantillas/eventos.json`).
- Una **mision nueva** necesita ademas su fila en `quest.xml` (el cliente la muestra desde ahi) y sus textos en `msg.xml`: eso todavia no lo genera el editor.

---


# Editor de mapas (FAO .mpc y Dos Coronas)

Abre `abrir_editor.bat` (o `py -3 editor_mapas.py`; necesita Python 3, Pillow y numpy). Indexa los .pak del cliente (la carpeta de arriba, `C:\AO\Angels Online`) y abre el navegador en http://127.0.0.1:8770/ .
Dos editores con el mismo servidor:

| Editor | Direccion | Para que sirve | Lo usa Dos Coronas |
|---|---|---|---|
| **Mapas de FAO (.mpc)** | `/` | Abrir, crear y editar mapas .mpc de Free Angels Online (terreno, colision, objetos, zonas, salidas, rutas, eventos) | Si, hoy: `mapa_mpc.lua` + `hornear_mpc.py` (boton **Enviar a Dos Coronas**) |
| **Mapas de Dos Coronas** | `/dc` | Editar los mapas que genera el codigo del juego (continentes, batalla, estandarte, casas): suelo, bioma, bando, bloqueo, props, campamentos, edificios, portal | Necesita un cargador en el juego (ver `PROMPT_DOS_CORONAS.md`) |

## Editor de mapas de FAO (.mpc)
- **Abrir**: los .mpc sueltos de la carpeta `map\` del cliente, los 558 de dentro de los .pak, tus proyectos (`proyectos\*.json`) y lo exportado (`salida\`). Los mapas con nombre de escena (map002 = Riprap Coast) lo muestran. **Nuevo**: mapa vacio con el terreno base que elijas (formato v5, el que lee Dos Coronas).
- **Terreno (B)**: pinta tilesets de pincel (`brush/brush.bNN`, texturas continuas de 512×512 que se repiten cada 16 casillas), circulo o cuadrado, tamano 1-40, Shift = linea recta. **Rectangulo (R)** y **relleno (G)**; **cuentagotas (I / Alt+clic)**.
- **Colision (T)**: pinta el atributo de casilla (0 libre, 1 obstaculo, 2 agua/risco, 3 borde, 10 zona del mar, o cualquier numero). Botones: *marcar obstaculo bajo los objetos que bloquean*, *agua profunda → 2*, *bordes → 3*. Capa **Transitable (reglas de Dos Coronas)**: verde = zona principal, amarillo = isla aislada, rojo = bloqueado.
- **Objetos (O)**: busqueda entre las definiciones de `setting/*.obd` (con miniatura), colocar uno o **esparcir** (bosques), ajuste a 16 px o a la base de la celda. Con sprite real; NPC y marcas del servidor salen como rombos de color. **Seleccionar (V)**: caja, mover, flechas (Shift ×8, Ctrl ×32), Supr, Ctrl+C/V/A, F espeja, inspector con id, x, y, a, espejo, c. Borrador (E).
- **Zonas (Z)** y **Rutas (X)**: polígonos y rutas (salidas 1-2, puntos 31-44, zonas 71-83, rutas de patrulla). Arrastra vertices, Shift+clic los quita, lista con ir-a y borrar.
- **Eventos / Dialogos**: editor del XML con validacion y resumen. **Capas**, **Mapa** (informacion, cambiar tamano moviendo el contenido, nombre al exportar, estadisticas) y **Validar** (objetos fuera del mapa, ids sin definicion, tilesets que faltan, salidas alcanzables, zonas aisladas).
- Deshacer/rehacer (Ctrl+Z / Ctrl+Y), autoguardado cada 90 s en `proyectos\_auto_*.json`, minimapa, zoom con la rueda, arrastrar con boton central o Espacio.
- **Guardar proyecto** = `.json` (reabrible con todo). **Exportar .mpc** = `salida\NOMBRE.mpc`: se relee para comprobarlo. **Enviar a Dos Coronas** = exporta y ejecuta `hornear_mpc.py` del proyecto (copia el .mpc a `compartido/datos/mapas_fao/`, genera `mapNNN_datos.lua` y los atlas); despues anade `nombre = NNN` a `M.MAPAS` en `compartido/dominio/mapas_fao.lua`.
- **Pack nuevo (`update28.pak`)**: **Guardar proyecto** y **Exportar .mpc** tambien mandan el mapa, con todas las modificaciones, a `update28.pak` en la carpeta del cliente (como `MAP\NOMBRE.MPC`). El cliente carga `update.pak`..`update31.pak` en orden y gana el de numero mas alto, asi que el juego usa tu mapa sin tocar ningun .pak original; borrar `update28.pak` lo deshace todo. Los mapas ya guardados en el pack se conservan y el que guardas de nuevo reemplaza al suyo. El autoguardado (cada 90 s) solo guarda el proyecto, no toca el pack. El pack se relee tras escribirlo para comprobar que el mapa quedo igual; si el cliente o el servidor lo tienen abierto, el editor avisa y el proyecto/.mpc se guardan igual: cierra y vuelve a guardar. El pack no se indexa en el editor (lo reescribe el propio editor).
  - Para los jugadores: el servidor mete `update28.pak` en su parche al arrancar (`server/parche.py`), quitando antes los NPC duplicados del mapa (`tools/mpc_sin_npc.py`). Despues sube el parche al VPS como siempre.
  - La colision que usa el servidor no se actualiza sola: `py -3 tools/instalar_mapa.py <mapa.mpc> --stage N` (en el proyecto del servidor) actualiza `transitable.bin`.
- **Criaturas (C)**: pestana *Criaturas* con las 88 criaturas de `monstruos.xml` (buscador, nivel, jefes). Clic = campamento nuevo con la plantilla (criatura, cantidad, radio), clic sobre uno = seleccionar y arrastrar, Supr = borrar; se validan (casilla transitable, zona aislada). Como el .mpc no trae criaturas se guardan en `salida\NOMBRE_campamentos.json/.lua` (y en el proyecto); **Enviar a Dos Coronas** copia `mapNNN_campamentos.lua` junto al .mpc. Para que el juego las haga aparecer hace falta `PROMPT_CRIATURAS_FAO.md`.

Garantias comprobadas: los **21 .mpc** de `Descargas\map\` se leen y se escriben **byte a byte identicos**; un mapa editado se relee y pasa por `hornear_mpc.py` sin errores. Maneja las dos versiones del formato (v5 y v6: en v6 hay una capa extra de 1 byte por celda y los tilesets son u16; se conservan tal cual).

## Editor de mapas de Dos Coronas (`/dc`)
- **Abrir**: *Volcar mapas del juego* ejecuta `lovec dcdump` (carpeta `dcdump\`) y deja `dc_mapas\*.json` con los mapas **tal como los genera hoy el codigo** (mundo 1152×832, batalla, estandarte, casas). Lo editado va a `dc_editados\`.
- **Capas**: suelo (20 tipos), bioma, bando (albor/umbra) y bloqueo, con pincel, rectangulo, relleno y cuentagotas.
- **Props** (P): 38 tipos del juego, colocar o esparcir. **Campamentos** (C): criatura, cantidad, radio, jefe. **Seleccionar** (V): props, campamentos, edificios (con su puerta) y ciudades; inspector de campos; **Portal**.
- Se conservan sin tocar los demas datos del mapa (jefes, puestos, puertos, NPC, escaleras, mesetas, caminos, lagos, continentes, mazmorras…), editables como JSON en la pestana **Mapa**.
- **Guardar / exportar**: `dc_editados\NOMBRE.json` (reabrible) y `NOMBRE.lua` (`return { … }` con las capas en RLE; se carga en 0,14 s). **Esto no cambia el juego por si solo**: hace falta el cargador (ver `PROMPT_DOS_CORONAS.md`).

## Limites conocidos
- FAO: el significado de los campos `a`, `espejo` y `c` de cada objeto y de las rutas/eventos sigue sin descifrar; se conservan y se editan como numeros. Los objetos se dibujan con su primer cuadro. Los mapas v6 los lee el cargador actual de Dos Coronas (`mapa_mpc.lua`) solo en parte: esta hecho para v5 (la lista de tilesets cambia de formato); conviene probarlo.
- Dos Coronas: las ciudades se muestran y se editan por campos, pero no se pueden mover con el raton (llevan muchas estructuras generadas). Hasta que el juego cargue estos archivos, los cambios no se ven en la partida.
- Todo el arte de FAO es de un juego ajeno: prototipo.

Atajos: H mano, B pincel, T colision (FAO), R rectangulo, G relleno, I cuentagotas, O objeto (FAO), P prop / C campamento (Dos Coronas), V seleccionar, Z zonas / X rutas (FAO), E borrar, [ ] tamano, Ctrl+S guardar, Espacio = mover vista.
