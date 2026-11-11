#!/usr/bin/env python3
"""Render the animated SVG cards for the GitHub profile README.

    python scripts/render_readme_cards.py                 # writes cards/*.svg
    STATIC=1 python scripts/render_readme_cards.py        # writes preview/ (final frame, no motion)
    python scripts/render_readme_cards.py --build-fonts   # one-off: download, subset and embed-ready fonts

Cards are shown through <img> tags, so each SVG is fully self-contained: an inline
<style> block (CSS keyframes), SMIL <animate>/<set>, and fonts embedded as base64
WOFF data URIs. Nothing is fetched at view time.

Reads:  data/contributions.json, data/repos.json   (refreshed daily by the Action)
        fonts/*.woff                               (made once by --build-fonts)
        assets/portrait.jpg                        (optional)
"""
from __future__ import annotations

import base64
import io
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

# ----------------------------------------------------------------------------
# Content: edit this block, then re-run the script.
# ----------------------------------------------------------------------------
USERNAME = "deoreparth700-design"
NAME = "Parth Deore"
ROLE = "Backend developer"
TAGLINE = ("Final-year CS student who designs the schema and API contract first, "
           "then builds FastAPI and PostgreSQL backends on top of it.")
STATUS = "Open to internships and backend roles"
LOCATION = "Chh. Sambhaji Nagar, India (GMT+5:30)"
SITE = "https://parthdeore.vercel.app/"
REPOS_TAB = f"https://github.com/{USERNAME}?tab=repositories"

# Featured repos, one card each. `repo` must match the GitHub repo name.
# Stars, language and last-push date come from data/repos.json when present.
FEATURED = [
    dict(repo="Cart-API",
         blurb="E-commerce cart backend with real-time inventory, atomic PostgreSQL "
               "transactions and Razorpay payments verified by HMAC webhooks.",
         tags=["FastAPI", "PostgreSQL", "JWT", "Razorpay", "SQLAlchemy"]),
    dict(repo="auth-service",
         blurb="Authentication API with JWT access and refresh token rotation, bcrypt "
               "hashing, sliding session expiry and rate limiting.",
         tags=["FastAPI", "PostgreSQL", "JWT", "Bcrypt", "Render"]),
    dict(repo="blog-platform-api",
         blurb="Article publishing API with Redis response caching, Neon PostgreSQL, "
               "JWT auth and automated Pytest coverage.",
         tags=["FastAPI", "PostgreSQL", "Redis", "Pytest", "Render"],
         highlight="16.9x faster on a warm cache (local benchmark)"),
]

# Palette and fonts come from the portfolio site.
INK, PAPER, CARD, LINE = "#1E1B2E", "#F8F5FF", "#FDFCFF", "#E8E3F6"
MUTE, VIOLET, AMBER = "#625C7C", "#7C3AED", "#F59E0B"
LAV, LAV2, DEEP = "#DCD0F8", "#EEE8FB", "#5B21B6"

# Animation timeline (seconds): the page plays top to bottom.
T = dict(hero=0.0, graph=1.0, activity=1.7, tile=2.5, repo=3.4)

# ----------------------------------------------------------------------------
# Fonts: subset with fontTools (the engine behind pyftsubset), embedded as WOFF.
# ----------------------------------------------------------------------------
FONTS = {
    "s4": ("Plus Jakarta Sans", 400, "sans-400.woff"),
    "s6": ("Plus Jakarta Sans", 600, "sans-600.woff"),
    "s8": ("Plus Jakarta Sans", 800, "sans-800.woff"),
    "m5": ("JetBrains Mono", 500, "mono-500.woff"),
}
FONT_URLS = {
    "sans": "https://github.com/google/fonts/raw/main/ofl/plusjakartasans/PlusJakartaSans%5Bwght%5D.ttf",
    "mono": "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}
KEEP = (list(range(0x20, 0x7F)) +
        [0xA0, 0xB7, 0xD7, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026])


def build_fonts(sans_path: str | None = None, mono_path: str | None = None) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    FONT_DIR.mkdir(exist_ok=True)
    src = {}
    for kind, given in (("sans", sans_path), ("mono", mono_path)):
        if given:
            src[kind] = given
        else:
            tmp = FONT_DIR / f"_{kind}.ttf"
            req = urllib.request.Request(FONT_URLS[kind], headers={"User-Agent": "readme-cards"})
            tmp.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            src[kind] = str(tmp)
    for key, (family, weight, fname) in FONTS.items():
        font = TTFont(src["mono" if key.startswith("m") else "sans"])
        if "fvar" in font:
            font = instancer.instantiateVariableFont(font, {"wght": weight})
        opts = subset.Options()
        opts.flavor = "woff"
        opts.hinting = False
        opts.layout_features = ["kern", "liga"]
        opts.name_IDs = [1, 2]
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=KEEP)
        sub.subset(font)
        font.flavor = "woff"
        font.save(FONT_DIR / fname)
        print(f"  fonts/{fname}  {(FONT_DIR / fname).stat().st_size / 1024:.1f} KB  ({family} {weight})")
    for tmp in FONT_DIR.glob("_*.ttf"):
        tmp.unlink()


