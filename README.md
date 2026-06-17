# KH Nuclear Task Force — State &amp; Local Regulatory Map

An embeddable, self-updating map of the U.S. state &amp; local nuclear-development
landscape: states tiered by how restrictive their nuclear law is, an accurate
ISO/RTO overlay, and a county-detail drill-down. Built as a single
`index.html` that reads its data from external JSON files, so the map can be
refreshed automatically without touching the page.

The map is one embeddable URL. Drop the repo on GitHub Pages and embed the
Pages URL in SharePoint via an iframe (Embed web part), the same pattern used
for the SMR Siting Tool.

---

## What updates automatically

A GitHub Action (`.github/workflows/update.yml`) runs **every Monday at
06:00 UTC**. It re-derives the restriction list, writes
`data/regulatory_data.json`, and commits the change **only if something
actually moved**. Because `index.html` fetches that file at load time, the
published map reflects the new landscape with no manual prompting.

```
DOE "What is a Nuclear Moratorium?"   ── live, primary ──┐
   (statewide moratorium list)                           │
NCSL restrictions page (via Internet Archive)            │   merge   ┌────────────────────────┐
   ── best-effort cross-check, never required ──────────►├──────────►│ regulatory_data.json   │
                                                         │           └────────────────────────┘
data/manual_overrides.json                               │
   ── editorial layer, authoritative ───────────────────┘
```

* **DOE is the live source.** The DOE Office of Nuclear Energy page is a stable
  federal page that enumerates the statewide-moratorium states. It is fetched
  every run and drives the `restricted` tier.
* **NCSL is a cross-check.** The live NCSL site blocks automated requests, so it
  is read best-effort through the Internet Archive. Any disagreement with DOE is
  recorded in `data/drift_report.json` for human review — it never blocks an
  update.
* **The editorial layer wins.** `data/manual_overrides.json` is hand-maintained
  and authoritative on mechanism wording, engagement notes, momentum flags, and
  any explicit tier corrections (e.g. NJ and IL, which recently opened but which
  a stale federal page may still list).
* **Graceful failure / drift detection.** A failed or unparseable fetch leaves
  the committed data untouched and logs the reason to `drift_report.json`. Any
  state added to or removed from the list since the last run is flagged there
  too — so if, say, Minnesota repeals its ban, it drops off the list, the map
  turns it green automatically, and the change is recorded for review.

## Where the data lives

| File | What it is | Auto or manual |
|------|------------|----------------|
| `data/regulatory_data.json` | State tiers + wording shown on the map | **auto** (weekly) |
| `data/drift_report.json` | Last run's status + any list changes | **auto** (weekly) |
| `data/manual_overrides.json` | Editorial layer — wording, notes, tier corrections, "recently opened" flags | manual |
| `data/county_notes.json` | FIPS-keyed local override layer (e.g. Long Island moratorium) | manual |
| `data/iso_rto.topojson` | Accurate ISO/RTO render geometry (7 regions) | rebuilt on demand |
| `data/state_iso.json` | Accurate `state → [markets]` lookup | rebuilt on demand |

`index.html` fetches `regulatory_data.json`, `county_notes.json`,
`state_iso.json`, and `iso_rto.topojson` at load. Edit any data file and the map
changes — no HTML edits, no redeploy beyond pushing the file.

## Accurate ISO/RTO borders

The overlay uses real **balancing-authority operating territories** (HIFLD
Control Areas), de-overlapped at the seams — not state approximations. ERCOT is
the ERCOT footprint, not all of Texas; states that span two or three markets
(TX, IL, MO, KY, MI, LA, and others) show every market they touch. City
spot-checks (Columbus → PJM, Chicago → PJM, New Orleans → MISO, Kansas City →
SPP, Detroit → MISO) all resolve correctly.

ISO/RTO boundaries are static; the weekly job does **not** touch them. To
regenerate them (only needed if a footprint actually changes):

```bash
pip install -r requirements.txt        # shapely
npm install -g mapshaper               # Node toolchain
python scripts/build_iso_geometry.py   # rewrites iso_rto.topojson + state_iso.json
```

## How to edit the editorial layers

* **Change wording, add an engagement note, correct a tier, flag a recent
  change** → edit `data/manual_overrides.json`. Keys per state: `tier`
  (`restricted`|`partial`|`clear`, forces the tier), `partial` (geographic /
  site-specific), `mech` (short mechanism label), `note` (panel detail),
  `recent` (true → "recently opened" flag), `effective` (date string).
* **Add a county ordinance / local rule** → add a FIPS-keyed entry to
  `data/county_notes.json` with `st`, `name`, `flag`
  (`restricted`|`favorable`|`watch`), and `note`.

The weekly scraper never overwrites these files.

## Deploying

1. Push this repo to GitHub.
2. **Settings → Pages**: serve from the default branch root. The map is the
   published `index.html`.
3. **Settings → Actions → General**: allow workflows to read and write
   (so the weekly job can commit). Then enable the workflow under the Actions
   tab; trigger a first run with **Run workflow** if you don't want to wait
   for Monday.
4. Embed the Pages URL in SharePoint via the Embed web part (iframe).

## Repository layout

```
index.html                          the map (fetches everything in data/)
data/
  regulatory_data.json              auto-generated weekly
  drift_report.json                 auto-generated weekly
  manual_overrides.json             editorial layer (you edit this)
  county_notes.json                 county override layer (you edit this)
  iso_rto.topojson                  ISO/RTO geometry (rebuild on demand)
  state_iso.json                    state → markets lookup (rebuild on demand)
scripts/
  update_regulatory.py              weekly scraper (stdlib only)
  build_iso_geometry.py             geometry rebuild (shapely + mapshaper)
.github/workflows/update.yml        weekly cron → scrape → commit if changed
requirements.txt
```

## Sources

U.S. DOE Office of Nuclear Energy · NCSL (via the Internet Archive) · state
legislation · ISO/RTO geometry from HIFLD balancing-authority footprints.
Confirm the governing statute and local zoning before any siting decision.
