#!/usr/bin/env python3
"""
build_iso_geometry.py  --  Kimley-Horn Nuclear Task Force
================================================================
Regenerates the accurate ISO/RTO map geometry from the authoritative
HIFLD "Control Areas" (balancing-authority) layer.

Produces two files consumed by index.html:

    data/iso_rto.topojson   7 de-overlapped ISO/RTO regions (render geometry,
                            object key "iso", ids = operator codes)
    data/state_iso.json     accurate  state -> [markets]  lookup, computed by
                            polygon intersection of each state with the clean
                            balancing-authority geometry (>=4% of state area)

WHY A BALANCING-AUTHORITY SOURCE
--------------------------------
ISO/RTO "membership" extents in some HIFLD layers are giant overlapping
blobs that swallow whole regions -- unusable for a map. The balancing-
authority operating territories are clean, non-overlapping, and are what
people mean by "which market is this site in." The seven ISO/RTO balancing
authorities are filtered out of the Control Areas layer and lightly
de-overlapped at the seams.

DATA SOURCE (stable PASDA mirror of HIFLD)
------------------------------------------
    .../pasda/HIFLD_FEMA/MapServer/26   (Control Areas)
Each balancing authority is fetched individually (NAME LIKE filter, Esri
JSON) because the bulk geojson export of this layer returns HTML errors.

REQUIREMENTS
------------
    pip install shapely requests       (see requirements.txt)
    npm  install -g mapshaper          (Node toolchain; build-time only)

This is a BUILD-TIME tool. The weekly GitHub Action does NOT run it
(geometry is static). Re-run only when an ISO/RTO footprint actually
changes, then commit the regenerated data files:

    python scripts/build_iso_geometry.py
"""

import json, os, subprocess, sys, tempfile, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = HERE  # flat layout: data files live next to the scripts
OUT_TOPO  = os.path.join(DATA, "iso_rto.topojson")
OUT_STATE = os.path.join(DATA, "state_iso.json")

PASDA = ("https://mapservices.pasda.psu.edu/server/rest/services/"
         "pasda/HIFLD_FEMA/MapServer/26/query")

# Balancing authorities that ARE the ISO/RTOs, keyed by operator code.
BA_QUERY = {
    "CAISO": "NAME LIKE '%CALIFORNIA ISO%'",
    "ERCOT": "NAME LIKE '%ELECTRIC RELIABILITY COUNCIL OF TEXAS%'",
    "ISONE": "NAME LIKE '%ISO NEW ENGLAND%'",
    "MISO":  "NAME LIKE '%MIDCONTINENT INDEPENDENT%'",
    "NYISO": "NAME LIKE '%NEW YORK INDEPENDENT%'",
    "PJM":   "NAME LIKE '%PJM INTERCONNECTION%'",
    "SPP":   "NAME LIKE '%SOUTHWEST POWER POOL%'",
}

# De-overlap priority: smaller / enclosed territories win at the seams, so they
# are subtracted out of the larger ones first.
PRIORITY = ["NYISO", "ISONE", "PJM", "ERCOT", "CAISO", "MISO", "SPP"]

STATES_10M = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json"
STATE_SHARE_MIN = 0.04   # min share of a state's area inside a market to count it

FIPS2AB = {
 "01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE",
 "12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS",
 "21":"KY","22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS",
 "29":"MO","30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY",
 "37":"NC","38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC",
 "46":"SD","47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV",
 "55":"WI","56":"WY",
}


def need(mod):
    try:
        return __import__(mod)
    except ImportError:
        sys.exit("Missing dependency '%s'. Run: pip install -r requirements.txt" % mod)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "KH-NTF-geometry-build/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_ba(where):
    qs = urllib.parse.urlencode({
        "where": where, "outFields": "NAME", "returnGeometry": "true",
        "outSR": "4326", "f": "json",
    })
    return get_json(PASDA + "?" + qs)


def esri_to_polygons(esri):
    """Convert Esri polygon rings to a shapely (Multi)Polygon, honouring holes.

    Esri encodes outer rings clockwise (signed area < 0) and holes counter-
    clockwise; assign each hole to the outer ring that contains it.
    """
    from shapely.geometry import Polygon, MultiPolygon
    from shapely.ops import unary_union
    polys = []
    for feat in esri.get("features", []):
        rings = feat.get("geometry", {}).get("rings", [])
        outers, holes = [], []
        for ring in rings:
            area2 = 0.0
            for i in range(len(ring) - 1):
                x1, y1 = ring[i]; x2, y2 = ring[i + 1]
                area2 += x1 * y2 - x2 * y1
            (outers if area2 < 0 else holes).append(ring)
        if not outers:
            outers = rings
        shells = [Polygon(o) for o in outers]
        for hole in holes:
            hp = Polygon(hole)
            for j, sh in enumerate(shells):
                if sh.contains(hp.representative_point()):
                    shells[j] = Polygon(sh.exterior.coords,
                                        list(sh.interiors) + [hole])
                    break
        polys.extend(shells)
    if not polys:
        return None
    geom = unary_union(polys)
    if geom.geom_type == "Polygon":
        geom = MultiPolygon([geom])
    return geom


