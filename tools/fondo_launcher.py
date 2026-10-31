"""El fondo y el icono del launcher (31/10/2026): cielo de azul noche a carmesi, como las alas del logo de Angels
Online Forever, con estrellas, brillo dorado y el logo arriba a la derecha (sobre el boton JUGAR).

    python tools/fondo_launcher.py launcher/logo.png <logo_redondo.png> launcher/fondo.jpg launcher/icono.ico
    python tools/compilar_launcher.py --ip <IP-del-VPS> --probar

launcher/logo.png es el logo con alas sin el fondo de cuadros que traia pintado. El fondo sale al doble de la ventana
(980x580) y el exe lo escala.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
logo_png, icono_src, dst_fondo, dst_ico = sys.argv[1:5]
W, H, S = 1960, 1160, 2          # el doble de la ventana (980x580)
rng = np.random.default_rng(11)
x = np.linspace(0, 1, W)[None, :]; y = np.linspace(0, 1, H)[:, None]
azul = np.array([10, 20, 62.]); morado = np.array([38, 14, 58.]); rojo = np.array([92, 10, 30.])
t = np.clip(x * 1.0, 0, 1)
base = np.where(t[..., None] < 0.5, azul + (morado - azul) * (t[..., None] / 0.5),
                morado + (rojo - morado) * ((t[..., None] - 0.5) / 0.5))
base = base * (1.0 - 0.35 * y[..., None])                   # mas oscuro abajo
img = np.broadcast_to(base, (H, W, 3)).copy()
# nebulosa: ruido grande y difuminado, azul a la izquierda y rojo a la derecha
for color, lado in (((60, 110, 255), 0.22), ((255, 50, 70), 0.85), ((150, 60, 220), 0.5)):
    ruido = Image.fromarray((rng.random((H // 16, W // 16)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    ruido = np.array(ruido.filter(ImageFilter.GaussianBlur(45))) / 255.0
    peso = np.exp(-((x - lado) ** 2) / 0.05) * (ruido ** 1.6) * 0.9
    img += peso[..., None] * np.array(color)
# brillo dorado detras del logo
cx, cy = 1540 / W, 270 / H
img += (np.exp(-(((x - cx) * 1.7) ** 2 + ((y - cy) * 1.0) ** 2) / 0.02) * 0.5)[..., None] * np.array([255, 190, 80])
fondo = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
# estrellas
capa = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(capa)
for _ in range(700):
    px, py = rng.random() * W, rng.random() * H
    r = rng.choice([0.8, 1.2, 1.8, 2.6], p=[.5, .3, .15, .05])
    c = (255, 236, 190) if rng.random() < .3 else (220, 230, 255)
    d.ellipse((px - r, py - r, px + r, py + r), fill=c + (int(120 + rng.random() * 135),))
fondo.alpha_composite(capa.filter(ImageFilter.GaussianBlur(0.6)))
glow = capa.filter(ImageFilter.GaussianBlur(5)); fondo.alpha_composite(glow)
# logo arriba a la derecha (en la ventana: x 595..955, y 48..)
logo = Image.open(logo_png)
ancho = 400 * S; alto = int(logo.height * ancho / logo.width)
logo = logo.resize((ancho, alto), Image.LANCZOS)
sombra = Image.new('RGBA', logo.size, (0, 0, 0, 0)); sombra.putalpha(logo.getchannel('A').point(lambda a: int(a * .6)))
sombra = sombra.filter(ImageFilter.GaussianBlur(14))
fondo.alpha_composite(sombra, (568 * S + 6, 34 * S + 10)); fondo.alpha_composite(logo, (568 * S, 34 * S))
fondo.convert('RGB').save(dst_fondo, quality=92)
print('logo en la ventana: alto', alto // S)
ic = Image.open(icono_src).convert('RGBA')
ic = ic.crop(ic.getbbox())
lado = max(ic.size)                 # cuadrado: con 63x64 Windows no usaba el icono
cuadro = Image.new('RGBA', (lado, lado)); cuadro.alpha_composite(ic, ((lado - ic.width) // 2, (lado - ic.height) // 2))
ic = cuadro

def emblema(lado):
    """Para 16-48 px el logo entero es una mancha: circulo azul/carmesi, borde de oro y una A blanca con halo."""
    from PIL import ImageFont
    k = 8; L = lado * k
    e = Image.new('RGBA', (L, L)); d = ImageDraw.Draw(e)
    d.ellipse((0, 0, L - 1, L - 1), fill=(240, 190, 70))
    m = int(L * 0.07)
    d.pieslice((m, m, L - m, L - m), 90, 270, fill=(22, 52, 160))
    d.pieslice((m, m, L - m, L - m), 270, 90, fill=(176, 18, 44))
    try:
        f = ImageFont.truetype('C:/Windows/Fonts/georgiab.ttf', int(L * 0.66))
    except OSError:
        f = ImageFont.load_default()
    d.text((L / 2, L * 0.6), 'A', font=f, anchor='mm', fill=(255, 255, 255), stroke_width=max(1, L // 40),
           stroke_fill=(60, 30, 10))
    hw, hy = L * 0.22, L * 0.2
    d.ellipse((L / 2 - hw, hy - L * 0.055, L / 2 + hw, hy + L * 0.055), outline=(255, 214, 90), width=max(2, L // 22))
    return e.resize((lado, lado), Image.LANCZOS)


chicos = {s: emblema(s) for s in (16, 24, 32, 48)}
grandes = {s: ic.resize((s, s), Image.LANCZOS) for s in (64, 128, 256)}
imgs = [chicos.get(s) or grandes[s] for s in (256, 128, 64, 48, 32, 24, 16)]
imgs[0].save(dst_ico, format='ICO', sizes=[i.size for i in imgs], append_images=imgs[1:])
