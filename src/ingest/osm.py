"""Any building in India (or anywhere) from OpenStreetMap: search a place name, then take the outline under a point.

Free, no key. Nominatim geocodes; Overpass returns the building polygon and its tags
(building type, name, building:levels, height). Tags are volunteer-entered: label them 'osm', never 'official'.
Usage: python -m src.ingest.osm "Prerna Arbour Complex, Ahmedabad"      # search, then outline of the first hit
       python -m src.ingest.osm --at 23.0339 72.5619
"""
import argparse
import json
import logging
import warnings
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import Point, Polygon, mapping

log = logging.getLogger("osm")
UA = {"User-Agent": "ulpin3d-hackathon (SIH 26011; educational)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]


def _get(url: str, timeout=40) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def placeholder_ulpin(lat: float, lon: float) -> str:
    """Demo stand-in for the official 14-digit ULPIN, which only DoLR/state systems can issue.
    Derived from location like the real one (7 digits from latitude, 7 from longitude, ~1 m grid),
    so the same building always gets the same number. Never present it as an official ID."""
    return f"{round((lat + 90) * 1e5):07d}{round((lon + 180) * 1e5):07d}"[:14]


def _admin(lat: float, lon: float) -> dict:
    """Village hierarchy + a placeholder ULPIN shaped like the real one when the point is in a known village."""
    from src.ingest.admin import village_at, placeholder_ulpin as structured
    v = village_at(lat, lon)
    u, how = structured(lat, lon, v)
    return {"placeholder_ulpin": u, "placeholder_how": how, "admin": v}


def geocode(q: str, limit: int = 5) -> list[dict]:
    d = _get(f"{NOMINATIM}?{urllib.parse.urlencode({'q': q, 'format': 'json', 'limit': limit})}")
    return [{"name": x["display_name"], "lat": float(x["lat"]), "lon": float(x["lon"])} for x in d]


CACHE = Path("data/raw/osm/buildings_cache.geojson")
_cache = None


def _load_cache():
    """Local building cache from src/ingest/osm_extract.py: instant and offline for the cities it covers."""
    global _cache
    if _cache is None and CACHE.exists():
        import geopandas as gpd
        g = gpd.read_file(CACHE)
        # covered area = one box per cached city (volunteer outlines can be self-crossing, so never union them)
        from shapely.geometry import box
        boxes = [box(*g[g.city == c].total_bounds) for c in g.city.unique()]
        _cache = (g, g.sindex, boxes)
        log.info("read %s (%d cached buildings, %d cities)", CACHE, len(g), len(boxes))
    return _cache


def _from_cache(lat: float, lon: float, radius_m: int) -> dict | None:
    c = _load_cache()
    if c is None:
        return None
    g, sidx, boxes = c
    pt = Point(lon, lat)
    if not any(b.contains(pt) for b in boxes):
        return None                      # outside the cached cities: caller goes online
    deg = radius_m / 111_000
    hits = g.iloc[sidx.query(pt.buffer(deg), predicate="intersects")]
    if hits.empty:
        return {}                        # inside a cached city but nothing mapped here: do not go online
    # 40 m is tiny, so degree distances rank correctly here; the closest (or containing, distance 0) wins
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = hits.iloc[(hits.geometry.distance(pt)).argmin()]
    clean = lambda v: None if v is None or (isinstance(v, float) and v != v) else v
    lv = re.match(r"\d+", str(clean(r["levels"]) or ""))
    h = re.match(r"[\d.]+", str(clean(r["height"]) or ""))
    cen = r.geometry.centroid
    return {"osm_id": int(r["osm_id"]), "geometry": mapping(r.geometry), "name": clean(r["name"]), "building": clean(r["building"]),
            **_admin(cen.y, cen.x),
            "levels": int(lv.group()) if lv else None, "height_m": float(h.group()) if h else None,
            "address": clean(r["address"]), "source": f"OpenStreetMap way {int(r['osm_id'])} (local extract)"}


def building_at(lat: float, lon: float, radius_m: int = 40) -> dict | None:
    """The building polygon containing the point, else the nearest one within radius_m. Cache first, then Overpass."""
    cached = _from_cache(lat, lon, radius_m)
    if cached is not None:
        return cached or None
    q = f'[out:json][timeout:20];way["building"](around:{radius_m},{lat},{lon});out geom;'
    last = None
    for base in OVERPASS:
        try:
            d = _get(f"{base}?{urllib.parse.urlencode({'data': q})}", timeout=25)
            break
        except Exception as e:      # ponytail: the public mirrors time out under load; try the next one
            last = e
    else:
        raise RuntimeError(f"OpenStreetMap (Overpass) unavailable: {last}")
    pt = Point(lon, lat)
    best = None
    for w in d.get("elements", []):
        pts = [(n["lon"], n["lat"]) for n in w.get("geometry", [])]
        if len(pts) < 4 or pts[0] != pts[-1]:
            continue
        poly = Polygon(pts)
        dist = 0.0 if poly.contains(pt) else poly.distance(pt)
        if best is None or dist < best[0]:
            best = (dist, w, poly)
    if best is None:
        return None
    _, w, poly = best
    t = w.get("tags", {})
    lv = re.match(r"\d+", t.get("building:levels", "") or "")
    h = re.match(r"[\d.]+", t.get("height", "") or "")
    c = poly.centroid
    return {"osm_id": w["id"], "geometry": mapping(poly), "name": t.get("name"), "building": t.get("building"),
            **_admin(c.y, c.x),
            "levels": int(lv.group()) if lv else None, "height_m": float(h.group()) if h else None,
            "address": " ".join(v for k, v in t.items() if k.startswith("addr:")) or None,
            "source": f"OpenStreetMap way {w['id']}"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="?")
    p.add_argument("--at", nargs=2, type=float, metavar=("LAT", "LON"))
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if a.at:
        lat, lon = a.at
    elif a.query:
        hits = geocode(a.query)
        if not hits:
            sys.exit(f"no place found for {a.query!r}")
        log.info("read %d places; using %s", len(hits), hits[0]["name"])
        lat, lon = hits[0]["lat"], hits[0]["lon"]
    else:
        sys.exit("give a query or --at LAT LON")
    b = building_at(lat, lon)
    if not b:
        sys.exit("no building outline in OpenStreetMap within 40 m of that point")
    log.info("processed 1 building: %s (%s), levels %s, height %s, %s", b["name"], b["building"], b["levels"], b["height_m"], b["source"])
    print(json.dumps({k: v for k, v in b.items() if k != "geometry"}, indent=2))


if __name__ == "__main__":
    main()
