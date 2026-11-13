"""La imagen de arranque del juego (13/11/2026, "quitemos esa imagen de userjoy y pongamos una de AOFOREVER con el logo
nuevo"): shape/logo/logo01a|b|c.shp (800x600, 1024x768 y 1280x800, una por resolucion), que era el logo de UserJoy.

Ahora: el cielo del launcher (launcher/arte/cielo.webp) oscurecido hacia el azul noche, el emblema (launcher/emblema.png)
en el centro con su halo, y "ANGELS ONLINE" / "FOREVER" en oro debajo (la marca de la web). Se escriben con la
cabecera de cada original (8 bits con paleta propia, mascota_abismo._tlhs_suelto).

    python tools/logo_inicio.py
    python tools/generar_parche.py
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import mascota_abismo as ma  # noqa: E402

SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'logo'
TAMANOS = {'logo01a': (800, 600), 'logo01b': (1024, 768), 'logo01c': (1280, 800)}
ORO_CLARO, ORO, ORO_OSCURO = (255, 243, 196), (246, 205, 106), (196, 138, 44)
NOCHE = (7, 20, 64)


def _letra(tam):
    for f in ('palab.ttf', 'georgiab.ttf', 'timesbd.ttf'):
        try:
            return ImageFont.truetype(f, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def _texto_oro(lienzo, texto, cy, tam, espacio):
    """Texto centrado en oro (degradado de arriba abajo) con sombra oscura y un brillo celeste."""
    w, h = lienzo.size
    f = _letra(tam)
    d = ImageDraw.Draw(lienzo)
    letras = [(c, d.textbbox((0, 0), c, font=f)) for c in texto]
    ancho = sum(b[2] - b[0] for _c, b in letras) + espacio * (len(texto) - 1)
    mascara = Image.new('L', (w, h), 0)
    md = ImageDraw.Draw(mascara)
    x = (w - ancho) // 2
    alto = max(b[3] - b[1] for _c, b in letras)
    y = cy - alto // 2
    for c, b in letras:
        md.text((x - b[0], y - b[1] - (alto - (b[3] - b[1])) * 0), c, font=f, fill=255)
        x += (b[2] - b[0]) + espacio
    caja = mascara.getbbox()
    sombra = Image.new('RGBA', (w, h), (2, 6, 24, 0))
    sombra.putalpha(mascara.filter(ImageFilter.GaussianBlur(max(2, tam // 14))).point(lambda a: min(255, a * 2)))
    lienzo.alpha_composite(sombra, (2, 3))
    brillo = Image.new('RGBA', (w, h), (127, 210, 255, 0))
    brillo.putalpha(mascara.filter(ImageFilter.GaussianBlur(max(3, tam // 6))).point(lambda a: a // 2))
    lienzo.alpha_composite(brillo)
    degr = Image.new('RGBA', (w, h))
    gd = ImageDraw.Draw(degr)
    for yy in range(caja[1], caja[3] + 1):
        t = (yy - caja[1]) / max(1, caja[3] - caja[1])
        a, b2 = (ORO_CLARO, ORO) if t < 0.5 else (ORO, ORO_OSCURO)
        k = t * 2 if t < 0.5 else (t - 0.5) * 2
        gd.line((0, yy, w, yy), fill=tuple(int(a[i] + (b2[i] - a[i]) * k) for i in range(3)) + (255,))
    degr.putalpha(mascara)
    lienzo.alpha_composite(degr)


def imagen(w, h) -> Image.Image:
    cielo = Image.open(RAIZ / 'launcher' / 'arte' / 'cielo.webp').convert('RGB')
    k = max(w / cielo.width, h / cielo.height)
    cielo = cielo.resize((round(cielo.width * k), round(cielo.height * k)), Image.LANCZOS)
    x = (cielo.width - w) // 2
    lienzo = cielo.crop((x, 0, x + w, h)).filter(ImageFilter.GaussianBlur(w / 260)).convert('RGBA')
    # velo azul noche: mas oscuro en los bordes y abajo, para que el emblema y el nombre destaquen
    velo = Image.new('RGBA', (w, h), NOCHE + (0,))
    vd = ImageDraw.Draw(velo)
    for i in range(60):
        t = i / 59
        vd.ellipse((-w * 0.2 + t * w * 0.45, -h * 0.25 + t * h * 0.45, w * 1.2 - t * w * 0.45, h * 1.25 - t * h * 0.45),
                   fill=NOCHE + (int(235 - 150 * t),))
    lienzo.alpha_composite(velo.filter(ImageFilter.GaussianBlur(w / 40)))
    # el emblema con su halo
    lado = int(h * 0.42)
    cx, cy = w // 2, int(h * 0.40)
    halo = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((cx - lado * 0.75, cy - lado * 0.75, cx + lado * 0.75, cy + lado * 0.75),
                                 fill=(127, 210, 255, 120))
    lienzo.alpha_composite(halo.filter(ImageFilter.GaussianBlur(lado / 5)))
    emblema = Image.open(RAIZ / 'launcher' / 'emblema.png').convert('RGBA')
    emblema = emblema.resize((lado, round(emblema.height * lado / emblema.width)), Image.LANCZOS)
    lienzo.alpha_composite(emblema, (cx - lado // 2, cy - emblema.height // 2))
    # el nombre
    _texto_oro(lienzo, 'ANGELS ONLINE', int(h * 0.72), int(h * 0.085), int(h * 0.008))
    _texto_oro(lienzo, 'FOREVER', int(h * 0.82), int(h * 0.06), int(h * 0.03))
    return lienzo


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, (w, h) in TAMANOS.items():
        im = imagen(w, h)
        (SALIDA / (nombre + '.shp')).write_bytes(ma._tlhs_suelto(im, 'shape\\logo\\%s.shp' % nombre, 0, 0))
        im.convert('RGB').save(RAIZ / 'docs' / ('arranque_%s.png' % nombre))
        print('escrito', nombre, (w, h))


if __name__ == '__main__':
    main()
