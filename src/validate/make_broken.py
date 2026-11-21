"""Make a deliberately broken copy of a building so the demo can show the validator catching errors.

Breaks: one unit slid onto its neighbour (overlap), one pushed outside (containment), one deleted (gap),
one lifted off its slab (floating), one duplicated ID. Output name <id>-broken so the API lists it as a second building.
Usage: python -m src.validate.make_broken data/processed/<id>
"""
import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

import geopandas as gpd
from shapely import affinity

from src.validate.checks import run_checks

log = logging.getLogger(Path(__file__).stem)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prefix", type=Path, help="data/processed/<id> (no suffix)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    src = Path(str(a.prefix) + "_units3d.geojson")
    if not src.exists():
        sys.exit(f"input not found: {src}")
    out = Path(str(a.prefix) + "-broken")
    for suf in (".geojson", "_floors.geojson"):
        shutil.copy(str(a.prefix) + suf, str(out) + suf)

    u = gpd.read_file(src)
    m = u.to_crs(u.estimate_utm_crs())
    g1 = m[m.level_code == "F01"].index
    m.loc[g1[1], "geometry"] = affinity.translate(m.loc[g1[1], "geometry"], xoff=-3)
    m.loc[g1[3], "geometry"] = affinity.translate(m.loc[g1[3], "geometry"], yoff=8)
    m.loc[g1[6], "z_min"] += 1.0
    m.loc[g1[8], "ulpin"] = m.loc[g1[7], "ulpin"]
    m = m.drop(index=g1[10])
    broken = m.to_crs("EPSG:4326")
    broken.to_file(str(out) + "_units3d.geojson", driver="GeoJSON")

    floors = gpd.read_file(str(out) + "_floors.geojson")
    findings = run_checks(broken, floors)
    Path(str(out) + "_report.json").write_text(json.dumps({"units": len(broken), "levels": len(floors), "findings": findings}, indent=2), encoding="utf-8")
    log.info("processed %d units, introduced 5 faults, validator found %d findings: %s", len(broken), len(findings),
             sorted({f['check'] for f in findings}))
    log.info("wrote %s_units3d.geojson and %s_report.json", out, out)


if __name__ == "__main__":
    main()
