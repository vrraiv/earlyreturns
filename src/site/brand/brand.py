"""The Early Returns mark and favicon (SI-9), drawn from one set of shapes.

Two cuts of one design, chosen 2026-11-23 (design/logo, rounds 1-9):
  mark     F6: a race track with two lanes and a staggered start; a check mark leaves the loop early.
           For the site header (24 px and up), link previews and anything larger.
  favicon  F2s: the same track and check with only a dashed infield, legible at 16-32 px.

One colour. The cut-outs are a mask, so the mark is transparent and takes its colour from `color` (inline) or from
the fill set in the file (standalone). Colours: #1B4978 in light mode (the site's heading blue), #C9CFD8 in dark mode.

    python src/site/brand/brand.py          writes mark.svg and favicon.svg beside this file
    node design/logo/export_png.js          renders the PNGs and favicon.ico from them (needs Playwright)

Nothing here is wired into the site yet; see README.md in this folder for the steps."""
from pathlib import Path

LIGHT, DARK = "#1B4978", "#C9CFD8"
_A = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'


def _track(w=2.2):
    return f'<rect x="2" y="7" width="28" height="19" rx="9.5" fill="none" stroke="#fff" stroke-width="{w}"/>'


def _check(w=2.6, gap=0.9):
    d = "M10.4 17.6 L14 21 L26.8 5"
    return (f'<path d="{d}" {_A} stroke="#000" stroke-width="{w + 2 * gap}"/>'
            f'<path d="{d}" {_A} stroke="#fff" stroke-width="{w}"/>')


MARK = (_track()
        + '<rect x="5" y="10" width="22" height="13" rx="6.5" fill="none" stroke="#fff" stroke-width="1.4" '
          'stroke-dasharray="1.8 1.7" stroke-linecap="round"/>'
        + '<rect x="8" y="13" width="16" height="7" rx="3.5" fill="none" stroke="#fff" stroke-width="1.8"/>'
        + '<line x1="17.5" y1="20.9" x2="17.5" y2="22.1" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>'
        + '<line x1="21.5" y1="23.9" x2="21.5" y2="25.1" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>'
        + _check())

FAVICON = (_track()
           + '<rect x="8" y="13" width="16" height="7" rx="3.5" fill="none" stroke="#fff" stroke-width="2" '
             'stroke-dasharray="3.4 2.4" stroke-linecap="round"/>'
           + _check())


def svg(shapes, mask_id, size=None, cls=None, fill="currentColor", style=""):
    """An <svg> of the given shapes, filled with `fill` through the cut-out mask."""
    attrs = f' width="{size}" height="{size}"' if size else ""
    attrs += f' class="{cls}"' if cls else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"{attrs} aria-hidden="true" focusable="false">{style}'
            f'<mask id="{mask_id}"><rect width="32" height="32" fill="#000"/>{shapes}</mask>'
            f'<rect class="er-ink" width="32" height="32" fill="{fill}" mask="url(#{mask_id})"/></svg>')


def mark_inline(size=24):
    """The header's mark: coloured by CSS `color` (see README.md), one per page, so its mask id is fixed."""
    return svg(MARK, "er-mark", size, cls="logo")


_SCHEME = f'<style>.er-ink{{fill:{LIGHT}}}@media (prefers-color-scheme: dark){{.er-ink{{fill:{DARK}}}}}</style>'


def standalone(shapes, mask_id):
    """A file that picks its colour from the viewer's light or dark setting (browser tabs, previews)."""
    return svg(shapes, mask_id, fill=LIGHT, style=_SCHEME) + "\n"


def write(folder=Path(__file__).parent):
    (folder / "mark.svg").write_text(standalone(MARK, "er-mark"), encoding="utf-8")
    (folder / "favicon.svg").write_text(standalone(FAVICON, "er-fav"), encoding="utf-8")


if __name__ == "__main__":
    write()