_metrics: dict = {}


def tw(text: str, key: str, size: float, ls: float = 0.0) -> float:
    """Rendered width of `text`, read from the embedded font's own advance widths."""
    if key not in _metrics:
        from fontTools.ttLib import TTFont
        path = FONT_DIR / FONTS[key][2]
        if not path.exists():
            sys.exit(f"Missing {path}. Run: python scripts/render_readme_cards.py --build-fonts")
        f = TTFont(path)
        _metrics[key] = (f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm)
    cmap, hmtx, upm = _metrics[key]
    total = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upm * 0.55 for c in text)
    return total * size / upm + ls * len(text)


def wrap(text: str, key: str, size: float, maxw: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and tw(trial, key, size) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def font_css(keys) -> str:
    out = []
    for k in keys:
        family, weight, fname = FONTS[k]
        path = FONT_DIR / fname
        if not path.exists():
            sys.exit(f"Missing {path}. Run: python scripts/render_readme_cards.py --build-fonts")
        b64 = base64.b64encode(path.read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{family}';font-weight:{weight};"
                   f"src:url(data:font/woff;base64,{b64}) format('woff')}}")
    return "".join(out)


# ----------------------------------------------------------------------------
# SVG plumbing
# ----------------------------------------------------------------------------
BASE_CSS = ("text{font-family:'Plus Jakarta Sans','Segoe UI',system-ui,sans-serif;"
            "text-rendering:geometricPrecision}"
            ".m{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace}")

ANIM_CSS = """
.rise{animation:rise .8s cubic-bezier(.2,.8,.2,1) var(--d,0s) both}
.slide{animation:slide .9s cubic-bezier(.2,.8,.2,1) var(--d,0s) both}
.col{animation:colin .5s ease-out var(--d,0s) both}
.grow{transform-box:fill-box;transform-origin:50% 100%;animation:grow .8s cubic-bezier(.2,.8,.2,1) var(--d,0s) both}
.pop{transform-box:fill-box;transform-origin:50% 50%;animation:pop .6s cubic-bezier(.3,1.5,.5,1) var(--d,0s) both}
.swing{transform-box:fill-box;transform-origin:50% 100%;animation:swing 1.1s cubic-bezier(.2,.9,.3,1.15) var(--d,0s) both}
.blink{animation:blink 2.4s ease-in-out var(--d,0s) infinite}
.ring{transform-box:fill-box;transform-origin:50% 50%;animation:ring 3s ease-out var(--d,0s) infinite}
.nudge{animation:nudge 1.9s ease-in-out var(--d,0s) infinite}
.sweep{transform:translateX(-160px) skewX(-20deg);animation:sweep 7s ease-in-out var(--d,0s) infinite}
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes slide{from{opacity:0;transform:translateX(-32px)}to{opacity:1;transform:none}}
@keyframes colin{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes pop{0%{opacity:0;transform:scale(.3)}70%{opacity:1;transform:scale(1.2)}100%{opacity:1;transform:scale(1)}}
@keyframes swing{0%{opacity:0;transform:translateY(46px) rotate(-5deg)}55%{opacity:1;transform:translateY(-8px) rotate(1.2deg)}100%{opacity:1;transform:none}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes ring{0%{opacity:.6;transform:scale(.55)}100%{opacity:0;transform:scale(1.7)}}
@keyframes nudge{0%,100%{transform:translateX(0)}50%{transform:translateX(4px)}}
@keyframes sweep{0%{transform:translateX(-160px) skewX(-20deg)}22%,100%{transform:translateX(480px) skewX(-20deg)}}
.still{display:none}
@media (prefers-reduced-motion:reduce){
*{animation:none!important}
.live{display:none}
.still{display:inline}
}
"""


def A(cls: str, delay: float, base: str = "") -> str:
    """Class + delay attributes for an animated element; only `base` in STATIC mode."""
    if STATIC:
        return f' class="{base}"' if base else ""
    return f' class="{(base + " " + cls).strip()}" style="--d:{delay:.2f}s"'


def dual(live: str, still: str) -> str:
    """SMIL ignores CSS media queries, so SMIL content ships as a live copy and a
    still copy; prefers-reduced-motion swaps them. STATIC mode keeps only the still."""
    return still if STATIC else f'<g class="live">{live}</g><g class="still">{still}</g>'


def svg(w, h, body, fonts, title, desc, defs=""):
    css = font_css(fonts) + BASE_CSS + ("" if STATIC else ANIM_CSS)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>'
            f'<desc>{escape(desc)}</desc><style>{css}</style><defs>{defs}</defs>{body}</svg>')