def build_geometry():
    """Fetch + de-overlap the 7 BAs, return {code: shapely geom} and write the topojson."""
    need("shapely")
    from shapely.geometry import mapping
    from shapely.validation import make_valid

    os.makedirs(DATA, exist_ok=True)

    raw = {}
    for code, where in BA_QUERY.items():
        print("fetching %-6s ..." % code, end=" ", flush=True)
        geom = esri_to_polygons(fetch_ba(where))
        if geom is None or geom.is_empty:
            sys.exit("no geometry for %s (check NAME filter / source URL)" % code)
        raw[code] = make_valid(geom).buffer(0)
        print("ok (%.1f sq-deg)" % raw[code].area)

    clean, taken = {}, None
    for code in PRIORITY:
        g = raw[code]
        if taken is not None:
            g = g.difference(taken)
        g = make_valid(g).buffer(0)
        clean[code] = g
        taken = g if taken is None else taken.union(g)

    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": code, "properties": {"iso": code},
         "geometry": mapping(clean[code])}
        for code in BA_QUERY
    ]}
    with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False) as tf:
        json.dump(fc, tf)
        clean_path = tf.name
    try:
        subprocess.run([
            "mapshaper", clean_path,
            "-simplify", "6%", "weighted", "keep-shapes",
            "-o", "format=topojson", "id-field=iso", "quantization=10000",
            OUT_TOPO,
        ], check=True)
    except FileNotFoundError:
        sys.exit("mapshaper not found. Install with: npm install -g mapshaper")
    finally:
        os.unlink(clean_path)

    t = json.load(open(OUT_TOPO))
    objs = t.get("objects", {})
    if "iso" not in objs and len(objs) == 1:
        t["objects"] = {"iso": next(iter(objs.values()))}
        json.dump(t, open(OUT_TOPO, "w"))
    print("wrote", os.path.relpath(OUT_TOPO))
    return clean


def topojson_features(topo, obj_key):
    """Minimal TopoJSON -> GeoJSON feature decoder (Polygon/MultiPolygon)."""
    arcs = topo["arcs"]
    tr = topo.get("transform")

    def dec(arc_idx):
        rev = arc_idx < 0
        a = arcs[~arc_idx] if rev else arcs[arc_idx]
        pts, x, y = [], 0, 0
        for p in a:
            if tr:
                x += p[0]; y += p[1]
                pts.append([x * tr["scale"][0] + tr["translate"][0],
                            y * tr["scale"][1] + tr["translate"][1]])
            else:
                pts.append(list(p))
        return pts[::-1] if rev else pts

    def ring(arc_list):
        coords = []
        for ai in arc_list:
            seg = dec(ai)
            coords.extend(seg if not coords else seg[1:])
        return coords

    def poly(rings):
        return [ring(r) for r in rings]

    feats = []
    for g in topo["objects"][obj_key]["geometries"]:
        gt = g["type"]
        if gt == "Polygon":
            geom = {"type": "Polygon", "coordinates": poly(g["arcs"])}
        elif gt == "MultiPolygon":
            geom = {"type": "MultiPolygon", "coordinates": [poly(p) for p in g["arcs"]]}
        else:
            continue
        feats.append({"id": g.get("id"), "geometry": geom})
    return feats


def build_state_lookup(clean):
    """Compute state -> [markets] by intersecting states with the clean BA geom."""
    from shapely.geometry import shape
    from shapely.validation import make_valid

    states_topo = get_json(STATES_10M)
    state_feats = topojson_features(states_topo, "states")

    out = {}
    for f in state_feats:
        ab = FIPS2AB.get(str(f["id"]).zfill(2))
        if not ab:
            continue
        g = make_valid(shape(f["geometry"])).buffer(0)
        if g.is_empty or g.area == 0:
            out[ab] = []
            continue
        hits = []
        for code, mg in clean.items():
            inter = g.intersection(mg)
            if not inter.is_empty and inter.area / g.area >= STATE_SHARE_MIN:
                hits.append((code, inter.area))
        out[ab] = [c for c, _ in sorted(hits, key=lambda x: -x[1])]
    json.dump(out, open(OUT_STATE, "w"))
    print("wrote", os.path.relpath(OUT_STATE),
          "(%d states, %d split across >1 market)" %
          (len(out), sum(1 for v in out.values() if len(v) > 1)))


def main():
    clean = build_geometry()
    build_state_lookup(clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
