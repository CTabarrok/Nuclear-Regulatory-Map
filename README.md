#!/usr/bin/env python3
"""
update_regulatory.py  --  Kimley-Horn Nuclear Task Force
================================================================
Refreshes data/regulatory_data.json for the State & Local Regulatory Map.

Design (mirrors the KH NRC Rulemaking Tracker philosophy):
  * PRIMARY LIVE SOURCE = DOE Office of Nuclear Energy "What is a Nuclear
    Moratorium?" -- a stable federal page that enumerates the states with a
    full statewide moratorium. This is fetched every run and drives the
    "restricted" tier.
  * PARTIAL TIER = the partial_states list in manual_overrides.json
    (geographic / site-specific restrictions such as CT-Millstone and
    NY-Long Island). These are stable and editorially maintained.
  * CROSS-CHECK = NCSL's restrictions page, read best-effort through the
    Internet Archive (the live NCSL site blocks automated requests). If it
    is reachable, any disagreement with DOE is recorded for human review.
    It is NEVER required -- an unreachable NCSL never blocks an update.
  * EDITORIAL LAYER (data/manual_overrides.json) is hand-maintained and
    WINS on wording, engagement notes, momentum (recent) flags, and any
    explicit tier corrections (e.g. NJ/IL recently opened). The scraper
    never overwrites it.
  * GRACEFUL FAILURE: if the live source can't be fetched/parsed, the
    committed regulatory_data.json is left untouched and the failure is
    recorded in data/drift_report.json. A bad fetch never wipes good data.
  * DRIFT DETECTION: any state added to / removed from the restriction list
    since the last run is written to drift_report.json for human review.

Run:  python scripts/update_regulatory.py
"""

import json, os, re, sys, datetime, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
OUT_DATA  = os.path.join(DATA, "regulatory_data.json")
OVERRIDES = os.path.join(DATA, "manual_overrides.json")
DRIFT     = os.path.join(DATA, "drift_report.json")

DOE_URL  = "https://www.energy.gov/ne/articles/what-nuclear-moratorium"
NCSL_URL = "https://www.ncsl.org/environment-and-natural-resources/states-restrictions-on-new-nuclear-power-facility-construction"
# Internet Archive "id_" replay returns the original NCSL HTML with no archive chrome.
WAYBACK_AVAIL = "https://archive.org/wayback/available?url=" + urllib.request.quote(
    "ncsl.org/environment-and-natural-resources/states-restrictions-on-new-nuclear-power-facility-construction", safe="")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

NAME2AB = {
 "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA","colorado":"CO",
 "connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA","hawaii":"HI","idaho":"ID",
 "illinois":"IL","indiana":"IN","iowa":"IA","kansas":"KS","kentucky":"KY","louisiana":"LA",
 "maine":"ME","maryland":"MD","massachusetts":"MA","michigan":"MI","minnesota":"MN","mississippi":"MS",
 "missouri":"MO","montana":"MT","nebraska":"NE","nevada":"NV","new hampshire":"NH","new jersey":"NJ",
 "new mexico":"NM","new york":"NY","north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK",
 "oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC","south dakota":"SD",
 "tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT","virginia":"VA","washington":"WA",
 "west virginia":"WV","wisconsin":"WI","wyoming":"WY"
}
# Longest-first so "new york" matches before "york"-like fragments; multiword before single.
NAME_KEYS = sorted(NAME2AB.keys(), key=len, reverse=True)


def fetch(url, tries=4):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:           # noqa: BLE001
            last = e
    raise RuntimeError("fetch failed for %s: %s" % (url, last))


