# SI-9: where the old name is written

Audit of every place the name `polling2026` (and the hostname `polling2026.vikramrai.com`) appears, done 2026-11-23 for
card SI-9. It is read-only: no code changed. It complements the OP-1 audit (`op1-hardcoded-2026-audit.md`), which covers
the 2026 *cycle* written into the code; this one covers the *name*. OP-1's line on the name (its section C, last item)
pointed here.

Method: `git grep -i polling2026` over the whole repository, plus a search for the hostname, the site's title and
header, the favicon and the link-preview images. Checked against `main` at 8b218a6 (after #67). The SI-3 work on the
local machine (commits 76ad269, 71a5921 and one more, not yet pushed) is not in this audit; the items it touches are
marked **SI-3** below and must be re-checked once it is merged.

## Decided 2026-11-23

- **Name:** Early Returns. Written "Early Returns" in the site header, page titles and link previews.
- **Slug:** `earlyreturns`, for the GitHub repo (`vrraiv/earlyreturns`) and the Cloudflare Worker.
- **Old address:** kept up, redirecting to the new one.
- **Logo and favicon:** new. A column chart being assembled from bits (compiling) blended with a ballot box receiving
  a vote (voting), for statistical analysis and voting together. The logo sits beside the name in the site header.

- **New hostname:** `earlyreturns.vikramrai.com` (confirmed 2026-11-23). The `earlyreturns` Worker does not exist yet.

## Summary

| Class | Places | What to do |
|---|---|---|
| A. Site name and hostname in the code | 9 source files | Replace. Most go through `site.json`; three files hardcode the hostname. |
| B. Generated pages | 11 files under `site/` | Rebuild with `build.py --all` and `landing.py`; never edit by hand. |
| C. Project and tooling | 4 files | Replace. |
| D. Docs | 4 files | Replace, noting the old name once. |
| E. Outside the repository | GitHub, Cloudflare, Claude, local machine | Done by hand, in order (below). |
| F. Leave as they are | 2 files | Historical records. |
| G. New: logo and favicon | 4 places | Design, then wire in. |

## A. Site name and hostname in the code

**Through `site.json` (one edit reaches every page)**
- `src/site/site.json:2` `"name": "polling2026"` → `"Early Returns"`. Read by `shell.py:66` (the header's site name,
  on every page) and `landing.py:50, 55, 58` (the landing page's `<title>`, `og:title` and `<h1>`). **SI-3**
- `src/site/site.json:3` `"base_url": "https://polling2026.vikramrai.com"` → the new hostname. Read by
  `landing.py:52` for `og:image`. **SI-3**

**Hostname written directly (should read `base_url` instead)**
- `src/site/template.html:10` `og:image` → `https://polling2026.vikramrai.com/og.png`. The forecast page template.
- `src/site/og_image.py:62` the hostname drawn into the bottom-right corner of `og.png`.
- `src/site/history.py:734` "Please credit this site (polling2026.vikramrai.com)" on the sources page.
- `src/collect/common.py:12` the collectors' User-Agent: `polling2026-research/0.1 (...; https://polling2026.vikramrai.com; https://github.com/vrraiv/polling2026)`.
  Name, site and repo all in one string. Changing it does not affect any collected data.

**Name written directly**
- `src/site/history.py:42` source label `"model": "polling2026 analysis"`, shown in chart source lines and the
  downloads table.
- `src/site/history.py:196` footer of the election data pages: `Code: MIT (<a href="https://github.com/vrraiv/polling2026">GitHub</a>)`.
- `src/collect/econ.py:56` User-Agent `"polling2026 research (contact: project owner)"`.
- `src/check_frozen.py:150` temp-folder prefix `polling2026-check-`. Cosmetic; change for consistency.

**Not the name, but checked**
- `src/site/template.html:6, 8` `<title>` and `og:title` are "2026 Midterm Forecast". That is the page's subject and
  stays. Consider `<meta property="og:site_name" content="Early Returns">` on every page (none has one now).
- `src/site/history.py:174` election data page titles carry no site name ("Votes · Election data"). Leave, or append
  " · Early Returns" everywhere at once.
- `.github/workflows/*.yml` use `${{ github.repository }}`, never the name, so they survive the rename.

## B. Generated pages (rebuild, do not edit)

All come from section A. Run `python src/site/build.py --all` and `python src/site/landing.py`, then check that the
only differences are the name, the hostname and the logo.

- `site/index.html:6, 13, 15, 20, 22` title, `og:title`, `og:image`, header, `<h1>`. **SI-3**
- `site/2026/forecast/index.html:10, 19` `og:image`, header. The forecast's embedded data must not change (check with
  `check_scorecard.py --ref main`, as for SI-6).
- `site/2026/index.html:17`, `site/404.html:15` header.
- `site/history/*.html` (approval, index, offcycle, polling, sources, states, votes) header, footer GitHub link, source
  labels, the sources page credit line.
- `site/og.png` (redrawn by `og_image.py`, carries the hostname).
- **SI-3** adds `site/og-home.png`, `site/2027/`, `site/2028/` and their preview images. They will carry the name and
  the hostname and need the same rebuild.

## C. Project and tooling

- `wrangler.jsonc:5` `"name": "polling2026"` → `"earlyreturns"`. A new name deploys a **new** Worker; see E.
- `pyproject.toml:2` `name = "polling2026"` → `"earlyreturns"`, then `uv lock` to update `uv.lock:310`.
- `uv.lock:310` follows from the line above; do not edit by hand.

## D. Docs

- `README.md:1, 3` title and live link. `README.md:11, 33, 40, 41, 58, 68, 70` the local venv path
  `$HOME\.venvs\polling2026`: rename only if the venv is renamed on the PC (optional; it is a local folder name).
- `PLAN.md:1, 10` title, live link and the Worker's name.
- `DATA.md:5` link to the sources page.
- `LICENSE-DATA.md:8` the credit line. Change to Early Returns (earlyreturns.vikramrai.com) and keep "formerly
  polling2026" so existing citations still resolve.
- `planning/op1-hardcoded-2026-audit.md:133` points at the naming decision; add "see si9-name-audit.md".
- `planning/plan.js` SI-9 card: record the decisions above and the extra scope (logo, favicon, redirect). Not done in
  this commit, because SI-3's unpushed plan edit bumps the same version line.

## E. Outside the repository, in order

1. **Push and merge SI-3 first.** Its commits are only on the PC.
2. **Rename the GitHub repo** `vrraiv/polling2026` → `vrraiv/earlyreturns`. GitHub redirects the old address for
   clones, pushes and web links. Then, on the PC, `git remote set-url origin https://github.com/vrraiv/earlyreturns.git`
   (works without it, but the redirect breaks if a new repo is ever created under the old name).
3. **Cloudflare Worker.** Create `earlyreturns` (not yet made as of 2026-11-23) by connecting Workers Builds to the
   renamed repo once the `wrangler.jsonc` change is on `main`; the dashboard name must match `wrangler.jsonc`. Then
   attach `earlyreturns.vikramrai.com` as its custom domain. The old Worker `polling2026` keeps the old hostname until step 4.
4. **Redirect the old hostname.** A static-assets Worker matches paths, not hosts, so `_redirects` cannot do this.
   Use a Cloudflare redirect rule on `polling2026.vikramrai.com`: 301 to the new hostname with the same path and query
   string. Then the old Worker can be deleted (its custom domain must stay proxied in DNS for the rule to fire). Old
   tab links like `/#senate` work, since the fragment stays in the browser and the new landing page forwards them.
5. **Claude.** Cloud environments and scheduled tasks that name `vrraiv/polling2026` (the bench-time task, any
   scorecard follow-ups) need the new repo attached; GitHub's redirect does not carry over the app's repository access.
6. **Local folder.** `C:\projects\polling2026` can stay or be renamed; nothing in the repo depends on it.

## F. Leave as they are

- `data/scorecard/poll_audit.json:18, 10588` an absolute path on the PC, recorded when the audit ran. A historical
  record.
- Git tag `final-forecast-2026` and the frozen 2026 forecast: named for the cycle, not the site.

## G. New: logo and favicon

Chosen 2026-11-23 after nine rounds of drafts (`design/logo/`): a race track with a check mark leaving the loop
early. The mark (F6) has two lanes and a staggered start, for the header and anything large; the favicon (F2s) has a
dashed infield only, for 16–32 px. One colour: `#1B4978` light, `#C9CFD8` dark.

Built and committed in `src/site/brand/` (new files only): both SVGs, `favicon.ico`, `apple-touch-icon.png`, and
512 px PNGs for link previews, with `brand.py` as the source. Not yet on the site. Where each piece goes, and the CSS,
is in `src/site/brand/README.md`:

- Header: `shell.py:66` writes the name as a text link; the mark goes inside it, before the name, as inline SVG
  coloured by a `--logo` token in `site/assets/site.css`.
- Favicon: replaces `src/site/favicon.svg` (copied to `site/` by `build.py:202`, linked by `shell.py:42`), with
  `favicon.ico` and `apple-touch-icon.png` beside it.
- Link previews: `og_image.py` (forecast `og.png`) and SI-3's landing and 2027/2028 cards show the mark and name in
  place of the bare hostname line.
