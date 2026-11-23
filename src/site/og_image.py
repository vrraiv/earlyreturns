"""Draw the 1200x630 link-preview card (site/og.png) from the current forecast, so it refreshes with every build."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# The card uses the site's light-mode colours (site/assets/site.css) and its font, IBM Plex Sans, from the copies in
# src/site/fonts (SIL Open Font License 1.1; Pillow cannot read the .woff2 files the pages use).
FONTS = Path(__file__).with_name("fonts")
BG, SURF, BORDER = "#FAF8F4", "#FFFFFF", "#CFDDEE"
TITLE, HEAD, TEXT, TEXT2, TEXT3 = "#0A1D37", "#1B4978", "#1F2733", "#505B6A", "#667080"
TINT, OCHRE, TEAL, ACCENT, DEM, REP = "#1B4978", "#B8641C", "#0F957D", "#A8551A", "#2F6FC4", "#CF4A40"
REGULAR, MEDIUM, SEMIBOLD = "IBMPlexSans-Regular.ttf", "IBMPlexSans-Medium.ttf", "IBMPlexSans-SemiBold.ttf"


def font(name, size):
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


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
    d.text((1140, 584), "polling2026.vikramrai.com", font=font(REGULAR, 20), fill=HEAD, anchor="ra")
    im.save(out_path, optimize=True)
