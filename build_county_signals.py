#!/usr/bin/env python3
"""
build_county_signals.py  --  Kimley-Horn Nuclear Task Force
================================================================
Regenerates the county-resolvable favorability signals consumed by index.html:

    county_data.json    energy_community: FIPS qualifying as IRA coal-closure
                        energy communities (bonus tax credits + transmission/
                        workforce from retired coal = siting-favorable)
                        nuclear_host:     FIPS already hosting an operating or
                        pipeline reactor (demonstrated siting precedent)
    county_names.json   FIPS -> [county name, state] for every U.S. county

SOURCES
-------
  * IRA energy communities (coal closure):
      NETL ArcGIS  .../Hosted/2024_Coal_Closure_Energy_Communities/FeatureServer/0
      (reduced to distinct county FIPS via geoid_county_2020)
  * Reactor host counties: point-in-county of operating-fleet + pipeline reactor
      coordinates (maintained in the fleet/pipeline tools) against us-atlas
      counties-10m. Update REACTORS below as the pipeline changes.
  * County names: Census 2020 national county file.

REQUIREMENTS
------------
    pip install shapely            (see requirements.txt)

This is a BUILD-TIME tool; the weekly Action does not run it. Re-run when the
energy-community dataset updates or the reactor pipeline changes, then commit.

    python build_county_signals.py
"""

import csv, json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DATA  = os.path.join(HERE, "county_data.json")
OUT_NAMES = os.path.join(HERE, "county_names.json")

NETL = ("https://arcgis.netl.doe.gov/server/rest/services/Hosted/"
        "2024_Coal_Closure_Energy_Communities/FeatureServer/0/query")
COUNTIES_10M = "https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"
CENSUS_COUNTIES = "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"

