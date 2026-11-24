"""Draw the 1200x630 link-preview card (site/og.png) from the current forecast, so it refreshes with every build."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# The card uses the site's light-mode colours (site/assets/site.css) and its font, IBM Plex Sans, from the copies in
# src/site/fonts (SIL Open Font License 1.1; Pillow cannot read the .woff2 files the pages use).
FONTS = Path(__file__).with_name("fonts")
BG, SURF, BORDER, OFF = "#FAF8F4", "#FFFFFF", "#CFDDEE", "#F1EFEA"
TITLE, HEAD, TEXT, TEXT2, TEXT3 = "#0A1D37", "#1B4978", "#1F2733", "#505B6A", "#667080"
TINT, OCHRE, TEAL, ACCENT, DEM, REP = "#1B4978", "#B8641C", "#0F957D", "#A8551A", "#2F6FC4", "#CF4A40"
NAME = json.loads(Path(__file__).with_name("site.json").read_text(encoding="utf-8"))["name"]
MARK = Path(__file__).with_name("brand") / "mark-512.png"   # the Early Returns mark, light-mode colour (SI-9)
REGULAR, MEDIUM, SEMIBOLD = "IBMPlexSans-Regular.ttf", "IBMPlexSans-Medium.ttf", "IBMPlexSans-SemiBold.ttf"


def font(name, size):
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


def sign(im, d, right=1140, base=598):
    """The mark and the site's name, bottom right: every card's signature in place of the bare address."""
    f = font(SEMIBOLD, 24)
    w = d.textlength(NAME, font=f)
    d.text((right, base), NAME, font=f, fill=HEAD, anchor="rs")
    try:
        with Image.open(MARK) as m:
            m = m.convert("RGBA").resize((36, 36), Image.LANCZOS)
            im.paste(m, (int(right - w - 46), base - 30), m)
    except OSError:
        pass


def q(hist, p):
    c = np.cumsum(hist) / np.sum(hist)
    return int(np.searchsorted(c, p))


def make(models, out_path, updated, final=False):
    F, A, PO = models["polls_fundamentals"], models["polls_fundamentals_biasadj"], models["polls_only"]
    im = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 8], fill=ACCENT)
    d.text((60, 44), "2026 Midterm Forecast", font=font(SEMIBOLD, 46), fill=TITLE)
    d.text((60, 104), (f"Final pre-election forecast · {updated}" if final else f"Polls + estimated fundamentals · updated {updated}"),
           font=font(REGULAR, 22), fill=ACCENT if final else TEXT3)

    def card(x, title, pF, pA, hF, hA, thr, pP, hP):
        d.rounded_rectangle([x, 160, x + 520, 560], radius=10, fill=SURF, outline=BORDER, width=2)
        d.text((x + 28, 184), title, font=font(SEMIBOLD, 22), fill=HEAD)
        lo, hi = min(round(100 * v) for v in (pA, pF, pP)), max(round(100 * v) for v in (pA, pF, pP))
        d.text((x + 26, 214), f"{lo}–{hi}%", font=font(SEMIBOLD, 78), fill=TITLE)
        d.text((x + 28, 314), "chance Democrats win", font=font(REGULAR, 24), fill=TEXT2)
        meds = [q(h, .5) for h in (hF, hA, hP)]
        r = [min(q(h, .025) for h in (hF, hA, hP)), max(q(h, .975) for h in (hF, hA, hP))]
        seats = f"{min(meds)}–{max(meds)}" if min(meds) != max(meds) else f"{meds[0]}"
        d.text((x + 28, 362), f"Dem seats: {seats}", font=font(SEMIBOLD, 28), fill=TEXT)
        d.text((x + 28, 400), f"95% range {r[0]}–{r[1]} · {thr} for control", font=font(REGULAR, 20), fill=TEXT3)
        for i, (lab, p, col) in enumerate([("Polls only", pP, TEAL), ("Polls + fund.", pF, TINT), ("Bias-adjusted", pA, OCHRE)]):
            y = 440 + i * 36
            d.rectangle([x + 28, y + 12, x + 44, y + 16], fill=col)
            d.text((x + 52, y), lab, font=font(REGULAR, 21), fill=TEXT2)
            bx, bw = x + 200, 210
            d.rounded_rectangle([bx, y + 6, bx + bw, y + 22], radius=6, fill=REP)
            d.rounded_rectangle([bx, y + 6, bx + int(bw * p), y + 22], radius=6, fill=DEM)
            d.text((bx + bw + 14, y - 1), f"{round(100 * p)}%", font=font(SEMIBOLD, 22), fill=TEXT)

    card(60, "House", F["house"]["p_dem_majority"], A["house"]["p_dem_majority"], F["house"]["hist"], A["house"]["hist"], 218,
         PO["house"]["p_dem_majority"], PO["house"]["hist"])
    card(620, "Senate", F["senate"]["p_dem_control_without_osborn"], A["senate"]["p_dem_control_without_osborn"],
         F["senate"]["hist"], A["senate"]["hist"], 51, PO["senate"]["p_dem_control_without_osborn"], PO["senate"]["hist"])
    d.text((60, 584), "Three versions: polls only · polls + fundamentals · bias-adjusted", font=font(REGULAR, 20), fill=TEXT3)
    sign(im, d)
    im.save(out_path, optimize=True)


# The landing page's and the coming cycles' cards (landing.py). They are drawn from site.json alone and carry no numbers
# and no date. A card is rewritten only when its pixels change, so a machine whose PNG compressor writes different bytes
# (the scorecard job runs on Linux) leaves the committed files alone.

def save(im, path):
    try:
        with Image.open(path) as old:
            if old.convert("RGB").tobytes() == im.tobytes():
                return
    except (OSError, ValueError):
        pass
    im.save(path, optimize=True)


def wrap(d, text, f, width):
    lines, line = [], ""
    for w in text.split():
        t = f"{line} {w}".strip()
        if d.textlength(t, font=f) > width and line:
            lines.append(line)
            line = w
        else:
            line = t
    return lines + [line] if line else lines


def _base(title, sub):
    im = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 8], fill=ACCENT)
    d.text((60, 52), title, font=font(SEMIBOLD, 64), fill=TITLE)
    y = 140
    for ln in wrap(d, sub, font(REGULAR, 28), 1080):
        d.text((60, y), ln, font=font(REGULAR, 28), fill=TEXT2)
        y += 40
    return im, d, y


def make_home(S, out_path):
    im, d, y = _base(S["name"], S["intro"])
    y = max(y + 30, 300)
    for i, (k, t) in enumerate([(S["featured"]["label"], S["featured"]["title"]),
                                ("Coming", S["og_home_coming"])]):
        d.rounded_rectangle([60, y, 1140, y + 96], radius=10, fill=SURF, outline=BORDER, width=2)
        d.text((88, y + 16), k.upper(), font=font(SEMIBOLD, 18), fill=ACCENT)
        d.text((88, y + 44), t, font=font(MEDIUM, 28), fill=HEAD)
        y += 116
    sign(im, d)
    save(im, out_path)


def make_preview(S, key, out_path, board=None):
    """A coming cycle's card: its title, line and dates. With `board` (landing.board_data(), 2028 before the
    nominees) the dates take the left side and the board the right: grey tiles, each with its electoral votes and
    seven bars for 2000 to 2024, as on the page."""
    P = S["previews"][key]
    im, d, y = _base(P["title"], P["image_line"])
    dates = [x for x in P["dates"] if x["when"] != "Through 2027"]
    y = max(y + 24, 250)
    text_x, text_w = (300, 840) if board is None else (262, 320)
    fs = 24 if board is None else 20
    for x in dates:
        for i, ln in enumerate(wrap(d, x["text"], font(REGULAR, fs), text_w)):
            if i == 0:
                d.text((60, y), x["when"], font=font(SEMIBOLD, fs), fill=ACCENT if x.get("target") else HEAD)
            d.text((text_x, y), ln, font=font(REGULAR, fs), fill=TEXT)
            y += 36 if board is None else 28
        y += 8 if board is None else 4
    if board:
        U, T, x0, y0 = 37, 34, 660, 236
        for k, c, r, ev, won in board:
            x, yy = round(x0 + c * U), round(y0 + (8.3 if r == 9 else r) * U)   # districts just under the grid
            d.rounded_rectangle([x, yy, x + T, yy + T], radius=4, fill=OFF, outline=BORDER, width=1)
            d.text((x + T / 2, yy + 3), k, font=font(MEDIUM, 9), fill=TEXT3, anchor="mt")
            d.text((x + T / 2, yy + 12), str(ev), font=font(SEMIBOLD, 14), fill=TEXT, anchor="mt")
            for i, yr in enumerate(sorted(won)):     # seven 3-pixel bars with 1-pixel gaps, centred
                bx = x + (T - 27) // 2 + i * 4
                d.rectangle([bx, yy + T - 8, bx + 2, yy + T - 4], fill=DEM if won[yr] == "D" else REP)
    sign(im, d)
    save(im, out_path)
