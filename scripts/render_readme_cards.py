#!/usr/bin/env python3
"""Render editorial SVG cards for the GitHub profile README.

    python scripts/render_readme_cards.py                 # writes cards/*.svg
    STATIC=1 python scripts/render_readme_cards.py        # writes preview/ (final frame)
    python scripts/render_readme_cards.py --build-fonts   # download and prepare local font files

Typography:
    - Display: Bodoni Moda (Regular & Italic)
    - Body: Inter (Regular & Semibold)
    - Code / Metadata: JetBrains Mono (Medium)
    - Supporting: Plus Jakarta Sans

Palette (Refined Editorial):
    - Background: Warm off-white #F8F6F0 / Card surface: #FFFFFF
    - Ink / Charcoal: #181614
    - Soft Grey: #605A54 / Muted: #8C847A
    - Dividers / Rules: #E6E1D8
    - Accent: Restrained Indigo #4F46E5 / Soft Lavender #EEF2FF
    - Warm Amber: #D97706
"""
from __future__ import annotations

import base64
import json
import math
import os
import sys
import urllib.request
from datetime import date, timedelta
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"
OUT = ROOT / ("preview" if STATIC else "cards")
FONT_DIR = ROOT / "fonts"
DATA_DIR = ROOT / "data"

# ---------------------------------------------------------------------------
# Profile Metadata
# ---------------------------------------------------------------------------
USERNAME   = "deoreparth700-design"
NAME_FIRST = "Parth"
NAME_LAST  = "Deore"
ROLE       = "Backend Developer"
TAGLINE    = ("Final-year CS student who designs the schema and API contract "
              "first, then builds robust FastAPI and PostgreSQL backends.")
STATUS     = "Open to internships & backend roles"
LOCATION   = "Chh. Sambhaji Nagar, India · GMT+5:30"
SITE       = "https://parthdeore.vercel.app/"
LINKEDIN   = "https://www.linkedin.com/in/parth-deore-1232b2212"
REPOS_TAB  = f"https://github.com/{USERNAME}?tab=repositories"

FEATURED = [
    dict(repo="Cart-API",
         blurb="E-commerce cart backend with real-time inventory, atomic PostgreSQL "
               "transactions and Razorpay payments verified by HMAC webhooks.",
         tags=["FastAPI", "PostgreSQL", "JWT", "Razorpay", "Docker"],
         highlight="41 automated tests"),
    dict(repo="auth-service",
         blurb="Authentication API with JWT access and refresh token rotation, bcrypt "
               "hashing, sliding session expiry and rate limiting.",
         tags=["FastAPI", "PostgreSQL", "JWT", "Bcrypt", "Render"],
         highlight="Token rotation"),
    dict(repo="blog-platform-api",
         blurb="Article publishing API with Redis response caching, Neon PostgreSQL, "
               "JWT auth and automated Pytest coverage.",
         tags=["FastAPI", "PostgreSQL", "Redis", "Pytest", "Render"],
         highlight="16.9x faster on a warm cache (local benchmark)"),
]

# ---------------------------------------------------------------------------
# Editorial Color Palette
# ---------------------------------------------------------------------------
BG_CANVAS = "#F8F6F0"   # warm off-white canvas
BG_CARD   = "#FFFFFF"   # crisp white card surface
BG_MUTED  = "#F2EFEB"   # soft warm grey surface
INK       = "#181614"   # deep editorial charcoal
INK_MID   = "#3D3833"   # secondary charcoal
SLATE     = "#68615A"   # soft grey for body & labels
RULE      = "#E8E3DA"   # subtle divider rule
RULE_DARK = "#D0C9BE"   # slightly deeper border
INDIGO    = "#4338CA"   # restrained editorial indigo
LAVENDER  = "#EEF2FF"   # subtle accent background
AMBER     = "#D97706"   # warm status / star amber
GREEN     = "#16A34A"   # active status green

# ---------------------------------------------------------------------------
# Fonts Definition (bundled locally)
# ---------------------------------------------------------------------------
FONTS = {
    "bd4":  ("Bodoni Moda", 400, "normal", "bodoni-400.woff2"),
    "bd4i": ("Bodoni Moda", 400, "italic", "bodoni-400i.woff2"),
    "in4":  ("Inter",       400, "normal", "inter-400.woff2"),
    "in6":  ("Inter",       600, "normal", "inter-600.woff2"),
    "m5":   ("JetBrains Mono", 500, "normal", "mono-500.woff"),
    "pjs":  ("Plus Jakarta Sans", 600, "normal", "sans-600.woff"),
    "s4":   ("Plus Jakarta Sans", 400, "normal", "sans-400.woff"),
    "s6":   ("Plus Jakarta Sans", 600, "normal", "sans-600.woff"),
    "s8":   ("Plus Jakarta Sans", 800, "normal", "sans-800.woff"),
}

