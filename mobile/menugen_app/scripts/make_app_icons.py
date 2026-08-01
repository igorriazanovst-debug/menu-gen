#!/usr/bin/env python3
"""MG_APPICON: генерация иконок Android-приложения из assets/images/logo.svg.

Делает два комплекта:

1. Legacy (`ic_launcher.png`, 48-192 px) — для Android 7 и старее, а также как
   запасной путь. Фон непрозрачный: прозрачность в лаунчере даёт чёрный квадрат.

2. Adaptive icon (Android 8+): отдельный слой переднего плана
   (`ic_launcher_foreground.png`) на прозрачном фоне плюс цвет подложки.
   Система сама обрезает иконку под форму лаунчера (круг, квадрат, капля),
   поэтому знак занимает центральные 66% холста — «безопасную зону». Если этого
   не сделать, на круглых иконках обрежется внешнее кольцо логотипа.

Запуск (нужны pillow и cairosvg):
    pip install pillow cairosvg
    python scripts/make_app_icons.py
"""

from __future__ import annotations

import io
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "images" / "logo.svg"
RES = ROOT / "android" / "app" / "src" / "main" / "res"

# Плотности экрана Android: mdpi = 1x, дальше кратно.
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}

LEGACY_DP = 48  # размер классической иконки в dp
ADAPTIVE_DP = 108  # размер холста adaptive icon в dp
SAFE_ZONE = 0.66  # видимая доля холста adaptive icon (остальное срежет лаунчер)

BG = (255, 255, 255, 255)  # знак нарисован на белом


def render(size: int) -> Image.Image:
    png = cairosvg.svg2png(url=str(SRC), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def fit(size: int, scale: float, background=None) -> Image.Image:
    """Знак масштабируется до scale от холста и центрируется."""
    inner = max(1, round(size * scale))
    mark = render(inner * 4).resize((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
    offset = (size - inner) // 2
    canvas.alpha_composite(mark, (offset, offset))
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Нет исходника: {SRC}")

    for name, factor in DENSITIES.items():
        out_dir = RES / f"mipmap-{name}"
        out_dir.mkdir(parents=True, exist_ok=True)

        legacy = round(LEGACY_DP * factor)
        fit(legacy, 0.94, background=BG).save(out_dir / "ic_launcher.png")

        adaptive = round(ADAPTIVE_DP * factor)
        fit(adaptive, SAFE_ZONE).save(out_dir / "ic_launcher_foreground.png")
        print(f"  mipmap-{name}: ic_launcher {legacy}px, foreground {adaptive}px")

    # Описание adaptive icon и цвет подложки.
    anydpi = RES / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    icon_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background"/>\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
        "</adaptive-icon>\n"
    )
    (anydpi / "ic_launcher.xml").write_text(icon_xml, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(icon_xml, encoding="utf-8")

    values = RES / "values"
    values.mkdir(parents=True, exist_ok=True)
    (values / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        '    <color name="ic_launcher_background">#FFFFFF</color>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    print("  mipmap-anydpi-v26/ic_launcher.xml + values/ic_launcher_background.xml")


if __name__ == "__main__":
    main()
