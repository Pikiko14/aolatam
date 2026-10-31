# Cambiar premios (login, online...) y que les llegue a los jugadores

Sirve para cualquier XML de `setting/eng` que edites a mano: `logingift.xml` (premios por días de login),
`onlinegift.xml` (premios por minutos conectado), etc.

## 1. Editar

Abre el archivo en `extracted_paks/update26/setting/eng/` (ese es el que lee el servidor):

```xml
<在線獎勵 編號="1" 在線分鐘="0" 道具1="89058" 數量1="1"/>
```

- `編號`: número de fila (1 a 10).
- `在線分鐘` (online) o `登入天數` (login): minutos conectado o días de login para el premio.
- Hasta tres premios por fila: `道具1`/`數量1`, `道具2`/`數量2`, `道具3`/`數量3` (item y cantidad).
- **No repitas un atributo en la misma fila** (dos `道具2`): el XML queda roto y el cliente puede fallar.

## 2. Publicar (un solo comando)

Desde la carpeta del repo:

```bash
python tools/publicar_setting.py onlinegift.xml
```

Varios a la vez: `python tools/publicar_setting.py logingift.xml onlinegift.xml`.

El script hace todo, en orden, y se para si algo falla:

1. Comprueba que el XML esté bien formado (te dice la línea si no).
2. Lo copia a `parches/extras/setting/eng/`, de donde sale el parche de los jugadores.
3. Rehace `parches/update27.pak` (sube la versión, p. ej. 8.5.1.21 → 8.5.1.22) y los paquetes del launcher.
4. Commit + push de la copia en `parches/extras/` (así queda en git).
5. Sube al VPS el XML, el parche y los paquetes, reinicia el servidor, compara los hashes y
   comprueba que el launcher anuncie la versión nueva.

Opciones: `--sin-vps` (prepara todo pero no sube) y `--sin-git` (sin commit).

## 3. Cómo les llega a los jugadores

- **Servidor**: entrega los premios nuevos en cuanto se reinicia (paso 5).
- **Cliente**: la ventana de premios la dibuja el cliente con su copia del XML. Al abrir el launcher, ve la
  versión nueva y baja `update27.pak` solo; después pulsan **JUGAR** y ya ven los premios nuevos.
- Quien siga con el `START.EXE` de IGG ya no recibe parches (llegó a `update31`): necesita el launcher
  propio (`AngelsLauncher.exe`, en la web).

## Si algo sale mal

- **"esta roto: ... line N"**: el XML tiene un error en esa línea (comillas, `/>` o atributo repetido).
- **"NO coinciden"**: la subida al VPS quedó a medias; vuelve a correr el mismo comando.
- **El launcher no ofrece actualizar**: mira la versión en `http://77.42.52.122:2121/launcher.json`, que
  debe ser la que imprimió el script.