FONT_URLS = {
    "bodoni_reg":  "https://fonts.gstatic.com/s/bodonimoda/v28/aFT67PxzY382XsXX63LUYL6GYFcan6NJrKp-VPjfJMShrpsGFUt8oU7awIA.ttf",
    "bodoni_ital": "https://fonts.gstatic.com/s/bodonimoda/v28/aFT07PxzY382XsXX63LUYJSPUqb0pL6OQqxrZLnVbvZedvJtj-V7tIaZKMN4sQ.ttf",
    "inter_reg":   "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2",
    "inter_semi":  "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuI6fAZ9hiJ-Ek-_EeA.woff2",
    "sans":        "https://github.com/google/fonts/raw/main/ofl/plusjakartasans/PlusJakartaSans%5Bwght%5D.ttf",
    "mono":        "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}

KEEP = (list(range(0x20, 0x7F)) +
        [0xA0, 0xB7, 0xD7, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D,
         0x2026, 0x00D7, 0x00B1, 0x2715, 0x2197, 0x2192, 0x2022])


def build_fonts():
    """Ensure all font files exist and are subsetted."""
    FONT_DIR.mkdir(exist_ok=True)
    # 1. Download Inter woff2 files if missing
    for key, fname in [("inter_reg", "inter-400.woff2"), ("inter_semi", "inter-600.woff2")]:
        p = FONT_DIR / fname
        if not p.exists():
            req = urllib.request.Request(FONT_URLS[key], headers={"User-Agent": "Mozilla/5.0"})
            p.write_bytes(urllib.request.urlopen(req, timeout=30).read())

    # 2. Download Bodoni Moda TTF and subset to woff2
    from fontTools import subset
    from fontTools.ttLib import TTFont
    for key, ttf_name, woff2_name in [
        ("bodoni_reg", "bodoni-400.ttf", "bodoni-400.woff2"),
        ("bodoni_ital", "bodoni-400i.ttf", "bodoni-400i.woff2")
    ]:
        dest = FONT_DIR / woff2_name
        if not dest.exists():
            ttf_path = FONT_DIR / ttf_name
            if not ttf_path.exists():
                req = urllib.request.Request(FONT_URLS[key], headers={"User-Agent": "Mozilla/5.0"})
                ttf_path.write_bytes(urllib.request.urlopen(req, timeout=30).read())
            font = TTFont(str(ttf_path))
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.hinting = False
            opts.layout_features = ["kern", "liga", "calt"]
            opts.name_IDs = [1, 2]
            s = subset.Subsetter(opts)
            s.populate(unicodes=KEEP)
            s.subset(font)
            font.flavor = "woff2"
            font.save(str(dest))
    print("Fonts ready.")


def font_css(keys) -> str:
    """Generate @font-face rules with base64 data URIs for specified fonts."""
    out = []
    for k in keys:
        family, weight, style, fname = FONTS[k]
        p = FONT_DIR / fname
        if not p.exists():
            sys.exit(f"Missing font {p}. Run with --build-fonts first.")
        b64 = base64.b64encode(p.read_bytes()).decode()
        fmt = "woff2" if fname.endswith(".woff2") else "woff"
        out.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:{style};"
            f"src:url(data:font/{fmt};base64,{b64}) format('{fmt}');font-display:swap;}}"
        )
    return "".join(out)


# ---------------------------------------------------------------------------
# CSS Styling & Animation System
# ---------------------------------------------------------------------------
BASE_CSS = """\
text{font-family:'Inter','Segoe UI',system-ui,sans-serif;text-rendering:geometricPrecision;-webkit-font-smoothing:antialiased}
.serif{font-family:'Bodoni Moda',Georgia,'Times New Roman',serif}
.mono{font-family:'JetBrains Mono',ui-monospace,monospace}
.pjs{font-family:'Plus Jakarta Sans','Segoe UI',system-ui,sans-serif}
"""

