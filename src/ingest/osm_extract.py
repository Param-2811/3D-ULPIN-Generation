"""Cut every building inside one or more bounding boxes out of a Geofabrik .osm.pbf into a local GeoJSON cache.

Why: the public Overpass servers time out under load, which is fatal in a live demo. A one-time local
extract makes the map picker answer instantly and offline for the cities we cache.
Usage: python -m src.ingest.osm_extract data/raw/osm/western-zone-latest.osm.pbf -o data/raw/osm/buildings_cache.geojson \
           --bbox anand 22.50 72.88 22.62 73.02 --bbox ahmedabad 22.95 72.45 23.12 72.70
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import osmium

log = logging.getLogger(Path(__file__).stem)


class Buildings(osmium.SimpleHandler):
    def __init__(self, boxes):
        super().__init__()
        self.boxes = boxes
        self.features = []
        self.seen = 0

    def way(self, w):
        if "building" not in w.tags or not w.is_closed() or len(w.nodes) < 4:
            return
        self.seen += 1
        try:
            pts = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        lon, lat = pts[0]
        city = next((name for name, (s, wst, n, e) in self.boxes.items() if s <= lat <= n and wst <= lon <= e), None)
        if city is None:
            return
        t = dict(w.tags)
        self.features.append({"type": "Feature",
                              "properties": {"osm_id": w.id, "city": city, "name": t.get("name"), "building": t.get("building"),
                                             "levels": t.get("building:levels"), "height": t.get("height"),
                                             "address": " ".join(v for k, v in t.items() if k.startswith("addr:")) or None},
                              "geometry": {"type": "Polygon", "coordinates": [pts]}})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pbf", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--bbox", nargs=5, action="append", metavar=("NAME", "S", "W", "N", "E"), required=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not a.pbf.exists():
        sys.exit(f"input not found: {a.pbf}")
    boxes = {b[0]: tuple(map(float, b[1:])) for b in a.bbox}
    log.info("read %s; boxes %s", a.pbf, boxes)
    h = Buildings(boxes)
    h.apply_file(str(a.pbf), locations=True, idx="flex_mem")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps({"type": "FeatureCollection", "features": h.features}), encoding="utf-8")
    per = {c: sum(f["properties"]["city"] == c for f in h.features) for c in boxes}
    lv = sum(bool(f["properties"]["levels"]) for f in h.features)
    log.info("processed %d buildings in the extract, kept %d (%s), %d with a floor count; wrote %s", h.seen, len(h.features), per, lv, a.output)


if __name__ == "__main__":
    main()
