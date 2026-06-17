# KH Nuclear Task Force — State & Local Regulatory Map

An embeddable, self-updating map of the U.S. state & local nuclear-development
landscape: states tiered by how restrictive their nuclear law is, an accurate
ISO/RTO overlay, and a county-detail drill-down. `index.html` reads its data
from sibling JSON files, so the map refreshes automatically without touching
the page.

> **Flat layout.** Every file sits at the repository root (no `data/` or
> `scripts/` subfolders). This matches GitHub's "Add files via upload" flow,
> which flattens folders. The one exception is the Actions workflow, which
> **must** live at `.github/workflows/update.yml` — see *Deploying* below.

---

## What updates automatically

A GitHub Action (`.github/workflows/update.yml`) runs **every Monday at
06:00 UTC**. It re-derives the restriction list, writes `regulatory_data.json`,
and commits the change **only if something actually moved**. Because
`index.html` fetches that file at load time, the published map reflects the new
landscape with no manual prompting.

- **DOE is the live source** — a stable federal page listing the statewide-
  moratorium states; fetched every run, drives the `restricted` tier.
- **NCSL is a cross-check** read best-effort through the Internet Archive (the
  live NCSL site blocks automated requests). Disagreements are logged to
  `drift_report.json`; an unreachable NCSL never blocks an update.
- **The editorial layer wins.** `manual_overrides.json` is authoritative on
  wording, engagement notes, momentum flags, and tier corrections (e.g. NJ and
  IL, which recently opened but which a stale federal page may still list).
- **Graceful failure / drift detection.** A failed fetch leaves the committed
  data untouched and logs the reason; any state added to or removed from the
  list is flagged in `drift_report.json` for review.

## The files (all at root)

| File | What it is | Auto or manual |
|------|------------|----------------|
| `index.html` | The map (fetches the JSON below) | — |
| `regulatory_data.json` | State tiers + wording shown on the map | **auto** (weekly) |
| `drift_report.json` | Last run's status + any list changes | **auto** (weekly) |
| `manual_overrides.json` | Editorial layer — wording, notes, tier corrections, "recently opened" flags | manual |
| `county_notes.json` | FIPS-keyed local override layer (e.g. Long Island moratorium) | manual |
| `iso_rto.topojson` | Accurate ISO/RTO render geometry (7 regions) | rebuilt on demand |
| `state_iso.json` | Accurate state -> [markets] lookup | rebuilt on demand |
| `update_regulatory.py` | Weekly scraper (stdlib only) | — |
| `build_iso_geometry.py` | Geometry rebuild (shapely + mapshaper) | — |

Edit any JSON file and the map changes — no HTML edits, just push the file.

## Accurate ISO/RTO borders

The overlay uses real **balancing-authority operating territories** (HIFLD
Control Areas), de-overlapped at the seams — not state approximations. ERCOT is
the ERCOT footprint, not all of Texas; states that span two or three markets
(TX, IL, MO, KY, MI, LA, ...) show every market they touch. ISO/RTO boundaries
are static; the weekly job does **not** touch them. To regenerate (only if a
footprint actually changes):

```bash
pip install -r requirements.txt        # shapely
npm install -g mapshaper               # Node toolchain
python build_iso_geometry.py           # rewrites iso_rto.topojson + state_iso.json
```

## How to edit the editorial layers

- **Change wording / add an engagement note / correct a tier / flag a recent
  change** -> edit `manual_overrides.json`. Keys per state: `tier`
  (`restricted`|`partial`|`clear`, forces the tier), `partial`, `mech` (short
  label), `note` (panel detail), `recent` (true -> "recently opened"),
  `effective` (date string).
- **Add a county ordinance / local rule** -> add a FIPS-keyed entry to
  `county_notes.json` with `st`, `name`, `flag`
  (`restricted`|`favorable`|`watch`), and `note`.

The weekly scraper never overwrites these files.

## Deploying

1. Upload all the root files to the repo (you've done this).
2. **Create the workflow at its required path.** GitHub Actions only runs
   workflows under `.github/workflows/`, and the upload flattens folders, so
   create it by hand: **Add file -> Create new file**, type the name
   `.github/workflows/update.yml` (typing `/` makes the folders), paste the
   contents of the included `update.yml`, and commit.
3. **Settings -> Pages**: serve from the default branch, root folder. The map is
   the published `index.html`.
4. **Settings -> Actions -> General -> Workflow permissions**: select
   *Read and write permissions* so the weekly job can commit. Then open the
   Actions tab and use **Run workflow** once to confirm it works.
5. Embed the Pages URL in SharePoint via the Embed web part (iframe).

## Sources

U.S. DOE Office of Nuclear Energy · NCSL (via the Internet Archive) · state
legislation · ISO/RTO geometry from HIFLD balancing-authority footprints.
Confirm the governing statute and local zoning before any siting decision.