def strip_tags(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", html)


def states_in(text):
    """Return the set of state abbreviations named in a text fragment."""
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    found = set()
    for name in NAME_KEYS:
        if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", t):
            found.add(NAME2AB[name])
    return found


def parse_doe_moratorium(html):
    """States DOE lists as FULL statewide moratoriums (restricted tier)."""
    text = re.sub(r"\s+", " ", strip_tags(html))
    # Primary: "...statewide moratoriums in [N] states: A, B, C ..."
    m = re.search(r"statewide moratoriums?[^.:]*?(?:in|these)\s+(?:these\s+)?(\w+)\s+states[^:]*:\s*([^.]+)\.", text, re.I)
    if m:
        s = states_in(m.group(2))
        if 3 <= len(s) <= 12:
            return s, "doe:n-states-sentence"
    # Fallback: the sentence asserting moratoriums "remain in place".
    m = re.search(r"statewide moratoriums? remain in place[^.]*\.", text, re.I)
    if m:
        s = states_in(m.group(0))
        if 3 <= len(s) <= 12:
            return s, "doe:remain-in-place"
    raise RuntimeError("DOE parse produced an implausible moratorium list")


def parse_ncsl(html):
    """NCSL list of states that restrict new nuclear construction (cross-check)."""
    text = re.sub(r"\s+", " ", strip_tags(html))
    m = re.search(r"restrictions? on .{0,80}?new nuclear[^:]{0,80}?:\s*([^.]+)\.", text, re.I)
    if m:
        s = states_in(m.group(1))
        if 3 <= len(s) <= 20:
            return s, "ncsl:lead-sentence"
    s = states_in(text[:1500])
    if 3 <= len(s) <= 20:
        return s, "ncsl:lead-scan"
    raise RuntimeError("NCSL parse produced an implausible list (%d states)" % len(s))


def ncsl_via_wayback():
    """Best-effort NCSL list through the Internet Archive. Returns (set|None, src)."""
    try:
        avail = json.loads(fetch(WAYBACK_AVAIL, tries=2))
        snap = avail.get("archived_snapshots", {}).get("closest", {})
        if not snap.get("available"):
            return None, "ncsl:wayback-no-snapshot"
        ts = snap.get("timestamp", "")
        raw = "https://web.archive.org/web/%sid_/%s" % (ts, NCSL_URL)
        s, p = parse_ncsl(fetch(raw, tries=2))
        return s, "ncsl:wayback:%s:%s" % (ts, p)
    except Exception as e:               # noqa: BLE001
        return None, "ncsl:wayback-unavailable:%s" % e


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                    # noqa: BLE001
        return default


def main():
    ov = load_json(OVERRIDES, {"partial_states": [], "states": {}})
    ov_states = ov.get("states", {})
    partial_default = set(ov.get("partial_states", []))
    prev = load_json(OUT_DATA, {})
    prev_list = set(prev.get("meta", {}).get("restriction_list", []))

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    notes = []

    # ---- PRIMARY: DOE live moratorium list; fail safe ----
    try:
        doe_moratorium, doe_src = parse_doe_moratorium(fetch(DOE_URL))
    except Exception as e:               # noqa: BLE001
        notes.append("DOE fetch/parse FAILED (%s) \u2014 kept previous data." % e)
        write_drift(prev_list, prev_list, now, notes, ok=False)
        print("\n".join(notes)); print("No changes written.")
        return 0

    # ---- CROSS-CHECK: NCSL via Internet Archive (best-effort, never required) ----
    ncsl_list, ncsl_src = ncsl_via_wayback()
    if ncsl_list is None:
        notes.append("NCSL cross-check unavailable (%s) \u2014 proceeding on DOE + overrides." % ncsl_src)
    else:
        extra = sorted((ncsl_list - doe_moratorium) - partial_default)
        if extra:
            notes.append("NCSL lists state(s) DOE does not: %s \u2014 review (treated as partial)." % ", ".join(extra))

    # ---- assemble base tiers: DOE -> restricted, partial_states -> partial ----
    states = {}
    for ab in doe_moratorium:
        states[ab] = {"tier": "restricted"}
    for ab in partial_default:
        states.setdefault(ab, {})["tier"] = "partial"
    # NCSL-only states (not in DOE, not already partial) surface as partial for review.
    if ncsl_list:
        for ab in (ncsl_list - doe_moratorium) - partial_default:
            states.setdefault(ab, {})["tier"] = "partial"

    # ---- merge editorial overrides (authoritative on wording / flags / tier) ----
    for ab, o in ov_states.items():
        rec = states.get(ab, {})
        if o.get("partial"):
            rec["tier"] = "partial"
        if "tier" in o:
            rec["tier"] = o["tier"]               # e.g. NJ/IL forced to "clear"
        for k in ("mech", "note", "recent", "effective"):
            if k in o:
                rec[k] = o[k]
        states[ab] = rec

    # Drop anything an override pinned to "clear" from the restriction tiers,
    # but keep the record so the map can render its "recently opened" flag.
    restriction_list = sorted(ab for ab, r in states.items() if r.get("tier") in ("restricted", "partial"))

    # ---- drift vs previous run ----
    cur = set(restriction_list)
    added   = sorted(cur - prev_list)
    removed = sorted(prev_list - cur)
    if added:   notes.append("ADDED to restriction list: %s" % ", ".join(added))
    if removed: notes.append("REMOVED from restriction list: %s" % ", ".join(removed))
    if not (added or removed):
        notes.append("No change to the restriction list since last run.")

    out = {
        "meta": {
            "updated": now,
            "restriction_list": restriction_list,
            "sources": {
                "doe":  {"url": DOE_URL,  "parse": doe_src,  "role": "primary (live)"},
                "ncsl": {"url": NCSL_URL, "parse": ncsl_src, "role": "cross-check (best-effort via Internet Archive)"},
            },
            "tier_legend": {
                "restricted": "statewide moratorium / high statutory barrier",
                "partial": "geographic or site-specific restriction only",
                "clear": "no statewide restriction (default if absent)",
            },
            "note": "Restriction list refreshed weekly from DOE (live) with an NCSL cross-check via the Internet Archive; mechanism wording, engagement notes and momentum flags come from manual_overrides.json.",
        },
        "states": states,
    }
    with open(OUT_DATA, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    write_drift(prev_list, cur, now, notes, ok=True)

    print("\n".join(notes))
    print("Wrote %s (%d restriction/partial states)." %
          (os.path.relpath(OUT_DATA), len(restriction_list)))
    return 0


def write_drift(prev_list, cur_list, now, notes, ok):
    drift = {
        "checked": now,
        "ok": ok,
        "restriction_list": sorted(cur_list),
        "added": sorted(set(cur_list) - set(prev_list)),
        "removed": sorted(set(prev_list) - set(cur_list)),
        "notes": notes,
    }
    with open(DRIFT, "w", encoding="utf-8") as f:
        json.dump(drift, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
