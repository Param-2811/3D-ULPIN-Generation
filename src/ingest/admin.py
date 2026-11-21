"""Which revenue village, sub-district, district and state a point lies in, with their official codes.

Source: datta07/INDIAN-SHAPEFILES (MIT), village polygons carrying Census 2011 codes (stcode11, dtcode11, sdtcode11,
vilcode11) and LGD codes. ULPINs are issued per revenue village, so this is the hierarchy a real parent ULPIN is
derived from. Caveat from the source: 2019 boundaries, "verify for official or legal purposes".

placeholder_ulpin(): 14 digits shaped like the real one: state(2) + district(3) + village census code(6) + a 3-digit
parcel sequence hashed from the building's position inside the village. Same building -> same number; different
buildings in one village share the first 11 digits. It is a stand-in until DoLR issues the real number.
Usage: python -m src.ingest.admin 22.55047 72.93107
"""
import argparse
import hashlib
import logging
from pathlib import Path

from shapely.geometry import Point

log = logging.getLogger("admin")
VILLAGES = Path("data/raw/india_admin/gujarat_villages_lite.gpkg")
_layer = None


def _load():
    global _layer
    if _layer is None and VILLAGES.exists():
        import geopandas as gpd
        g = gpd.read_file(VILLAGES)
        _layer = (g, g.sindex)
        log.info("read %s (%d villages)", VILLAGES, len(g))
    return _layer


def village_at(lat: float, lon: float) -> dict | None:
    """Official codes and names for the village containing the point, or None if outside the loaded layer."""
    lay = _load()
    if lay is None:
        return None
    g, sidx = lay
    pt = Point(lon, lat)
    cand = g.iloc[sidx.query(pt, predicate="within")]
    if cand.empty:
        return None
    r = cand.iloc[0]
    return {"state": r.state, "state_code": r.stcode11, "district": r.district, "district_code": r.dtcode11,
            "subdistrict": r.subdistrict, "subdistrict_code": r.sdtcode11 or None,
            "village": r.village, "village_code": r.vilcode11 or None, "village_lgd": int(r.vil_lgd) if r.vil_lgd else None,
            "source": "Census 2011 codes via datta07/INDIAN-SHAPEFILES (2019 boundaries)"}


def placeholder_ulpin(lat: float, lon: float, village: dict | None = None) -> tuple[str, str]:
    """(ulpin, how): village-structured when the point falls in a known village, else the plain location form."""
    v = village or village_at(lat, lon)
    if v and v["village_code"] and len(v["village_code"]) == 6:
        seq = int(hashlib.sha1(f"{lat:.5f},{lon:.5f}".encode()).hexdigest(), 16) % 1000
        return f"{v['state_code']}{v['district_code']}{v['village_code']}{seq:03d}", f"state {v['state_code']} + district {v['district_code']} + village {v['village_code']} ({v['village']}) + parcel seq {seq:03d}"
    return f"{round((lat + 90) * 1e5):07d}{round((lon + 180) * 1e5):07d}"[:14], "location-based (no village polygon here)"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("lat", type=float); p.add_argument("lon", type=float)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    v = village_at(a.lat, a.lon)
    print(v or "outside the loaded village layer")
    u, how = placeholder_ulpin(a.lat, a.lon, v)
    print("placeholder ULPIN:", u, "=", how)


if __name__ == "__main__":
    main()
