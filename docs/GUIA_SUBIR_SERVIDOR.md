# Subir cambios al servidor (VPS)

El servidor corre en `root@77.42.52.122:/opt/angels` como el servicio `angels.service`. La API de cuentas de la
web (`angels-web-registro.service`) va enganchada a él y se reinicia sola con él.

## Qué script usar

| Cambiaste... | Comando |
|---|---|
| Código o plantillas del servidor (`server/*.py`, `server/plantillas/*.json`, `configuracion.py`) | `python tools/subir_servidor.py` |
| Premios u otros XML del cliente (`logingift.xml`, `onlinegift.xml`, `activityurl.xml`...) | `python tools/publicar_setting.py onlinegift.xml` (ver `GUIA_PUBLICAR_SETTING.md`) |
| Un mapa del editor | `python tools/subir_mapa.py <numero>` |
| La web (`tools/web_sitio/`) | `python tools/publicar_web.py` (`--solo-web` para no reiniciar el juego) |

## Pasos para el servidor

1. **Prueba en local** y corre los tests de lo que tocaste (solo esos, no toda la suite).
2. **Commit y push**, para que lo que esté en el VPS sea lo mismo que hay en git:

   ```bash
   git add server/app.py
   git commit -m "Lo que cambiaste"
   git push origin HEAD
   ```

3. **Mira qué difiere** del VPS (no sube nada):

   ```bash
   python tools/subir_servidor.py --ver
   ```

   Compara por hash todos los archivos de `server/` que están en git con los del VPS y lista los distintos.
   Si aparece algo que no esperabas, revísalo antes de subir: puede ser un cambio que alguien hizo
   directamente en el VPS.

4. **Sube y reinicia**:

   ```bash
   python tools/subir_servidor.py
   ```

   Muestra la lista, avisa si alguno tiene cambios sin commit y pregunta antes de subir. Después sube solo los
   distintos, reinicia `angels.service`, espera a que arranque y vuelve a comparar los hashes. Tiene que acabar
   en `active active` y `hashes iguales: N de N`.

   Para subir solo algunos archivos: `python tools/subir_servidor.py server/app.py server/combate.py`.

## Ten en cuenta

- **Reiniciar desconecta a todos los jugadores** unos segundos. Mejor hacerlo cuando haya poca gente.
- `configuracion.py` también se sube así. Si cambiaste algo directamente en el VPS, `--ver` lo mostrará
  como distinto: pásalo primero a tu copia local, o lo perderás al subir.
- Los datos de los jugadores (`data/cuentas.db`) **nunca** se suben ni se tocan: viven solo en el VPS.

## Si algo sale mal

- **No acaba en `active`**: mira el error con
  `ssh root@77.42.52.122 "journalctl -u angels.service -n 50 --no-pager"`. Corrige en local y vuelve a subir.
- **Volver atrás**: `git revert` del commit (o deja el archivo como estaba) y vuelve a correr el script.
- **"NO coinciden"**: la subida quedó a medias; vuelve a correr el mismo comando.
