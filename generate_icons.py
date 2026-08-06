#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Иконки приложения (PWA / домашний экран iPhone): тёмная плитка + 🎭."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).parent / "icons"
OUT.mkdir(exist_ok=True)
EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
BG = (14, 17, 22, 255)  # #0e1116


def make(size):
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)
    # скруглённая подложка-акцент
    pad = int(size * 0.10)
    d.rounded_rectangle([pad, pad, size - pad, size - pad],
                        radius=int(size * 0.22), fill=(23, 27, 34, 255))
    try:
        # Apple Color Emoji поддерживает только страйк 160 — рендерим и масштабируем
        f = ImageFont.truetype(EMOJI_FONT, 160)
        em = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(em).text((80, 80), "🎭", font=f, anchor="mm", embedded_color=True)
        target = int(size * 0.62)
        em = em.resize((target, target), Image.LANCZOS)
        img.alpha_composite(em, ((size - target) // 2, (size - target) // 2))
    except Exception as e:
        # запасной вариант — золотая «Р»
        try:
            f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", int(size * 0.5))
        except Exception:
            f = ImageFont.load_default()
        d.text((size / 2, size / 2), "Р", font=f, anchor="mm", fill=(255, 207, 91, 255))
    img.save(OUT / f"icon-{size}.png")
    print("icon-%d.png" % size)


for s in (192, 512):
    make(s)
# apple-touch-icon 180
Image.open(OUT / "icon-192.png").resize((180, 180), Image.LANCZOS).save(OUT / "icon-180.png")
print("icon-180.png")
