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
| `index.html` | The map (fetches everything below) | — |
| `regulatory_data.json` | Statutory restriction tier per state | **auto** (weekly) |
| `drift_report.json` | Last run's status + any list changes | **auto** (weekly) |
| `state_posture.json` | Friendliness/activity layer — score 0-4, signals, state nuclear entity, fleet, Task Force angle | manual |
| `county_data.json` | County signals — `energy_community` (818 FIPS) + `nuclear_host` (76 FIPS) | derived |
| `county_names.json` | FIPS -> [county, state] for every U.S. county (selectable names) | derived |
| `county_notes.json` | Curated local overrides (e.g. Long Island moratorium) | manual |
| `manual_overrides.json` | Editorial layer for the restriction tier — wording, tier corrections, "recently opened" flags | manual |
| `iso_rto.topojson` | Accurate ISO/RTO render geometry (7 regions) | rebuilt on demand |
| `state_iso.json` | Accurate state -> [markets] lookup | rebuilt on demand |
| `update_regulatory.py` | Weekly scraper (stdlib only) | — |
| `build_iso_geometry.py` | ISO geometry rebuild (shapely + mapshaper) | — |
| `build_county_signals.py` | County signal rebuild (shapely) | — |

Edit any JSON file and the map changes — no HTML edits, just push the file.

## Two reads of every place: favorability + restriction tier

The map answers two questions, switchable with the **COLOR BY** control:

- **Favorability (default)** — a 0-4 read of how friendly a place is to new
  development: `0 Hostile` (statewide moratorium), `1 Restrictive` (geographic
  or site-specific), `2 Neutral` (standard NRC + state PUC pathway),
  `3 Favorable` (active state support), `4 Leading` (incentives / dedicated
  office / directed deployment). State scores live in `state_posture.json`,
  sourced from NEI/ANS "Where States Stand on Nuclear" (Jan 2026), NCSL, DOE,
  and state legislation.
- **Restriction tier** — the binding statute only: `restricted` / `partial` /
  `clear`, auto-refreshed weekly.

The state panel shows both, plus the concrete 2025-26 signals, the state
nuclear entity, existing fleet, markets, and a Task Force engagement angle.

## County detail: every county is selectable

Turn on **County Detail** and click any of the ~3,140 counties. There is no
national dataset of county nuclear zoning codes — those live as thousands of
separate municipal documents — so the tool models the layers that actually
generalize:

1. **Inherited state regime.** Federal (NRC) licensing is uniform; the binding
   sub-federal layer is state law, which applies to every county in the state.
   Each county inherits its state's tier and favorability as the baseline.
2. **County-resolvable favorability signals** (`county_data.json`):
   - **Energy community** — IRA coal-closure counties (NETL/Treasury). Bonus
     clean-energy tax credits plus transmission and workforce from retired
     coal = siting-favorable.
   - **Nuclear host** — counties already hosting an operating or pipeline
     reactor (demonstrated siting precedent, workforce, transmission,
     interconnection).
3. **Curated local overrides** (`county_notes.json`) — documented local rules,
   e.g. the Long Island moratorium.

Composite county favorability = state baseline, nudged **up** one step where a
county is an energy community or a nuclear host (only where development is
already legal — a coal closure does not undo a statewide moratorium), and
forced to **Hostile** where a local override restricts. The county panel is
explicit that local zoning/special-use permitting must be confirmed against the
jurisdiction's own code.

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
python build_county_signals.py         # rewrites county_data.json + county_names.json
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

U.S. DOE Office of Nuclear Energy · NCSL (via the Internet Archive) · NEI/ANS
"Where States Stand on Nuclear" (state posture) · IRA energy communities
(NETL / U.S. Treasury) · operating + pipeline reactor hosts · ISO/RTO geometry
from HIFLD balancing-authority footprints. There is no national dataset of
county nuclear zoning codes; confirm the governing statute and the local
ordinance before any siting decision.