# Staggered entrance animations: smooth spring-like bezier curves
ANIM_CSS = """\
.rise{animation:rise 1.0s cubic-bezier(0.16, 1, 0.3, 1) var(--d, 0s) both}
.rise-sm{animation:riseSm 0.85s cubic-bezier(0.16, 1, 0.3, 1) var(--d, 0s) both}
.fade{animation:fade 0.9s cubic-bezier(0.16, 1, 0.3, 1) var(--d, 0s) both}
.grow{transform-box:fill-box;transform-origin:50% 100%;animation:grow 0.9s cubic-bezier(0.16, 1, 0.3, 1) var(--d, 0s) both}
.pop{transform-box:fill-box;transform-origin:50% 50%;animation:pop 0.8s cubic-bezier(0.34, 1.4, 0.64, 1) var(--d, 0s) both}
.col{animation:colin 0.6s cubic-bezier(0.16, 1, 0.3, 1) var(--d, 0s) both}
.nudge{animation:nudge 2.2s ease-in-out var(--d, 0s) infinite}
@keyframes rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
@keyframes riseSm{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes grow{from{opacity:0;transform:scaleY(0)}to{opacity:1;transform:scaleY(1)}}
@keyframes pop{0%{opacity:0;transform:scale(0.85)}60%{opacity:1;transform:scale(1.03)}100%{opacity:1;transform:scale(1)}}
@keyframes colin{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes nudge{0%,100%{transform:translateX(0)}50%{transform:translateX(4px)}}
.still{display:none}
@media(prefers-reduced-motion:reduce){*{animation:none!important}.live{display:none}.still{display:inline}}
"""


def A(anim_class: str, delay: float, extra_classes: str = "") -> str:
    """Build a class attribute and style delay. Merges animation and font classes safely."""
    classes = (extra_classes + " " + anim_class).strip() if extra_classes else anim_class
    if STATIC:
        return f' class="{extra_classes}"' if extra_classes else ""
    return f' class="{classes}" style="--d:{delay:.2f}s"'


def svg(w: int, h: int, body: str, fonts: tuple[str, ...], title: str, desc: str, defs: str = "") -> str:
    css = font_css(fonts) + BASE_CSS + ("" if STATIC else ANIM_CSS)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img" aria-label="{escape(title)}">'
            f'<title>{escape(title)}</title>'
            f'<desc>{escape(desc)}</desc>'
            f'<style>{css}</style><defs>{defs}</defs>{body}</svg>')


def wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip() if cur else w
    if cur:
        lines.append(cur)
    return lines


def arrow(cx, cy, r, bg, fg, delay):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{bg}"/>'
            f'<g{A("nudge", delay)}><path d="M{cx - 6} {cy}H{cx + 6}'
            f'M{cx + 1} {cy - 5}L{cx + 6.5} {cy}L{cx + 1} {cy + 5}" '
            f'fill="none" stroke="{fg}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/></g>')


