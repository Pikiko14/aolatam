"""El fondo y el icono del launcher.

12/11/2026, "rehagamos el launcher con esta imagen y este logo": la imagen del cielo con islas flotantes
(launcher/arte/cielo.webp) recortada a la proporcion de la ventana (980x580, al doble: el exe la escala) y el emblema
redondo (launcher/emblema.png, sin el fondo de cuadros que traia pintado) arriba a la izquierda, sobre el arbol. Los
personajes de la imagen quedan a la izquierda y las noticias, las versiones y JUGAR en una columna a la derecha
(launcher/Ventana.cs). El icono (launcher/icono.ico) es el emblema en todos los tamanos; tools/icono_angel_dat_en_sitio.py lo
pone tambien en angel.dat, el juego, para que se vea en la barra de tareas.

    python tools/fondo_launcher.py launcher/arte/cielo.webp launcher/emblema.png launcher/fondo.jpg launcher/icono.ico
    python tools/compilar_launcher.py --ip <IP-del-VPS> --probar
"""
import sys

from PIL import Image, ImageFilter

cielo_src, emblema_src, dst_fondo, dst_ico = sys.argv[1:5]
W, H, S = 1960, 1160, 2                     # el doble de la ventana (980x580)
EMBLEMA = (30, 22, 150)                     # en la ventana: x, y y lado

cielo = Image.open(cielo_src).convert('RGBA')
ancho = round(cielo.height * W / H)         # la imagen es algo mas ancha: se corta por la derecha (el castillo oscuro)
fondo = cielo.crop((0, 0, min(ancho, cielo.width), cielo.height)).resize((W, H), Image.LANCZOS)

emblema = Image.open(emblema_src).convert('RGBA')
lado = EMBLEMA[2] * S
emblema = emblema.resize((lado, round(emblema.height * lado / emblema.width)), Image.LANCZOS)
sombra = Image.new('RGBA', emblema.size, (0, 0, 0, 0))
sombra.putalpha(emblema.getchannel('A').point(lambda a: int(a * .65)))
sombra = sombra.filter(ImageFilter.GaussianBlur(10))
x, y = EMBLEMA[0] * S, EMBLEMA[1] * S
fondo.alpha_composite(sombra, (x + 8, y + 12))
fondo.alpha_composite(emblema, (x, y))
fondo.convert('RGB').save(dst_fondo, quality=92)

ic = Image.open(emblema_src).convert('RGBA')
ic = ic.crop(ic.getbbox())
lado = max(ic.size)                         # cuadrado: con 63x64 Windows no usaba el icono
cuadro = Image.new('RGBA', (lado, lado))
cuadro.alpha_composite(ic, ((lado - ic.width) // 2, (lado - ic.height) // 2))
imgs = [cuadro.resize((s, s), Image.LANCZOS) for s in (256, 128, 64, 48, 32, 24, 16)]
imgs[0].save(dst_ico, format='ICO', sizes=[i.size for i in imgs], append_images=imgs[1:])
print('fondo', fondo.size, 'icono', [i.size for i in imgs])
