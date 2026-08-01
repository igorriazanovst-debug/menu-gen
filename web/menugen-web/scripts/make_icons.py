#!/usr/bin/env python3
"""MG_FAVICON: сборка иконок сайта из public/favicon.svg.

Единственный источник правды — favicon.svg (фирменный знак). Скрипт рендерит из
него всё, что нужно браузерам и мобильным ОС, и складывает в public/.

Ключевая деталь: в размерах вкладки (16-32 px) двойное кольцо с точками
превращается в грязное пятно, а листья становятся неразличимы. Поэтому в .ico
кладутся два варианта знака — упрощённый (только листья, во весь кадр) для
16/32 и полный для 48 и крупнее. Браузер сам берёт подходящий размер.

Запуск:
    pip install pillow cairosvg
    python scripts/make_icons.py

Перезапускать нужно только при смене логотипа.
"""

from __future__ import annotations

import io
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SRC = PUBLIC / "favicon.svg"

SVG_NS = "http://www.w3.org/2000/svg"
LEAF_CLASS = "fil1"  # класс листьев в исходнике CorelDRAW

APP_BG = (255, 255, 255, 255)  # фон иконок приложения: знак нарисован на белом


def render(svg: bytes, size: int) -> Image.Image:
    png = cairosvg.svg2png(bytestring=svg, output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def leaves_only_svg() -> bytes:
    """Тот же файл без колец и точек — остаются только листья."""
    ET.register_namespace("", SVG_NS)
    root = ET.parse(SRC).getroot()
    for parent in root.iter():
        for child in list(parent):
            tag = child.tag.split("}")[-1]
            if tag in ("path", "circle") and LEAF_CLASS not in (child.get("class") or "").split():
                parent.remove(child)
    return ET.tostring(root, encoding="utf-8")


def fit_square(img: Image.Image, size: int, pad: float, background=None) -> Image.Image:
    """Обрезает по непрозрачным пикселям и вписывает в квадрат с полями."""
    box = img.getbbox()
    if box:
        img = img.crop(box)
    inner = max(1, int(size * (1 - 2 * pad)))
    scale = min(inner / img.width, inner / img.height)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def write_ico(path: Path, images: list[Image.Image]) -> None:
    """Многокадровый .ico с PNG-полезной нагрузкой.

    Pillow умеет сохранять .ico только из одной картинки, масштабируя её под все
    размеры, — а нам нужна разная отрисовка для мелких и крупных. Поэтому
    контейнер собирается вручную: заголовок, таблица кадров, затем сами PNG.
    """
    blobs = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        blobs.append(buf.getvalue())

    header = struct.pack("<HHH", 0, 1, len(blobs))  # reserved, type=icon, count
    offset = 6 + 16 * len(blobs)
    entries = b""
    for img, blob in zip(images, blobs):
        # 0 в поле размера означает 256 — больше байта не влезает
        entries += struct.pack(
            "<BBBBHHII",
            img.width if img.width < 256 else 0,
            img.height if img.height < 256 else 0,
            0,  # палитра не используется
            0,  # reserved
            1,  # color planes
            32,  # бит на пиксель
            len(blob),
            offset,
        )
        offset += len(blob)

    path.write_bytes(header + entries + b"".join(blobs))


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Нет исходника: {SRC}")

    full_svg = SRC.read_bytes()
    leaves_svg = leaves_only_svg()

    # .ico: мелкие размеры — листья во весь кадр, крупные — знак целиком
    frames = [fit_square(render(leaves_svg, 256), s, pad=0.03) for s in (16, 32)]
    frames += [fit_square(render(full_svg, max(s, 256)), s, pad=0.0) for s in (48, 64, 128)]
    write_ico(PUBLIC / "favicon.ico", frames)

    # иконки приложения: на белом фоне — apple-touch-icon не поддерживает прозрачность
    for size, name in ((180, "apple-touch-icon.png"), (192, "logo192.png"), (512, "logo512.png")):
        fit_square(render(full_svg, 1024), size, pad=0.06, background=APP_BG).save(PUBLIC / name)

    for name in ("favicon.ico", "apple-touch-icon.png", "logo192.png", "logo512.png"):
        print(f"  {name}: {(PUBLIC / name).stat().st_size} байт")


if __name__ == "__main__":
    main()