def star(cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append(f"{cx + rad * math.cos(ang):.1f},{cy + rad * math.sin(ang):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


def fmt_date(d: date) -> str:
    return f"{d.day} {d.strftime('%b')} {d.year}"


def mix(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------
def load_data():
    cpath = DATA_DIR / "contributions.json"
    rpath = DATA_DIR / "repos.json"
    if not cpath.exists():
        sys.exit("data/contributions.json missing. Run scripts/fetch_data.py first.")
    raw = json.loads(cpath.read_text(encoding="utf-8"))
    days = {date.fromisoformat(d): int(c) for d, c in raw["days"]}
    end = date.fromisoformat(raw["end"])
    start = end - timedelta(days=364)
    full = {start + timedelta(days=i): days.get(start + timedelta(days=i), 0) for i in range(365)}
    repos = {}
    if rpath.exists():
        repos = {r["name"].lower(): r for r in json.loads(rpath.read_text(encoding="utf-8"))["repos"]}
    return full, start, end, repos


def stats(days, start, end):
    d = end if days[end] > 0 else end - timedelta(days=1)
    current = 0
    while d >= start and days[d] > 0:
        current += 1
        d -= timedelta(days=1)
    longest = run = 0
    for i in range(365):
        run = run + 1 if days[start + timedelta(days=i)] > 0 else 0
        longest = max(longest, run)
    active = sum(1 for c in days.values() if c > 0)
    busiest = max(days.items(), key=lambda kv: (kv[1], kv[0]))
    months, y, m = [], end.year, end.month
    for _ in range(12):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    per_month = [sum(c for dd, c in days.items() if (dd.year, dd.month) == ym) for ym in months]
    return dict(current=current, longest=longest, active=active, busiest=busiest,
                months=months, per_month=per_month, total=sum(days.values()))


# ---------------------------------------------------------------------------
# Card 1: HERO (Editorial Typography, Serif Name, Monogram, No Photo)
# ---------------------------------------------------------------------------
def hero() -> str:
    W, H = 1000, 340
    D = 0.0

    # Clean off-white surface with border
    bg = (
        f'<rect width="{W}" height="{H}" rx="16" fill="{BG_CANVAS}"/>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="15.5" '
        f'fill="{BG_CARD}" stroke="{RULE}"/>'
    )

    # Subtle decorative PD monogram watermark on right side (behind content)
    watermark = (
        f'<text x="860" y="230" font-size="200" font-weight="400" font-style="italic" '
        f'fill="{INDIGO}" opacity=".035" class="serif" text-anchor="middle">PD</text>'
    )

    # Top metadata row: location on right, role tag on left
    top_meta = (
        f'<g{A("fade", D + 0.15)}>'
        f'<text x="56" y="44" font-size="11" font-weight="500" fill="{SLATE}" '
        f'class="mono" letter-spacing="1.4">{escape(ROLE.upper())}</text>'
        f'<text x="944" y="44" text-anchor="end" font-size="11" font-weight="500" '
        f'fill="{SLATE}" class="mono" letter-spacing="0.8">{escape(LOCATION.upper())}</text>'
        f'<line x1="56" y1="58" x2="944" y2="58" stroke="{RULE}" stroke-width="1"/>'
        f'</g>'
    )

    # Large Editorial Serif Name: First Name Regular, Surname Italic
    name_svg = (
        f'<g{A("rise", D + 0.25)}>'
        f'<text x="56" y="142" font-size="76" font-weight="400" fill="{INK}" '
        f'class="serif" letter-spacing="-1">{escape(NAME_FIRST)}</text>'
        f'<text x="56" y="214" font-size="76" font-weight="400" font-style="italic" '
        f'fill="{INDIGO}" class="serif" letter-spacing="-1">{escape(NAME_LAST)}</text>'
        f'</g>'
    )

    # Right side: Description & Tech Focus (aligned next to the name)
    tag_lines = wrap_text(TAGLINE, 44)
    desc_svg = "".join(
        f'<text x="520" y="{118 + i * 24}" font-size="15.5" font-weight="400" '
        f'fill="{INK_MID}">{escape(line)}</text>'
        for i, line in enumerate(tag_lines)
    )

    # Tech stack pills on right side below description
    stack_tags = ["FastAPI", "PostgreSQL", "Redis", "Docker", "Pytest"]
    pills_svg = []
    px = 520
    py = 186
    for tag in stack_tags:
        pw = len(tag) * 8 + 18
        pills_svg.append(
            f'<rect x="{px}" y="{py}" width="{pw}" height="24" rx="12" '
            f'fill="{BG_MUTED}" stroke="{RULE_DARK}" stroke-width=".7"/>'
            f'<text x="{px + pw / 2}" y="{py + 16}" text-anchor="middle" '
            f'font-size="11" font-weight="500" fill="{SLATE}" class="mono">{escape(tag)}</text>'
        )
        px += pw + 8

    right_content = (
        f'<g{A("rise", D + 0.45)}>'
        f'{desc_svg}'
        f'{"".join(pills_svg)}'
        f'</g>'
    )

    # Bottom Row: Active Status Indicator (left) + Links (right)
    # The status indicator animates in last with a gentle pop
    bottom_bar = (
        f'<line x1="56" y1="274" x2="944" y2="274" stroke="{RULE}" stroke-width="1"/>'
        f'<g{A("pop", D + 0.95)}>'
        f'<circle cx="64" cy="306" r="4.5" fill="{GREEN}"/>'
        f'<circle cx="64" cy="306" r="8" fill="none" stroke="{GREEN}" stroke-width="1" opacity=".4"/>'
        f'<text x="80" y="310" font-size="12" font-weight="500" fill="{INK_MID}" '
        f'class="mono" letter-spacing="0.4">{escape(STATUS)}</text>'
        f'</g>'
        f'<g{A("fade", D + 0.8)}>'
        f'<text x="770" y="310" font-size="11.5" font-weight="500" fill="{INDIGO}" '
        f'class="mono" letter-spacing="0.8">PORTFOLIO ↗</text>'
        f'<text x="880" y="310" font-size="11.5" font-weight="500" fill="{SLATE}" '
        f'class="mono" letter-spacing="0.8">LINKEDIN ↗</text>'
        f'</g>'
    )

    body = bg + watermark + top_meta + name_svg + right_content + bottom_bar
    return svg(W, H, body, ("bd4", "bd4i", "in4", "in6", "m5"),
               f"{NAME_FIRST} {NAME_LAST} — {ROLE}",
               TAGLINE)


# ---------------------------------------------------------------------------
# Card 2: CONTRIBUTION GRAPH
# ---------------------------------------------------------------------------
LEVELS = [mix("#F3F0EA", INDIGO, t) for t in (0, .22, .48, .74, 1.0)]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def graph(days, start, end, st) -> str:
    W, x0, y0 = 1000, 66, 96
    D = 0.05
    first = start - timedelta(days=(start.weekday() + 1) % 7)
    cols = (end - first).days // 7 + 1
    pitch = (W - x0 - 36) / cols
    cell = pitch - 3.2
    nz = sorted(c for c in days.values() if c > 0)
    cuts = [nz[int(len(nz) * q)] for q in (.25, .5, .75)] if nz else [1, 2, 3]

    def level(c):
        return 0 if c == 0 else 1 + sum(c > t for t in cuts)

    parts, labelled = [], []
    for c in range(cols):
        cells = []
        for r in range(7):
            d = first + timedelta(days=7 * c + r)
            if d < start or d > end:
                continue
            if d.day == 1 and (not labelled or c - labelled[-1][0] >= 3):
                labelled.append((c, MON[d.month - 1]))
            cells.append(
                f'<rect x="{x0 + c * pitch:.1f}" y="{y0 + r * pitch:.1f}" '
                f'width="{cell:.1f}" height="{cell:.1f}" rx="2.8" '
                f'fill="{LEVELS[level(days[d])]}"/>'
            )
        parts.append(f'<g{A("col", D + 0.05 + c * 0.012)}>{" ".join(cells)}</g>')

    if not labelled or labelled[0][0] >= 3:
        labelled.insert(0, (0, MON[start.month - 1]))

    months = "".join(
        f'<text class="mono" x="{x0 + c * pitch:.1f}" y="84" '
        f'font-size="11" font-weight="500" fill="{SLATE}">{m}</text>'
        for c, m in labelled
    )
    dows = "".join(
        f'<text class="mono" x="34" y="{y0 + r * pitch + cell - 2:.1f}" '
        f'font-size="10" font-weight="500" fill="{SLATE}">{n}</text>'
        for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )

    H = round(y0 + 7 * pitch + 52)
    lx = W - 36 - 5 * 18 - 46
    legend = (
        f'<text x="{lx - 40:.0f}" y="{H - 22}" font-size="11" font-weight="500" '
        f'fill="{SLATE}" class="mono">Less</text>'
        + "".join(
            f'<rect x="{lx + i * 18}" y="{H - 33}" width="13" height="13" '
            f'rx="3" fill="{LEVELS[i]}"/>'
            for i in range(5)
        )
        + f'<text x="{lx + 5 * 18 + 6}" y="{H - 22}" font-size="11" '
        f'font-weight="500" fill="{SLATE}" class="mono">More</text>'
    )

    body = (
        f'<rect width="{W}" height="{H}" rx="16" fill="{BG_CANVAS}"/>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="15.5" '
        f'fill="{BG_CARD}" stroke="{RULE}"/>'
        f'<g{A("rise-sm", D)}>'
        f'<text x="36" y="50" font-size="20" font-weight="600" fill="{INK}" class="pjs">'
        f'{st["total"]:,} contributions in the last year</text>'
        f'</g>'
        f'<g{A("fade", D + 0.1)}>{months}{dows}</g>'
        f'{"".join(parts)}'
        f'<g{A("fade", D + 0.8)}>{legend}</g>'
    )
    return svg(W, H, body, ("in4", "in6", "m5", "pjs", "s6"),
               "Contribution Graph",
               f"{st['total']} contributions in the last year, shown as an activity heatmap.")


# ---------------------------------------------------------------------------
# Card 3: ACTIVITY (Monthly bars + Stats)
# ---------------------------------------------------------------------------
def activity(st) -> str:
    W, H = 1000, 340
    D = 0.05
    base_y, top_y = 268, 110
    xl, xr = 40, 646
    slot = (xr - xl) / 12
    bw = 28
    pm = st["per_month"]
    vmax = max(pm) or 1
    best = max(range(12), key=lambda i: (pm[i], i))
    bars, labels = [], []

    for i, v in enumerate(pm):
        h = max(6, (base_y - top_y) * v / vmax)
        x = xl + i * slot + (slot - bw) / 2
        is_best = i == best
        col = INDIGO if is_best else mix(RULE_DARK, INDIGO, 0.35)
        bars.append(
            f'<rect{A("grow", D + 0.1 + i * 0.045)} x="{x:.1f}" y="{base_y - h:.1f}" '
            f'width="{bw}" height="{h:.1f}" rx="5" fill="{col}"/>'
        )
        if is_best:
            labels.append(
                f'<text{A("pop", D + 0.1 + 12 * 0.045 + 0.15, "pjs")} '
                f'x="{x + bw / 2:.1f}" y="{base_y - h - 10:.1f}" text-anchor="middle" '
                f'font-size="18" font-weight="600" fill="{INDIGO}">{v}</text>'
            )
        else:
            labels.append(
                f'<text{A("fade", D + 0.1 + i * 0.045 + 0.15, "pjs")} '
                f'x="{x + bw / 2:.1f}" y="{base_y - h - 8:.1f}" text-anchor="middle" '
                f'font-size="11.5" font-weight="400" fill="{SLATE}">{v}</text>'
            )
        labels.append(
            f'<text x="{x + bw / 2:.1f}" y="{base_y + 24}" text-anchor="middle" '
            f'font-size="11" font-weight="500" fill="{INK if is_best else SLATE}" '
            f'class="mono">{MON[st["months"][i][1] - 1]}</text>'
        )

    def block(i, label, big, unit, sub):
        top = 26 + i * 95
        d = D + 0.2 + i * 0.15
        u = (f'<text x="{684 + len(big) * 22 + 8}" y="{top + 58}" font-size="16" '
             f'font-weight="600" fill="{SLATE}" class="pjs">{unit}</text>' if unit else "")
        return (
            f'<g{A("rise-sm", d)}>'
            f'<text x="680" y="{top + 22}" font-size="11" font-weight="500" '
            f'fill="{SLATE}" class="mono" letter-spacing="1.2">{label.upper()}</text>'
            f'<text x="680" y="{top + 60}" font-size="42" font-weight="600" '
            f'fill="{INK}" class="pjs">{big}</text>{u}'
            f'<text x="680" y="{top + 78}" font-size="11.5" font-weight="400" '
            f'fill="{SLATE}" class="mono">{sub}</text>'
            f'</g>'
        )

    bday, bcount = st["busiest"]
    cur = st["current"]
    stats_svg = (
        block(0, "Streak", str(cur), "day" if cur == 1 else "days", f"longest: {st['longest']} days")
        + f'<line x1="680" y1="120" x2="956" y2="120" stroke="{RULE}"/>'
        + block(1, "Active", str(st["active"]), "", "active days out of 365")
        + f'<line x1="680" y1="215" x2="956" y2="215" stroke="{RULE}"/>'
        + block(2, "Peak Day", str(bcount), "commits", fmt_date(bday))
    )

    body = (
        f'<rect width="{W}" height="{H}" rx="16" fill="{BG_CANVAS}"/>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="15.5" '
        f'fill="{BG_CARD}" stroke="{RULE}"/>'
        f'<g{A("rise-sm", D)}>'
        f'<text x="40" y="50" font-size="20" font-weight="600" fill="{INK}" class="pjs">'
        f'Contributions per month</text>'
        f'<text x="40" y="72" font-size="13" font-weight="400" fill="{SLATE}" class="pjs">'
        f'Last 12 months · peak month highlighted in indigo</text>'
        f'</g>'
        f'<line x1="{xl}" y1="{base_y}" x2="{xr}" y2="{base_y}" stroke="{RULE}" stroke-width="1.5"/>'
        f'<line x1="656" y1="36" x2="656" y2="{H - 32}" stroke="{RULE}" stroke-width=".8"/>'
        f'{"".join(bars)}{"".join(labels)}{stats_svg}'
    )
    return svg(W, H, body, ("in4", "in6", "m5", "pjs", "s6"),
               "Contributions Per Month",
               f"Monthly contributions. Current streak: {cur} days. Active: {st['active']} days.")


# ---------------------------------------------------------------------------
# Card 4, 5, 6: THREE TILES (Projects, Simulations, Study)
# ---------------------------------------------------------------------------
TW, TH = 328, 240


def tile_projects(n: int) -> str:
    D = 0.05
    body = (
        f'<g{A("pop", D)}>'
        f'<rect width="{TW}" height="{TH}" rx="16" fill="{BG_CARD}" stroke="{RULE}"/>'
        f'<text x="26" y="44" font-size="11" font-weight="500" fill="{SLATE}" '
        f'class="mono" letter-spacing="1.5">PROJECTS</text>'
        f'<text x="24" y="140" font-size="94" font-weight="600" fill="{INK}" '
        f'class="pjs" letter-spacing="-3">{n}</text>'
        f'<text x="26" y="172" font-size="15" font-weight="500" fill="{INK_MID}" '
        f'class="pjs">public repositories</text>'
        f'<text x="26" y="196" font-size="12" font-weight="400" fill="{INDIGO}" '
        f'class="mono">FastAPI · PostgreSQL · Redis</text>'
        f'{arrow(TW - 36, TH - 36, 18, INK, BG_CANVAS, D + 0.4)}'
        f'</g>'
    )
    return svg(TW, TH, body, ("in4", "in6", "m5", "pjs", "s6"),
               "Projects", f"{n} public repositories on GitHub.")


def tile_sims() -> str:
    D = 0.05
    rows = ["JPMorgan Chase", "Datacom", "Quantium"]
    items = "".join(
        f'<g{A("rise-sm", D + 0.15 + i * 0.12)}>'
        f'<text x="26" y="{98 + i * 40}" font-size="18.5" font-weight="400" '
        f'fill="{INK}" class="serif">{r}</text>'
        f'</g>'
        for i, r in enumerate(rows)
    )
    body = (
        f'<g{A("pop", D)}>'
        f'<rect width="{TW}" height="{TH}" rx="16" fill="{BG_MUTED}" stroke="{RULE}"/>'
        f'<text x="26" y="44" font-size="11" font-weight="500" fill="{SLATE}" '
        f'class="mono" letter-spacing="1.5">SIMULATIONS</text>'
        f'{items}'
        f'<text x="26" y="218" font-size="11.5" font-weight="400" fill="{SLATE}" '
        f'class="mono">Forage · 2026</text>'
        f'{arrow(TW - 36, TH - 36, 18, INK, BG_CANVAS, D + 0.4)}'
        f'</g>'
    )
    return svg(TW, TH, body, ("bd4", "in4", "m5", "pjs"),
               "Simulations", "Forage job simulations: JPMorgan Chase, Datacom, Quantium.")


def tile_study() -> str:
    D = 0.05
    body = (
        f'<g{A("pop", D)}>'
        f'<rect width="{TW}" height="{TH}" rx="16" fill="{BG_CARD}" stroke="{RULE}"/>'
        f'<text x="26" y="44" font-size="11" font-weight="500" fill="{SLATE}" '
        f'class="mono" letter-spacing="1.5">STUDY</text>'
        f'<text x="24" y="144" font-size="82" font-weight="400" fill="{INK}" '
        f'class="serif" letter-spacing="-2">1–2</text>'
        f'<text x="26" y="172" font-size="15" font-weight="600" fill="{INDIGO}" '
        f'class="pjs">hours a day</text>'
        f'<text x="26" y="196" font-size="12.5" font-weight="400" fill="{SLATE}" '
        f'class="mono">backend systems &</text>'
        f'<text x="26" y="214" font-size="12.5" font-weight="400" fill="{SLATE}" '
        f'class="mono">concurrency</text>'
        f'{arrow(TW - 36, TH - 36, 18, INDIGO, BG_CARD, D + 0.4)}'
        f'</g>'
    )
    return svg(TW, TH, body, ("bd4", "in4", "in6", "m5", "pjs"),
               "Study", "Daily study: backend systems and concurrency.")


# ---------------------------------------------------------------------------
# Card 7, 8, 9: FEATURED REPOSITORY CARDS
# ---------------------------------------------------------------------------
LANG_COL = {
    "Python": "#3572A5", "TypeScript": "#3178C6", "JavaScript": "#F1E05A",
    "Java": "#B07219", "HTML": "#E34C26", "CSS": "#663399",
}


def repo_card(i: int, spec: dict, gh: dict) -> str:
    W, x0 = 1000, 36
    D = 0.05
    name = gh.get("name") or spec["repo"]
    lines = wrap_text(spec["blurb"], 75)
    y = 96
    blurb = "".join(
        f'<text x="{x0}" y="{y + 24 * k}" font-size="15.5" fill="{SLATE}" '
        f'class="pjs">{escape(t)}</text>'
        for k, t in enumerate(lines)
    )
    cy = y + 24 * (len(lines) - 1) + 26
    chips, cx = [], x0
    for tag in spec["tags"]:
        w = len(tag) * 8 + 22
        chips.append(
            f'<rect x="{cx:.0f}" y="{cy}" width="{w:.0f}" height="26" rx="13" '
            f'fill="{BG_MUTED}" stroke="{RULE}" stroke-width=".8"/>'
            f'<text x="{cx + w / 2:.0f}" y="{cy + 17}" text-anchor="middle" '
            f'font-size="11.5" font-weight="500" fill="{SLATE}" class="mono">{escape(tag)}</text>'
        )
        cx += w + 8

    if spec.get("highlight"):
        hw = len(spec["highlight"]) * 7.5 + 26
        if cx + hw > W - 220:
            cx, cy = x0, cy + 36
        chips.append(
            f'<rect x="{cx:.0f}" y="{cy}" width="{hw:.0f}" height="26" rx="13" '
            f'fill="#FEF3C7" stroke="#FDE68A" stroke-width=".8"/>'
            f'<text x="{cx + hw / 2:.0f}" y="{cy + 17}" text-anchor="middle" '
            f'font-size="11.5" font-weight="500" fill="#92400E" class="mono">{escape(spec["highlight"])}</text>'
        )

    H = cy + 26 + 32
    top = []
    rx2 = W - x0
    if gh.get("language"):
        lang = gh["language"]
        top.append(
            f'<text x="{rx2}" y="52" text-anchor="end" font-size="12.5" '
            f'font-weight="500" fill="{SLATE}" class="mono">{escape(lang)}</text>'
            f'<circle cx="{rx2 - len(lang) * 7.8 - 14:.0f}" cy="47" r="5" '
            f'fill="{LANG_COL.get(lang, SLATE)}"/>'
        )
        rx2 -= len(lang) * 7.8 + 28
    if gh.get("stars"):
        s = str(gh["stars"])
        top.append(
            f'<text x="{rx2}" y="52" text-anchor="end" font-size="12.5" '
            f'font-weight="500" fill="{SLATE}" class="mono">{s}</text>'
            + star(rx2 - len(s) * 7.5 - 14, 47, 7, AMBER)
        )

    meta = []
    if gh.get("pushed_at"):
        d0 = date.fromisoformat(gh["pushed_at"][:10])
        meta.append(
            f'<text x="{W - x0}" y="{H - 28}" text-anchor="end" '
            f'font-size="11" font-weight="400" fill="{RULE_DARK}" class="mono">'
            f'Updated {fmt_date(d0)}</text>'
        )

    body = (
        f'<g{A("rise-sm", D)}>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" '
        f'fill="{BG_CARD}" stroke="{RULE}"/>'
        f'<text x="{x0}" y="56" font-size="28" font-weight="400" '
        f'fill="{INK}" class="serif" letter-spacing="-.4">{escape(name)}</text>'
        f'{"".join(top)}{blurb}{"".join(chips)}{"".join(meta)}'
        f'</g>'
    )
    return svg(W, H, body, ("bd4", "in4", "m5", "pjs", "s6"),
               f"{name} repository", spec["blurb"])


# ---------------------------------------------------------------------------
# Output & CLI Entry Point
# ---------------------------------------------------------------------------
def slug(repo: str) -> str:
    return repo.lower().replace("_", "-")


def write_preview():
    readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    html = readme.replace("./gifs/", "./").replace("./cards/", "./")
    page = (
        '<!doctype html><meta charset="utf-8">'
        '<title>README preview</title>'
        f'<style>body{{margin:0;background:{BG_CANVAS};color:{INK};font:16px system-ui}}'
        'main{max-width:920px;margin:40px auto;padding:0 20px}img{max-width:100%}'
        'p{margin:0 0 16px}'
        f'@media(prefers-color-scheme:dark){{body{{background:#141210;color:{BG_CANVAS}}}}}'
        '</style>'
        f'<main>{html}</main>'
    )
    (OUT / "index.html").write_text(page, encoding="utf-8")


def main():
    if "--build-fonts" in sys.argv:
        build_fonts()
        return

    days, start, end, repos = load_data()
    st = stats(days, start, end)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()

    n_projects = sum(
        1 for r in repos.values()
        if not r["fork"] and r["name"].lower() != USERNAME.lower()
    ) or len(FEATURED)

    cards = {
        "hero":             hero(),
        "graph":            graph(days, start, end, st),
        "activity":         activity(st),
        "tile-projects":    tile_projects(n_projects),
        "tile-simulations": tile_sims(),
        "tile-study":       tile_study(),
    }
    for i, spec in enumerate(FEATURED):
        cards[f"repo-{slug(spec['repo'])}"] = repo_card(i, spec, repos.get(spec["repo"].lower(), {}))

    for name, markup in cards.items():
        path = OUT / f"{name}.svg"
        path.write_text(markup, encoding="utf-8")
        print(f"  {OUT.name}/{name}.svg  {len(markup) / 1024:.1f} KB")

    if STATIC:
        write_preview()
        print(f"Static preview: open {OUT.name}/index.html")


if __name__ == "__main__":
    main()
