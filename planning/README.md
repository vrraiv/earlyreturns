# Work plan for 2028

The plan for taking this project from the 2026 midterm forecast to 2028: nine parallel tracks, each a set of story
cards with dependencies, steps and pointers into the repo.

| File | What it is |
|---|---|
| `plan.js` | The plan itself: tracks, cards, phases, fixed dates and ground rules. This is the file to edit. |
| `workplan.html` | The tracker page that reads `plan.js`: overview, timeline, one page per track, decisions, ideas. |

Nothing here is part of the public site. The site is built from `site/`, and this folder is not linked from it.

## Using it

The working copy is a private hosted page, where statuses, ticked steps, notes and ideas are saved to a database and
follow you across devices. Those are not stored in this repo.

`workplan.html` also opens straight from disk. It is a page fragment (no doctype), so open it in a browser from this
folder with `plan.js` beside it. In that mode changes are kept in that browser only.

Use **Export** or **Copy** in the header to save a snapshot of statuses, ticked steps, notes and ideas to
`planning/state.local.json` (gitignored), so local agents or an offline browser copy (**Import**) can read them without
putting private notes in git.

## Editing the plan

- Edit `plan.js` and open a pull request. Plan changes never share a commit with forecast changes.
- **Card ids and checklist item ids are permanent.** Saved statuses and notes are keyed by them. Add new ids; never
  renumber or reuse one. To retire a card, leave it in place and mark it dropped on the page.
- This repo is public. Keep provisional 2026 numbers and anything private out of `plan.js`; they belong in notes on
  the hosted page.
- After a change, check the file:

```powershell
node -e "global.window={}; require('./planning/plan.js'); console.log(window.PLAN.tracks.map(t => t.code + ':' + t.cards.length).join(' '))"
```

## Fixed dates

- May 2027: a first presidential primaries model (both parties, decided 2026-11-20).
- May 2028: the electoral college model and every other model frozen.
- November 7, 2028: Election Day.

Everything else is ordered by dependency and tied to outside events, not to deadlines.
