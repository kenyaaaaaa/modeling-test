"""Textures painted with PIL (no fonts needed: the numerals are line glyphs)."""
import math

from PIL import Image, ImageDraw, ImageFilter

INK = (24, 20, 18, 255)


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _glyph(draw, kind, x, h, w, stroke):
    """Draw one numeral letter with its left edge at x; returns its width."""
    top, bot = 0, h
    serif = w * 0.45
    if kind == "I":
        cx = x + serif
        draw.rectangle((cx - stroke / 2, top, cx + stroke / 2, bot), fill=INK)
        draw.rectangle((cx - serif, top, cx + serif, top + stroke * 0.5), fill=INK)
        draw.rectangle((cx - serif, bot - stroke * 0.5, cx + serif, bot), fill=INK)
        return serif * 2
    if kind == "V":
        draw.polygon([(x, top), (x + stroke * 1.3, top), (x + w / 2 + stroke * 0.4, bot), (x + w / 2 - stroke * 0.4, bot)], fill=INK)
        draw.polygon([(x + w - stroke * 0.7, top), (x + w, top), (x + w / 2 + stroke * 0.3, bot), (x + w / 2 - stroke * 0.1, bot)], fill=INK)
        draw.rectangle((x - stroke * 0.3, top, x + stroke * 1.6, top + stroke * 0.5), fill=INK)
        draw.rectangle((x + w - stroke, top, x + w + stroke * 0.3, top + stroke * 0.5), fill=INK)
        return w
    if kind == "X":
        draw.polygon([(x, top), (x + stroke * 1.3, top), (x + w, bot), (x + w - stroke * 1.3, bot)], fill=INK)
        draw.polygon([(x + w - stroke * 0.7, top), (x + w, top), (x + stroke * 0.7, bot), (x, bot)], fill=INK)
        for yy in (top, bot - stroke * 0.5):
            draw.rectangle((x - stroke * 0.3, yy, x + stroke * 1.6, yy + stroke * 0.5), fill=INK)
            draw.rectangle((x + w - stroke * 1.6, yy, x + w + stroke * 0.3, yy + stroke * 0.5), fill=INK)
        return w
    raise ValueError(kind)


def _numeral(text, h):
    w = h * 0.5
    stroke = h * 0.14
    img = Image.new("RGBA", (int(h * 3), int(h * 1.2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = h * 0.1
    for ch in text:
        x += _glyph(d, ch, x, h, w if ch != "I" else w * 0.5, stroke) + h * 0.04
    return img.crop((0, 0, int(x + h * 0.05), int(h) + 1))


ROMAN = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]


def clock_face(path, size, palette):
    base = _hex(palette["clock_face"])
    light = _hex(palette["stone_light"])
    img = Image.new("RGBA", (size, size), base + (255,))
    d = ImageDraw.Draw(img)
    c = size / 2
    # soft lighter centre
    for i in range(40):
        r = c * (1 - i / 40)
        t = i / 40
        col = tuple(int(base[k] * (1 - t * 0.5) + light[k] * t * 0.5) for k in range(3))
        d.ellipse((c - r, c - r, c + r, c + r), fill=col + (255,))
    ink = INK
    # minute track
    d.ellipse((c * 0.07, c * 0.07, size - c * 0.07, size - c * 0.07), outline=ink, width=max(2, size // 200))
    d.ellipse((c * 0.15, c * 0.15, size - c * 0.15, size - c * 0.15), outline=ink, width=max(1, size // 300))
    for i in range(60):
        a = 2 * math.pi * i / 60
        r0, r1 = c * 0.86, c * (0.93 if i % 5 else 0.95)
        w = max(2, size // (120 if i % 5 == 0 else 260))
        d.line((c + r0 * math.sin(a), c - r0 * math.cos(a), c + r1 * math.sin(a), c - r1 * math.cos(a)), fill=ink, width=w)
    # numerals, upright along the radius (feet towards the centre)
    h = int(size * 0.095)
    for i, text in enumerate(ROMAN):
        g = _numeral(text, h)
        a = 360 * i / 12
        g = g.rotate(-a, resample=Image.BICUBIC, expand=True)
        r = c * 0.70
        x = c + r * math.sin(math.radians(a)) - g.width / 2
        y = c - r * math.cos(math.radians(a)) - g.height / 2
        img.alpha_composite(g, (int(x), int(y)))
    img = img.filter(ImageFilter.SMOOTH)
    img.convert("RGB").save(path)
    return path
