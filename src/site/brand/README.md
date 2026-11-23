# Early Returns mark (SI-9)

Chosen 2026-11-23 after nine rounds of drafts (`design/logo/`). Two cuts of one design:

| File | What | Use |
|---|---|---|
| `mark.svg` | F6: race track, two lanes, staggered start, a check leaving the loop early | Header (24 px and up), link previews, anything large |
| `favicon.svg` | F2s: the same track and check with a dashed infield only | Browser tab, 16–32 px |
| `favicon.ico` | 16, 32 and 48 px of `favicon.svg` | Browsers that ask for `/favicon.ico` |
| `favicon-16/32/48.png` | The sizes packed into the `.ico` | Source for the `.ico` |
| `apple-touch-icon.png` | 180 px, the favicon on the site's light background | Phone home screens |
| `mark-512.png`, `mark-512-dark.png` | The mark, transparent, light and dark colours | Link-preview images (`og_image.py`, SI-3's cards) |

One colour: `#1B4978` in light mode (the site's heading blue), `#C9CFD8` in dark mode. The cut-outs are a mask, so the
mark is transparent on any background.

`brand.py` holds the shapes and writes both SVGs; `mark_inline()` returns the header's copy, coloured by CSS.
To change the design: edit `brand.py`, then from the repo root

```
python src/site/brand/brand.py
node design/logo/export_png.js        # needs Playwright and Chromium
python design/logo/make_ico.py
```

## Wiring it in (after SI-3 is merged, with the rename pass)

Not done yet, because SI-3's unpushed work also edits `shell.py`'s neighbours, `site.css` and the generated pages.

1. **Header.** In `src/site/shell.py`, `header()`: put `brand.mark_inline(22)` inside the `sitename` link, before the
   name, and import `brand` (it sits in `src/site/brand/`, so add that folder to the import path or move `brand.py`
   up beside `shell.py`).
2. **Colour and spacing.** In `site/assets/site.css`, a token in each mode and the layout of the name link:

   ```css
   :root { --logo: #1B4978; }                    /* light, beside the other light tokens */
   :root[data-theme="dark"] { --logo: #C9CFD8; } /* dark, beside the other dark tokens */
   .sitebar .sitename { display: inline-flex; align-items: center; gap: 8px; }
   .sitebar .sitename .logo { color: var(--logo); flex: none; }
   ```

   The header follows the page's own light/dark switch (`data-theme`), not the device setting, so the colour comes
   from this token and not from the SVG's `prefers-color-scheme` rule.
3. **Favicon.** Replace `src/site/favicon.svg` with `brand/favicon.svg` (`build.py:202` copies it to `site/`). Copy
   `favicon.ico` and `apple-touch-icon.png` to `site/` in the same step, and in `shell.py`'s `head()` add
   `<link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">` beside the icon link. The favicon follows the
   browser's own light or dark setting.
4. **Link previews.** Draw `mark-512.png` (scaled down) beside "Early Returns" in `og_image.py` in place of the
   hostname line, and do the same on SI-3's landing, 2027 and 2028 cards.
5. **Check.** `python src/site/build.py --all`, then the header in both modes and at 375 px wide, the tab icon, and
   that `check_scorecard.py --ref main` is CLEAN.
