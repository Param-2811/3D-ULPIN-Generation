"""Download one real building from 3DBAG (3D model) and BAG (dwelling units) into data/raw/.

Usage: python -m src.ingest.download 0503100000000071 [more ids] -o data/raw
"""
import argparse
import json
import logging
import sys
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger(Path(__file__).stem)

BAG3D = "https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.{pid}"
BAG_WFS = "https://service.pdok.nl/lv/bag/wfs/v2_0"
# WFS 2.0 needs an XML filter; PDOK ignores CQL_FILTER silently.
FES = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo>'
       '<fes:ValueReference>pandidentificatie</fes:ValueReference><fes:Literal>{pid}</fes:Literal>'
       '</fes:PropertyIsEqualTo></fes:Filter>')


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def fetch_building(pid: str) -> dict:
    d = fetch_json(BAG3D.format(pid=pid))
    # The API splits one CityJSON document into "feature" + "metadata"; merge so the file stands alone.
    doc = d["metadata"]
    doc["CityObjects"] = d["feature"]["CityObjects"]
    doc["vertices"] = d["feature"]["vertices"]
    return doc


def fetch_units(pid: str) -> dict:
    q = urllib.parse.urlencode({"service": "WFS", "version": "2.0.0", "request": "GetFeature",
                                "typeName": "bag:verblijfsobject", "outputFormat": "json",
                                "count": 5000, "FILTER": FES.format(pid=pid)})
    return fetch_json(f"{BAG_WFS}?{q}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pand_ids", nargs="+", help="16-digit BAG pand identificatie")
    p.add_argument("-o", "--output", type=Path, default=Path("data/raw"))
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    a.output.mkdir(parents=True, exist_ok=True)

    for pid in a.pand_ids:
        if not (pid.isdigit() and len(pid) == 16):
            sys.exit(f"pand id must be 16 digits, got {pid!r}")
        log.info("read 3DBAG %s", pid)
        city = fetch_building(pid)
        attrs = city["CityObjects"][f"NL.IMBAG.Pand.{pid}"]["attributes"]
        log.info("read BAG units %s", pid)
        units = fetch_units(pid)
        n = len(units["features"])
        if n == 0:
            sys.exit(f"BAG returned no dwelling units for {pid}; cannot use it as demo building")
        res = sum(f["properties"]["gebruiksdoel"] == "woonfunctie" for f in units["features"])

        f1 = a.output / f"{pid}.city.json"
        f2 = a.output / f"{pid}_units.geojson"
        f1.write_text(json.dumps(city), encoding="utf-8")
        f2.write_text(json.dumps(units), encoding="utf-8")
        log.info("wrote %s (%d vertices) and %s", f1, len(city["vertices"]), f2)
        log.info("processed %s: floors=%s height_m=%.1f ground_m2=%.0f units=%d residential=%d roof=%s",
                 pid, attrs.get("b3_bouwlagen"), attrs["b3_h_dak_50p"] - attrs["b3_h_maaiveld"],
                 attrs["b3_opp_grond"], n, res, attrs.get("b3_dak_type"))


if __name__ == "__main__":
    main()