def mix(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def arrow(cx, cy, r, bg, fg, delay):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{bg}"/>'
            f'<g{A("nudge", delay)}><path d="M{cx - 7} {cy}H{cx + 7}M{cx + 1.5} {cy - 6}L{cx + 7.5} {cy}L{cx + 1.5} {cy + 6}" '
            f'fill="none" stroke="{fg}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></g>')


def star(cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append(f"{cx + rad * math.cos(ang):.1f},{cy + rad * math.sin(ang):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


def fmt_date(d: date) -> str:
    return f"{d.day} {d.strftime('%b')} {d.year}"


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_data():
    cpath, rpath = DATA_DIR / "contributions.json", DATA_DIR / "repos.json"
    if not cpath.exists():
        sys.exit("data/contributions.json is missing. Run scripts/fetch_data.py first "
                 "(needs GH_TOKEN), or trigger the Action once.")
    raw = json.loads(cpath.read_text())
    days = {date.fromisoformat(d): int(c) for d, c in raw["days"]}
    end = date.fromisoformat(raw["end"])
    start = end - timedelta(days=364)
    full = {start + timedelta(days=i): days.get(start + timedelta(days=i), 0) for i in range(365)}
    repos = {}
    if rpath.exists():
        repos = {r["name"].lower(): r for r in json.loads(rpath.read_text())["repos"]}
    return full, start, end, repos


def stats(days, start, end):
    d = end if days[end] > 0 else end - timedelta(days=1)  # today may still be pending
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


# ----------------------------------------------------------------------------
# Card: hero
# ----------------------------------------------------------------------------
def portrait_b64():
    for name in ("portrait.jpg", "portrait.jpeg", "portrait.png"):
        p = ROOT / "assets" / name
        if p.exists():
            from PIL import Image
            im = Image.open(p).convert("RGB")
            s = min(im.size)
            im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                          (im.width + s) // 2, (im.height + s) // 2)).resize((280, 280))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82, optimize=True)
            return base64.b64encode(buf.getvalue()).decode()
    return None


def hero():
    x0, tagw = 56, 590
    D = T["hero"]
    pill_w = 18 + 8 + 10 + tw(STATUS, "s6", 14) + 20
    lines = wrap(TAGLINE, "s4", 18, tagw)
    y_name, y_role, y_tag = 168, 212, 252
    y_loc = y_tag + 27 * (len(lines) - 1) + 40
    H = y_loc + 34
    cx, cy, r = 832, H // 2 + 4, 104

    b64 = portrait_b64()
    if b64:
        face = (f'<clipPath id="pc"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>'
                f'<image href="data:image/jpeg;base64,{b64}" x="{cx - r}" y="{cy - r}" width="{2 * r}" '
                f'height="{2 * r}" clip-path="url(#pc)" preserveAspectRatio="xMidYMid slice"/>')
    else:
        initials = "".join(w[0] for w in NAME.split()[:2])
        face = (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#mono)"/>'
                f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" font-size="72" font-weight="800" '
                f'fill="#fff">{escape(initials)}</text>')
    defs = (f'<radialGradient id="g1" cx="85%" cy="0%" r="60%"><stop offset="0" stop-color="{AMBER}" stop-opacity=".28"/>'
            f'<stop offset="1" stop-color="{AMBER}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="g2" cx="0%" cy="100%" r="55%"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".18"/>'
            f'<stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="mono" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{VIOLET}"/>'
            f'<stop offset="1" stop-color="{DEEP}"/></linearGradient>')
    if not STATIC:
        defs += (f'<linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0">'
                 f'<stop offset="0" stop-color="{INK}"/><stop offset=".40" stop-color="{INK}"/>'
                 f'<stop offset=".5" stop-color="{VIOLET}"/><stop offset=".60" stop-color="{INK}"/>'
                 f'<stop offset="1" stop-color="{INK}"/>'
                 f'<animateTransform attributeName="gradientTransform" type="translate" '
                 f'values="-1 0;1 0;1 0" keyTimes="0;.3;1" dur="7s" begin="{D + 1.6:.1f}s" repeatCount="indefinite"/>'
                 f'</linearGradient>')
    name_attrs = f'x="{x0}" y="{y_name}" font-size="86" font-weight="800" letter-spacing="-2.5"'
    name = dual(f'<text {name_attrs} fill="url(#sheen)">{escape(NAME)}</text>',
                f'<text {name_attrs} fill="{INK}">{escape(NAME)}</text>')
    tag = "".join(f'<text x="{x0}" y="{y_tag + 27 * i}" font-size="18" fill="{MUTE}">{escape(t)}</text>'
                  for i, t in enumerate(lines))
    body = (
        f'<rect x=".5" y=".5" width="999" height="{H - 1}" rx="32" fill="{PAPER}" stroke="{LINE}"/>'
        f'<rect width="1000" height="{H}" rx="32" fill="url(#g1)"/><rect width="1000" height="{H}" rx="32" fill="url(#g2)"/>'
        f'<g{A("rise", D + .1)}><rect x="{x0}" y="40" width="{pill_w:.0f}" height="36" rx="18" fill="#fff" stroke="{LINE}"/>'
        f'<circle{A("blink", D + 1)} cx="{x0 + 22}" cy="58" r="4.5" fill="{AMBER}"/>'
        f'<text x="{x0 + 40}" y="63" font-size="14" font-weight="600" fill="{INK}">{escape(STATUS)}</text></g>'
        f'<g{A("rise", D + .25)}>{name}</g>'
        f'<g{A("rise", D + .45)}><text x="{x0}" y="{y_role}" font-size="26" font-weight="600" fill="{VIOLET}">{escape(ROLE)}</text></g>'
        f'<g{A("rise", D + .6)}>{tag}</g>'
        f'<g{A("rise", D + .8)}><text class="m" x="{x0}" y="{y_loc}" font-size="13" font-weight="500" fill="{MUTE}">{escape(LOCATION)}</text></g>'
        f'<circle cx="{cx}" cy="{cy}" r="{r + 14}" fill="none" stroke="{VIOLET}" stroke-width="2" opacity=".25"{A("ring", D + 1.2)}/>'
        f'<g{A("pop", D + .5)}><circle cx="{cx}" cy="{cy}" r="{r + 7}" fill="{AMBER}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r + 2}" fill="{PAPER}"/>{face}</g>'
    )
    return svg(1000, H, body, ("s6", "s8", "s4", "m5"), f"{NAME}, {ROLE}", TAGLINE, defs)


# ----------------------------------------------------------------------------
# Card: contribution graph (brand colour)
# ----------------------------------------------------------------------------
LEVELS = [mix("#E7DFF9", VIOLET, t) for t in (0, .25, .5, .75, 1)]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def graph(days, start, end, st):
    W, x0, y0 = 1000, 66, 100
    D = T["graph"]
    first = start - timedelta(days=(start.weekday() + 1) % 7)  # the Sunday on or before start
    cols = (end - first).days // 7 + 1
    pitch = (W - x0 - 34) / cols
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
            cells.append(f'<rect x="{x0 + c * pitch:.1f}" y="{y0 + r * pitch:.1f}" width="{cell:.1f}" height="{cell:.1f}" '
                         f'rx="3.2" fill="{LEVELS[level(days[d])]}"/>')
        parts.append(f'<g{A("col", D + .25 + c * .02)}>{"".join(cells)}</g>')
    if not labelled or labelled[0][0] >= 3:
        labelled.insert(0, (0, MON[start.month - 1]))
    months = "".join(f'<text class="m" x="{x0 + c * pitch:.1f}" y="88" font-size="12" font-weight="500" fill="{MUTE}">{m}</text>'
                     for c, m in labelled)
    dows = "".join(f'<text class="m" x="32" y="{y0 + r * pitch + cell - 2:.1f}" font-size="11" font-weight="500" fill="{MUTE}">{n}</text>'
                   for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")))
    H = round(y0 + 7 * pitch + 50)
    lx = W - 34 - 5 * 17 - tw("More", "s6", 13) - 10
    legend = (f'<text x="{lx - tw("Less", "s6", 13) - 10:.0f}" y="{H - 22}" font-size="13" font-weight="600" fill="{MUTE}">Less</text>'
              + "".join(f'<rect x="{lx + i * 17}" y="{H - 33}" width="12" height="12" rx="3" fill="{LEVELS[i]}"/>' for i in range(5))
              + f'<text x="{lx + 5 * 17 + 4}" y="{H - 22}" font-size="13" font-weight="600" fill="{MUTE}">More</text>')
    body = (f'<rect x=".5" y=".5" width="999" height="{H - 1}" rx="28" fill="{CARD}" stroke="{LINE}"/>'
            f'<g{A("rise", D)}><text x="32" y="50" font-size="22" font-weight="800" fill="{INK}">'
            f'{st["total"]:,} contributions in the last year</text></g>'
            f'<g{A("rise", D + .1)}>{months}{dows}</g>{"".join(parts)}<g{A("rise", D + 1.2)}>{legend}</g>')
    return svg(W, H, body, ("s4", "s6", "s8", "m5"), "Contribution graph",
               f"{st['total']} contributions in the last year, shown as a calendar heatmap.")


# ----------------------------------------------------------------------------
# Card: contributions per month + streak, active days, busiest day
# ----------------------------------------------------------------------------
def activity(st):
    W, H = 1000, 340
    D = T["activity"]
    base_y, top_y = 270, 112
    xl, xr = 40, 650
    slot = (xr - xl) / 12
    bw = 30
    pm = st["per_month"]
    vmax = max(pm) or 1
    best = max(range(12), key=lambda i: (pm[i], i))
    bars, labels = [], []
    for i, v in enumerate(pm):
        h = max(5, (base_y - top_y) * v / vmax)
        x = xl + i * slot + (slot - bw) / 2
        is_best = i == best
        bars.append(f'<rect{A("grow", D + .3 + i * .06)} x="{x:.1f}" y="{base_y - h:.1f}" width="{bw}" height="{h:.1f}" rx="9" '
                    f'fill="{VIOLET if is_best else LAV}"/>')
        if is_best:
            labels.append(f'<text{A("pop", D + .3 + 12 * .06 + .4)} x="{x + bw / 2:.1f}" y="{base_y - h - 12:.1f}" text-anchor="middle" '
                          f'font-size="20" font-weight="800" fill="{VIOLET}">{v}</text>')
        else:
            labels.append(f'<text{A("rise", D + .3 + i * .06 + .5, "m")} x="{x + bw / 2:.1f}" y="{base_y - h - 9:.1f}" '
                          f'text-anchor="middle" font-size="12" font-weight="500" fill="{MUTE}">{v}</text>')
        labels.append(f'<text x="{x + bw / 2:.1f}" y="{base_y + 26}" text-anchor="middle" font-size="13" font-weight="600" '
                      f'fill="{INK if is_best else MUTE}">{MON[st["months"][i][1] - 1]}</text>')

    def block(i, label, big, unit, sub):
        top = 28 + i * 100
        d = D + .5 + i * .2
        u = f'<text x="{690 + tw(big, "s8", 44) + 8:.0f}" y="{top + 66}" font-size="20" font-weight="600" fill="{MUTE}">{unit}</text>' if unit else ""
        return (f'<g{A("rise", d)}><text x="690" y="{top + 26}" font-size="14" font-weight="600" fill="{MUTE}">{label}</text>'
                f'<text x="690" y="{top + 66}" font-size="44" font-weight="800" fill="{INK}">{big}</text>{u}'
                f'<text class="m" x="690" y="{top + 88}" font-size="13" font-weight="500" fill="{MUTE}">{sub}</text></g>')

    bday, bcount = st["busiest"]
    cur = st["current"]
    stats_svg = (
        block(0, "Current streak", str(cur), "day" if cur == 1 else "days", f"Longest this year: {st['longest']}")
        + f'<line x1="690" y1="131" x2="968" y2="131" stroke="{LINE}"/>'
        + block(1, "Active days", str(st["active"]), "", "out of the last 365 days")
        + f'<line x1="690" y1="231" x2="968" y2="231" stroke="{LINE}"/>'
        + block(2, "Busiest day", str(bcount), "contributions" if bcount != 1 else "contribution", fmt_date(bday)))
    body = (f'<rect x=".5" y=".5" width="999" height="{H - 1}" rx="28" fill="{CARD}" stroke="{LINE}"/>'
            f'<g{A("rise", D)}><text x="40" y="52" font-size="22" font-weight="800" fill="{INK}">Contributions per month</text>'
            f'<text x="40" y="76" font-size="14" font-weight="400" fill="{MUTE}">The last 12 months, best month in violet</text></g>'
            f'<line x1="{xl}" y1="{base_y}" x2="{xr}" y2="{base_y}" stroke="{LINE}" stroke-width="2"/>'
            f'<line x1="668" y1="40" x2="668" y2="{H - 40}" stroke="{LINE}"/>'
            f'{"".join(bars)}{"".join(labels)}{stats_svg}')
    return svg(W, H, body, ("s4", "s6", "s8", "m5"), "Contributions per month",
               f"Monthly contributions for the last 12 months. Current streak {cur} days, "
               f"{st['active']} active days, busiest day {fmt_date(bday)} with {bcount}.")


# ----------------------------------------------------------------------------
# Cards: three linked tiles
# ----------------------------------------------------------------------------
TW, TH = 330, 250


def tile_shell(idx, bg, inner, title, desc, fonts, ring_color, sweep_color="#fff"):
    d = T["tile"] + idx * .18
    clip = f'<clipPath id="tc"><rect width="{TW}" height="{TH}" rx="30"/></clipPath>'
    sweep = "" if STATIC else (f'<g clip-path="url(#tc)"><rect{A("sweep", d + 1.6)} x="0" y="-20" width="70" height="{TH + 40}" '
                               f'fill="{sweep_color}" opacity=".16"/></g>')
    body = (f'<g{A("swing", d)}><rect width="{TW}" height="{TH}" rx="30" fill="{bg}"/>'
            f'<circle{A("ring", d + 1)} cx="{TW - 40}" cy="46" r="26" fill="none" stroke="{ring_color}" stroke-width="2" opacity=".3"/>'
            f'{sweep}{inner}</g>')
    return svg(TW, TH, body, fonts, title, desc, clip)


def count_up(value, x, y, size, fill, start):
    """Numbers can't tween in an SVG <img> (CSS can't change text), so the live copy is a
    run of <text> frames that SMIL switches on one after another."""
    n = min(value, 14)
    seq = []
    for i in range(n + 1):
        t = i / n if n else 1
        v = round(value * (1 - (1 - t) ** 3))
        if not seq or v != seq[-1]:
            seq.append(v)
    seq[-1] = value
    step = .055
    frames = []
    for i, v in enumerate(seq):
        last = i == len(seq) - 1
        timing = 'fill="freeze"' if last else f'dur="{step}s"'
        frames.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="800" fill="{fill}" visibility="hidden" letter-spacing="-3">{v}'
                      f'<set attributeName="visibility" to="visible" begin="{start + i * step:.2f}s" {timing}/></text>')
    still = f'<text x="{x}" y="{y}" font-size="{size}" font-weight="800" fill="{fill}" letter-spacing="-3">{value}</text>'
    return dual("".join(frames), still)


def tile_projects(n):
    d = T["tile"] + .5
    inner = (f'<text x="28" y="50" font-size="18" font-weight="600" fill="#fff" opacity=".92">Projects</text>'
             f'{count_up(n, 26, 152, 104, "#fff", d + .35)}'
             f'<text x="28" y="188" font-size="17" font-weight="600" fill="#fff">public repositories</text>'
             f'<text x="28" y="214" font-size="15" font-weight="400" fill="#fff" opacity=".88">FastAPI, PostgreSQL, Redis</text>'
             f'{arrow(282, 202, 22, "#fff", VIOLET, d + 1)}')
    return tile_shell(0, VIOLET, inner, "Projects", f"{n} public repositories. Opens my GitHub repositories.",
                      ("s4", "s6", "s8"), "#fff")


def tile_sims():
    d = T["tile"] + .18 + .5
    rows = ["JPMorgan Chase", "Datacom", "Quantium"]
    items = "".join(
        f'<g{A("rise", d + i * .18)}><circle cx="41" cy="{100 + i * 40}" r="11" fill="{INK}"/>'
        f'<path d="M36 {100 + i * 40}l3.6 3.8 6.6-7.6" fill="none" stroke="{AMBER}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<text x="64" y="{107 + i * 40}" font-size="21" font-weight="600" fill="{INK}">{r}</text></g>'
        for i, r in enumerate(rows))
    inner = (f'<text x="28" y="50" font-size="18" font-weight="600" fill="{INK}">Simulations</text>{items}'
             f'<text x="28" y="226" font-size="14" font-weight="400" fill="{INK}" opacity=".78">Forage job simulations, 2026</text>'
             f'{arrow(282, 202, 22, INK, AMBER, d + 1)}')
    return tile_shell(1, AMBER, inner, "Simulations",
                      "Three Forage job simulations completed in 2026: JPMorgan Chase, Datacom and Quantium.",
                      ("s4", "s6"), INK, "#fff")


def tile_study():
    d = T["tile"] + .36 + .5
    big, unit, usize = "1\u20132", "hours a day", 22
    size = 104
    while tw(big, "s8", size, -1) + 12 + tw(unit, "s6", usize) > TW - 28 - 24:
        size -= 4
    lines = wrap("Backend systems and concurrency", "s4", 17, 200)
    txt = "".join(f'<text x="28" y="{190 + 24 * i}" font-size="17" font-weight="400" fill="{LAV}">{escape(t)}</text>'
                  for i, t in enumerate(lines))
    inner = (f'<text x="28" y="50" font-size="18" font-weight="600" fill="{LAV}">Study</text>'
             f'<g{A("rise", d)}><text x="26" y="152" font-size="{size}" font-weight="800" fill="{AMBER}" letter-spacing="-1">{big}</text>'
             f'<text x="{26 + tw(big, "s8", size, -1) + 12:.0f}" y="152" font-size="{usize}" font-weight="600" fill="{LAV}">{unit}</text></g>'
             f'<g{A("rise", d + .2)}>{txt}</g>{arrow(282, 202, 22, AMBER, INK, d + 1)}')
    return tile_shell(2, INK, inner, "Study", "One to two hours of backend study every day, on systems and concurrency.",
                      ("s4", "s6", "s8"), AMBER, "#fff")


# ----------------------------------------------------------------------------
# Cards: one per featured repo
# ----------------------------------------------------------------------------
LANG = {"Python": "#3572A5", "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "Java": "#B07219",
        "HTML": "#E34C26", "C#": "#178600", "CSS": "#663399"}


def repo_card(i, spec, gh):
    W, x0 = 1000, 36
    D = T["repo"] + i * .2
    name = gh.get("name") or spec["repo"]
    lines = wrap(spec["blurb"], "s4", 17, W - 2 * x0 - 20)
    y = 100
    blurb = "".join(f'<text x="{x0}" y="{y + 26 * k}" font-size="17" fill="{MUTE}">{escape(t)}</text>' for k, t in enumerate(lines))
    cy = y + 26 * (len(lines) - 1) + 24
    chips, cx = [], x0
    for tag in spec["tags"]:
        w = tw(tag, "m5", 12.5) + 24
        chips.append(f'<rect x="{cx:.0f}" y="{cy}" width="{w:.0f}" height="30" rx="15" fill="{LAV2}"/>'
                     f'<text class="m" x="{cx + w / 2:.0f}" y="{cy + 20}" text-anchor="middle" font-size="12.5" font-weight="500" fill="{DEEP}">{escape(tag)}</text>')
        cx += w + 8
    if spec.get("highlight"):
        hw = tw(spec["highlight"], "s6", 13) + 28
        if cx + hw > W - 240:
            cx, cy = x0, cy + 40
        chips.append(f'<rect x="{cx:.0f}" y="{cy}" width="{hw:.0f}" height="30" rx="15" fill="#FEF3C7"/>'
                     f'<text x="{cx + hw / 2:.0f}" y="{cy + 20}" text-anchor="middle" font-size="13" font-weight="600" fill="#92400E">{escape(spec["highlight"])}</text>')
    H = cy + 30 + 32
    meta, rx = [], W - x0
    if gh.get("pushed_at"):
        d0 = date.fromisoformat(gh["pushed_at"][:10])
        t = f"Updated {fmt_date(d0)}"
        meta.append(f'<text class="m" x="{rx}" y="{H - 38 + 20 - 1}" text-anchor="end" font-size="12.5" font-weight="500" fill="{MUTE}">{t}</text>')
    top, rx2 = [], W - x0
    if gh.get("language"):
        lang = gh["language"]
        top.append(f'<text x="{rx2}" y="55" text-anchor="end" font-size="15" font-weight="600" fill="{INK}">{escape(lang)}</text>'
                   f'<circle cx="{rx2 - tw(lang, "s6", 15) - 14:.0f}" cy="50" r="6" fill="{LANG.get(lang, MUTE)}"/>')
        rx2 -= tw(lang, "s6", 15) + 14 + 26
    if gh.get("stars"):
        s = str(gh["stars"])
        top.append(f'<text x="{rx2}" y="55" text-anchor="end" font-size="15" font-weight="600" fill="{INK}">{s}</text>'
                   + star(rx2 - tw(s, "s6", 15) - 16, 49, 8, AMBER))
    body = (f'<g{A("slide", D)}><rect x=".5" y=".5" width="999" height="{H - 1}" rx="26" fill="{CARD}" stroke="{LINE}"/>'
            f'<text x="{x0}" y="58" font-size="30" font-weight="800" fill="{INK}" letter-spacing="-.6">{escape(name)}</text>'
            f'{"".join(top)}{blurb}{"".join(chips)}{"".join(meta)}</g>')
    return svg(W, H, body, ("s4", "s6", "s8", "m5"), f"{name} repository", spec["blurb"])


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------
def slug(repo):
    return repo.lower().replace("_", "-")


def write_preview():
    """STATIC=1 also writes preview/index.html: README.md laid out like GitHub shows it."""
    readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
    html = readme.replace("./cards/", "./")
    page = ("<!doctype html><meta charset=utf-8><title>README preview (final frame)</title>"
            "<style>body{margin:0;background:#fff;color:#1f2328;font:16px system-ui}"
            "main{max-width:888px;margin:32px auto;padding:0 16px}img{max-width:100%}p{margin:0 0 16px}"
            "@media(prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}}</style>"
            f"<main>{html}</main>")
    (OUT / "index.html").write_text(page)


def main():
    if "--build-fonts" in sys.argv:
        args = sys.argv
        build_fonts(args[args.index("--sans") + 1] if "--sans" in args else None,
                    args[args.index("--mono") + 1] if "--mono" in args else None)
        return
    days, start, end, repos = load_data()
    st = stats(days, start, end)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    n_projects = sum(1 for r in repos.values() if not r["fork"] and r["name"].lower() != USERNAME.lower()) or len(FEATURED)
    cards = {"hero": hero(), "graph": graph(days, start, end, st), "activity": activity(st),
             "tile-projects": tile_projects(n_projects), "tile-simulations": tile_sims(), "tile-study": tile_study()}
    for i, spec in enumerate(FEATURED):
        cards[f"repo-{slug(spec['repo'])}"] = repo_card(i, spec, repos.get(spec["repo"].lower(), {}))
    for name, markup in cards.items():
        (OUT / f"{name}.svg").write_text(markup, encoding="utf-8")
        print(f"  {OUT.name}/{name}.svg  {len(markup) / 1024:.1f} KB")
    if STATIC:
        write_preview()
        print(f"Static preview: open {OUT.name}/index.html")


if __name__ == "__main__":
    main()
