# Abrir o cerrar una expansión (Atlantis, Forest, Desert...)

Todo sale de **una sola lista**: `MAPAS_APAGADOS` en `server/configuracion.py`. Cada región va en su bloque
(`# Atlantis`, `# Forest`, ...), con sus mapas y sus instancias.

Mientras los mapas de una región están en la lista:

- **Servidor:** nadie entra. Portales, NPC, pergaminos, Superwing y Ring of Angel Wings se rechazan con un aviso
  y sin gastar nada. Quien estaba dentro aparece en el Angel Lyceum al conectar o al revivir.
- **Mapa (M):** su pestaña no se ve (`tools/parche_pestanas_mapa.py`, archivo `wnd01.xml` del cliente).
- **Teletransporte:** sus destinos y su categoría no salen en la lista (`tools/parche_tp_expansiones.py`,
  archivos `jumpmap.xml` y `jumpmapclass.xml` del cliente).

Una región cuenta como cerrada si **todos** los mapas cuya categoría principal es esa región están en la lista. Los
mapas compartidos (por ejemplo 129-131: son de Heart of Eden y salen también en Desert) no la mantienen abierta.

## Abrir una expansión

Ejemplo con Atlantis.

1. **Configuración.** En `server/configuracion.py`, dentro de `MAPAS_APAGADOS`, borra el bloque entero de la
   región:

   ```python
       # Atlantis
       84,  # Blue Sea
       ...
       101,  # Horrible Lost Region
   ```

2. **Regenera los archivos del cliente:**

   ```bash
   python tools/parche_pestanas_mapa.py
   python tools/parche_tp_expansiones.py
   ```

   Cada uno imprime lo que queda: la región tiene que aparecer en «quedan» / «categorías que quedan».

3. **Publica el parche** (los jugadores lo bajan al abrir el launcher):

   ```bash
   python tools/publicar_setting.py wnd01.xml jumpmap.xml jumpmapclass.xml --sin-copiar
   ```

4. **Sube la configuración al servidor**, para que deje entrar a esos mapas:

   ```bash
   python tools/subir_servidor.py
   ```

5. **Commit y push** de `server/configuracion.py`:

   ```bash
   git add server/configuracion.py
   git commit -m "Abre la expansion Atlantis"
   git push origin HEAD
   ```

## Cerrar una expansión

Lo mismo al revés: vuelve a poner su bloque en `MAPAS_APAGADOS` (los números de mapa y sus nombres están en
`setting/eng/jumpmap.xml` y en el historial de git de `configuracion.py`) y repite los pasos 2 a 5.

## Dungeon

Las mazmorras de Eden (Sad Abyss, Fiery Path, Lava Cave, Flaming Door, Underground Square, Hell Palace: mapas
67-72) también están cerradas, con su bloque `# Dungeon` en `MAPAS_APAGADOS`. Se abren igual que una expansión.

## Pestañas que se ocultan siempre

`tools/parche_pestanas_mapa.py` tiene `SIEMPRE_OCULTAS`: pestañas del mapa que no se ven aunque su región esté
abierta. Ahora está vacía; para ocultar una, pon su nombre en minúsculas (por ejemplo `{'dungeon'}`) y repite los
pasos 2 y 3.

## Comprobar

- En el juego, con el launcher actualizado: abre el mapa (M) y la ventana de teletransporte.
- En el servidor: `python tools/listar_mapas.py` dice qué mapas están apagados.