# Operating-fleet + pipeline reactor sites (name, lat, lon). Keep in sync with
# the fleet/pipeline tools. Duplicates at one site are fine (deduped by county).
REACTORS = [{"name": "Farley 1","lat": 31.22,"lon": -85.11},{"name": "Farley 2","lat": 31.22,"lon": -85.11},{"name": "Browns Ferry 1","lat": 34.7,"lon": -87.12},{"name": "Browns Ferry 2","lat": 34.7,"lon": -87.12},{"name": "Browns Ferry 3","lat": 34.7,"lon": -87.12},{"name": "Arkansas Nuclear 1","lat": 35.31,"lon": -93.23},{"name": "Arkansas Nuclear 2","lat": 35.31,"lon": -93.23},{"name": "Palo Verde 1","lat": 33.39,"lon": -112.86},{"name": "Palo Verde 2","lat": 33.39,"lon": -112.86},{"name": "Palo Verde 3","lat": 33.39,"lon": -112.86},{"name": "Diablo Canyon 1","lat": 35.21,"lon": -120.86},{"name": "Diablo Canyon 2","lat": 35.21,"lon": -120.86},{"name": "Millstone 2","lat": 41.31,"lon": -72.17},{"name": "Millstone 3","lat": 41.31,"lon": -72.17},{"name": "St. Lucie 1","lat": 27.35,"lon": -80.25},{"name": "St. Lucie 2","lat": 27.35,"lon": -80.25},{"name": "Turkey Point 3","lat": 25.44,"lon": -80.33},{"name": "Turkey Point 4","lat": 25.44,"lon": -80.33},{"name": "Hatch 1","lat": 31.93,"lon": -82.34},{"name": "Hatch 2","lat": 31.93,"lon": -82.34},{"name": "Vogtle 1","lat": 33.14,"lon": -81.76},{"name": "Vogtle 2","lat": 33.14,"lon": -81.76},{"name": "Vogtle 3","lat": 33.14,"lon": -81.76},{"name": "Vogtle 4","lat": 33.14,"lon": -81.76},{"name": "Braidwood 1","lat": 41.24,"lon": -88.23},{"name": "Braidwood 2","lat": 41.24,"lon": -88.23},{"name": "Byron 1","lat": 42.08,"lon": -89.28},{"name": "Byron 2","lat": 42.08,"lon": -89.28},{"name": "Clinton","lat": 40.17,"lon": -88.83},{"name": "Dresden 2","lat": 41.39,"lon": -88.27},{"name": "Dresden 3","lat": 41.39,"lon": -88.27},{"name": "LaSalle 1","lat": 41.24,"lon": -88.67},{"name": "LaSalle 2","lat": 41.24,"lon": -88.67},{"name": "Quad Cities 1","lat": 41.73,"lon": -90.31},{"name": "Quad Cities 2","lat": 41.73,"lon": -90.31},{"name": "Wolf Creek","lat": 38.24,"lon": -95.69},{"name": "River Bend","lat": 30.76,"lon": -91.33},{"name": "Waterford 3","lat": 30.0,"lon": -90.47},{"name": "Calvert Cliffs 1","lat": 38.43,"lon": -76.44},{"name": "Calvert Cliffs 2","lat": 38.43,"lon": -76.44},{"name": "D.C. Cook 1","lat": 41.98,"lon": -86.56},{"name": "D.C. Cook 2","lat": 41.98,"lon": -86.56},{"name": "Fermi 2","lat": 41.96,"lon": -83.26},{"name": "Monticello","lat": 45.33,"lon": -93.85},{"name": "Prairie Island 1","lat": 44.62,"lon": -92.63},{"name": "Prairie Island 2","lat": 44.62,"lon": -92.63},{"name": "Grand Gulf","lat": 32.0,"lon": -91.05},{"name": "Callaway","lat": 38.76,"lon": -91.78},{"name": "Brunswick 1","lat": 33.96,"lon": -78.01},{"name": "Brunswick 2","lat": 33.96,"lon": -78.01},{"name": "McGuire 1","lat": 35.43,"lon": -80.95},{"name": "McGuire 2","lat": 35.43,"lon": -80.95},{"name": "Shearon Harris","lat": 35.63,"lon": -78.96},{"name": "Cooper","lat": 40.36,"lon": -95.64},{"name": "Seabrook","lat": 42.9,"lon": -70.85},{"name": "Hope Creek","lat": 39.47,"lon": -75.54},{"name": "Salem 1","lat": 39.46,"lon": -75.54},{"name": "Salem 2","lat": 39.46,"lon": -75.54},{"name": "FitzPatrick","lat": 43.52,"lon": -76.4},{"name": "Ginna","lat": 43.28,"lon": -77.31},{"name": "Nine Mile Pt 1","lat": 43.52,"lon": -76.41},{"name": "Nine Mile Pt 2","lat": 43.52,"lon": -76.41},{"name": "Davis-Besse","lat": 41.6,"lon": -83.09},{"name": "Perry 1","lat": 41.8,"lon": -81.14},{"name": "Beaver Valley 1","lat": 40.62,"lon": -80.43},{"name": "Beaver Valley 2","lat": 40.62,"lon": -80.43},{"name": "Limerick 1","lat": 40.22,"lon": -75.59},{"name": "Limerick 2","lat": 40.22,"lon": -75.59},{"name": "Peach Bottom 2","lat": 39.76,"lon": -76.27},{"name": "Peach Bottom 3","lat": 39.76,"lon": -76.27},{"name": "Susquehanna 1","lat": 41.09,"lon": -76.15},{"name": "Susquehanna 2","lat": 41.09,"lon": -76.15},{"name": "Catawba 1","lat": 35.05,"lon": -81.07},{"name": "Catawba 2","lat": 35.05,"lon": -81.07},{"name": "Oconee 1","lat": 34.79,"lon": -82.9},{"name": "Oconee 2","lat": 34.79,"lon": -82.9},{"name": "Oconee 3","lat": 34.79,"lon": -82.9},{"name": "Robinson 2","lat": 34.4,"lon": -80.16},{"name": "Summer","lat": 34.3,"lon": -81.32},{"name": "Sequoyah 1","lat": 35.23,"lon": -85.09},{"name": "Sequoyah 2","lat": 35.23,"lon": -85.09},{"name": "Watts Bar 1","lat": 35.6,"lon": -84.79},{"name": "Watts Bar 2","lat": 35.6,"lon": -84.79},{"name": "Comanche Peak 1","lat": 32.3,"lon": -97.79},{"name": "Comanche Peak 2","lat": 32.3,"lon": -97.79},{"name": "South Texas 1","lat": 28.8,"lon": -96.05},{"name": "South Texas 2","lat": 28.8,"lon": -96.05},{"name": "North Anna 1","lat": 38.06,"lon": -77.79},{"name": "North Anna 2","lat": 38.06,"lon": -77.79},{"name": "Surry 1","lat": 37.17,"lon": -76.7},{"name": "Surry 2","lat": 37.17,"lon": -76.7},{"name": "Columbia Generating","lat": 46.47,"lon": -119.33},{"name": "Point Beach 1","lat": 44.28,"lon": -87.54},{"name": "Point Beach 2","lat": 44.28,"lon": -87.54},{"name": "Palisades Nuclear Plant","lat": 42.3222,"lon": -86.3153},{"name": "Crane Clean Energy (TMI-1)","lat": 40.1531,"lon": -76.7247},{"name": "Duane Arnold","lat": 42.1006,"lon": -91.7776},{"name": "Kewaunee","lat": 44.343,"lon": -87.536},{"name": "TerraPower Natrium","lat": 41.7927,"lon": -110.5377},{"name": "X-energy Xe-100 (Dow)","lat": 28.4141,"lon": -96.7133},{"name": "Kairos Hermes 1","lat": 35.931,"lon": -84.31},{"name": "Kairos Hermes 2","lat": 35.933,"lon": -84.315},{"name": "BWXT BANR","lat": 41.14,"lon": -104.82},{"name": "TVA Clinch River","lat": 35.891,"lon": -84.389},{"name": "Holtec Pioneer SMR","lat": 42.325,"lon": -86.318},{"name": "Cascade (Amazon)","lat": 46.55,"lon": -119.25},{"name": "Duke Belews Creek","lat": 36.244,"lon": -80.059},{"name": "Dominion North Anna","lat": 38.06,"lon": -77.79},{"name": "AEP Indiana","lat": 37.93,"lon": -87.12},{"name": "Creekstone Delta","lat": 39.352,"lon": -112.577},{"name": "Google/Elementl Power","lat": 39.5,"lon": -98.35},{"name": "Holtec Oyster Creek","lat": 39.814,"lon": -74.206},{"name": "NANO Nuclear KRONOS","lat": 40.116,"lon": -88.243},{"name": "V.C. Summer 2&3","lat": 34.296,"lon": -81.32},{"name": "Fermi America","lat": 35.199,"lon": -101.845},{"name": "NYPA New Nuclear","lat": 42.65,"lon": -73.75},{"name": "Valar Atomics","lat": 41.79,"lon": -110.53},{"name": "Aalo Atomics","lat": 43.515,"lon": -112.945},{"name": "Antares MARK-0","lat": 43.518,"lon": -112.948},{"name": "Oklo Aurora","lat": 43.52,"lon": -112.95},{"name": "Oklo Pluto","lat": 43.522,"lon": -112.952},{"name": "Atomic Alchemy VIPR","lat": 43.524,"lon": -112.954},{"name": "Radiant Kaleidos","lat": 43.526,"lon": -112.956},{"name": "Deep Fission DFBR-1","lat": 37.34,"lon": -95.262},{"name": "Last Energy PWR-20","lat": 30.628,"lon": -96.464},{"name": "Natura MSR-1","lat": 32.449,"lon": -99.733},{"name": "Terrestrial TETRA","lat": 43.528,"lon": -112.958},{"name": "Westinghouse eVinci","lat": 43.534,"lon": -112.964},{"name": "MARVEL","lat": 43.53,"lon": -112.96},{"name": "Project Pele","lat": 43.5154,"lon": -112.9452},{"name": "Janus Program","lat": 64.663,"lon": -147.102},{"name": "Amazon-Talen Susquehanna","lat": 41.095,"lon": -76.155},{"name": "Meta-Constellation","lat": 41.24,"lon": -88.23},{"name": "Switch-Oklo (12 GW)","lat": 36.04,"lon": -115.17},{"name": "ENTRA1-NuScale (6 GW)","lat": 35.75,"lon": -84.0}]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "KH-NTF-county-build/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def energy_community_counties():
    qs = urllib.parse.urlencode({
        "where": "1=1", "outFields": "geoid_county_2020",
        "returnGeometry": "false", "returnDistinctValues": "true",
        "f": "json", "resultRecordCount": "5000",
    })
    j = json.loads(get(NETL + "?" + qs))
    out = set()
    for f in j.get("features", []):
        fips = f["attributes"].get("geoid_county_2020")
        if fips:
            out.add(str(fips).zfill(5))
    return sorted(out)


