#!/usr/bin/env python3
"""Generate optimized animated GIF cards for the GitHub profile README.

Uses Playwright with Chromium to snapshot each SVG at staggered keyframe
timestamps via the Web Animations API (anim.currentTime), then assembles
them into smooth, palette-consistent play-once GIFs using Pillow.

Each GIF plays its entrance animation once at approximately 25 fps and holds on the final frame.
No loop extension is written, so the animation plays once and then remains on its final frame.

Usage:
    python scripts/make_gifs.py
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "cards"
GIF_DIR = ROOT / "gifs"

# Canvas background colour (matches editorial theme)
BG_COLOR = (248, 246, 240, 255)

# Card specs: (width, fallback_height, animation_duration_ms, n_frames)
# Card specs: (width, fallback_height, animation_duration_ms, frame_count).
# 41 frames across 1.6s gives a smooth ~25 fps entrance without excessive GIF weight.
CARD_CONFIGS = {
    "hero":                     (1000, 340, 1600, 41),
    "graph":                    (1000, 269, 1600, 41),
    "activity":                 (1000, 340, 1600, 41),
    "tile-projects":            (328,  240, 1400, 36),
    "tile-simulations":         (328,  240, 1400, 36),
    "tile-study":               (328,  240, 1400, 36),
    "repo-cart-api":            (1000, 202, 1400, 36),
    "repo-auth-service":        (1000, 202, 1400, 36),
    "repo-blog-platform-api":   (1000, 218, 1400, 36),
}


def render_card_gif(card_name: str, page) -> Path:
    svg_path = CARDS_DIR / f"{card_name}.svg"
    if not svg_path.exists():
        sys.exit(f"Card {svg_path} not found. Run render_readme_cards.py first.")

    width, default_h, duration_ms, n_frames = CARD_CONFIGS[card_name]
    content = svg_path.read_text(encoding="utf-8")

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; overflow: hidden; }}
  .wrap {{ width: {width}px; }}
  svg {{ display: block; width: 100%; height: auto; }}
</style>
</head>
<body>
<div class="wrap">{content}</div>
</body>
</html>"""

    page.set_viewport_size({"width": width, "height": default_h or 600})
    page.set_content(html)
    page.wait_for_load_state("networkidle")

    # Measure exact rendered height of the card
    actual_h = page.evaluate("document.querySelector('svg').getBoundingClientRect().height")
    height = round(actual_h) if actual_h > 10 else default_h

    # Staggered timeline from 0 to duration_ms
    times = [int(duration_ms * i / (n_frames - 1)) for i in range(n_frames)]

    rgb_frames = []

    for t_ms in times:
        page.evaluate(f"""() => {{
            const ms = {t_ms};
            document.getAnimations().forEach(a => {{
                a.pause();
                a.currentTime = ms;
            }});
        }}""")
        png_bytes = page.screenshot(
            clip={"x": 0, "y": 0, "width": width, "height": height},
            type="png"
        )
        im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        bg = Image.new("RGBA", im.size, BG_COLOR)
        bg.alpha_composite(im)
        rgb_frames.append(bg.convert("RGB"))

    # Build ONE shared palette from every sampled frame. Per-frame adaptive palettes
    # can cause subtle colour flicker that looks like jitter during motion.
    palette_sheet = Image.new("RGB", (width, height * len(rgb_frames)))
    for index, frame in enumerate(rgb_frames):
        palette_sheet.paste(frame, (0, index * height))
    shared_palette = palette_sheet.quantize(
        colors=128,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    frames = [
        frame.quantize(palette=shared_palette, dither=Image.Dither.NONE)
        for frame in rgb_frames
    ]

    # Match each frame delay to its sampled timeline interval (GIF uses 10ms units).
    durations = [
        max(20, int(round((times[i + 1] - times[i]) / 10)) * 10)
        for i in range(len(times) - 1)
    ]
    # Hold the completed card for 5 seconds. No loop extension is written.
    durations.append(5000)

    out_path = GIF_DIR / f"{card_name}.gif"
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        optimize=False,
        disposal=2,
    )
    return out_path


def main():
    if not CARDS_DIR.exists() or not any(CARDS_DIR.glob("*.svg")):
        sys.exit("cards/ is empty. Run render_readme_cards.py first.")

    GIF_DIR.mkdir(exist_ok=True)
    t0 = time.time()

    print(f"Generating {len(CARD_CONFIGS)} animated GIFs (non-looping)...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(device_scale_factor=1)

        for name in CARD_CONFIGS:
            out_file = render_card_gif(name, page)
            kb = out_file.stat().st_size / 1024
            print(f"  gifs/{name}.gif  {kb:.1f} KB")

        browser.close()

    total_kb = sum(g.stat().st_size for g in GIF_DIR.glob("*.gif")) / 1024
    print(f"Done in {time.time() - t0:.1f}s. Total GIF size: {total_kb:.1f} KB")


if __name__ == "__main__":
    main()