def county_names():
    out = {}
    for row in csv.DictReader(get(CENSUS_COUNTIES).splitlines(), delimiter="|"):
        fips = (row["STATEFP"] + row["COUNTYFP"]).zfill(5)
        out[fips] = [row["COUNTYNAME"], row["STATE"]]
    return out


def host_counties():
    from shapely.geometry import shape, Point
    from shapely.prepared import prep
    topo = json.loads(get(COUNTIES_10M))
    arcs = topo["arcs"]; tr = topo.get("transform")

    def dec(i):
        rev = i < 0; a = arcs[~i] if rev else arcs[i]; pts = []; x = y = 0
        for p in a:
            if tr:
                x += p[0]; y += p[1]
                pts.append([x*tr["scale"][0]+tr["translate"][0], y*tr["scale"][1]+tr["translate"][1]])
            else:
                pts.append(list(p))
        return pts[::-1] if rev else pts

    def ring(al):
        c = []
        for ai in al:
            seg = dec(ai); c.extend(seg if not c else seg[1:])
        return c

    def poly(rs):
        return [r for r in (ring(x) for x in rs) if len(r) >= 4]

    geoms = {}
    for g in topo["objects"]["counties"]["geometries"]:
        gid = str(g.get("id")).zfill(5)
        try:
            if g["type"] == "Polygon":
                co = poly(g["arcs"])
                if co: geoms[gid] = shape({"type": "Polygon", "coordinates": co}).buffer(0)
            elif g["type"] == "MultiPolygon":
                co = [p for p in (poly(pp) for pp in g["arcs"]) if p]
                if co: geoms[gid] = shape({"type": "MultiPolygon", "coordinates": co}).buffer(0)
        except Exception:
            continue
    prepared = {f: prep(g) for f, g in geoms.items()}

    host = {}
    for r in REACTORS:
        pt = Point(r["lon"], r["lat"]); nm = r["name"].rstrip(" 0123456789").strip() or r["name"]
        found = None
        for f, pg in prepared.items():
            if pg.contains(pt): found = f; break
        if not found:  # coastal sites land just offshore -> nearest county within ~25km
            best, bd = None, 9e9
            for f, g in geoms.items():
                d = g.distance(pt)
                if d < bd: bd, best = d, f
            if best and bd < 0.25: found = best
        if found:
            host.setdefault(found, [])
            if nm not in host[found]: host[found].append(nm)
    return host


def main():
    try:
        from shapely.geometry import shape  # noqa: F401
    except ImportError:
        sys.exit("Missing dependency 'shapely'. Run: pip install -r requirements.txt")
    ec = energy_community_counties()
    host = host_counties()
    names = {f: v for f, v in sorted(county_names().items())}
    json.dump({
        "_comment": "COUNTY SIGNAL LAYER — energy_community = IRA coal-closure energy communities (siting-favorable: bonus credits, transmission, workforce). nuclear_host = counties already hosting an operating/pipeline reactor. Counties absent here inherit their state regime. Regenerate with build_county_signals.py.",
        "energy_community": ec,
        "nuclear_host": {f: host[f] for f in sorted(host)},
    }, open(OUT_DATA, "w"))
    json.dump({"_comment": "FIPS -> [county name, state abbr] (Census 2020).",
               "names": names}, open(OUT_NAMES, "w"))
    print("wrote county_data.json (%d energy-community, %d host counties) and county_names.json (%d)"
          % (len(ec), len(host), len(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
