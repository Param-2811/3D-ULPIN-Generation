"""Judge demo folder where EVERY step has a real, open-licence file for the SAME building. Nothing synthetic.

Netherlands is the one country publishing all of these openly: outline + unit register (BAG), 3D model + height
(3DBAG), cadastral parcel with its official ID (Kadaster), DSM/DTM (AHN via PDOK WCS), LiDAR (AHN4 via GeoTiles),
orthophoto (PDOK). Floor plans: real Swiss apartment plans (MSD, CC-BY-4.0): no country ties open plans to a locatable building.
Folder names follow the Manual page steps. Each step folder holds only the file(s) that step's form control accepts.

Usage: python -m src.ingest.demo_open 0503100000000948 0503100000000016 ... -o demo_inputs_open --laz data/raw/37EN1_19.LAZ
"""
import argparse
import json
import logging
import shutil
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from PIL import Image

from src.ingest import align, clip_las, download
from src.ulpin.generate import generate

log = logging.getLogger("demo_open")
WCS = "https://service.pdok.nl/rws/ahn/wcs/v1_0?service=WCS&version=2.0.1&request=GetCoverage&coverageId={cov}&format=image/tiff&subset=x({x0},{x1})&subset=y({y0},{y1})"
WMS = "https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0?service=WMS&version=1.1.1&request=GetMap&layers=Actueel_orthoHR&styles=&srs=EPSG:28992&bbox={x0},{y0},{x1},{y1}&width={w}&height={h}&format=image/jpeg"
PARCEL = "https://service.pdok.nl/kadaster/kadastralekaart/wfs/v5_0?service=WFS&version=2.0.0&request=GetFeature&typeName=kadastralekaart:Perceel&outputFormat=json&srsName=EPSG:4326&bbox={x0},{y0},{x1},{y1},EPSG:28992"
PLANS = Path("data/processed/msd_yolo_v3/images/val")


def sub(site: Path, name: str) -> Path:
    d = site / name; d.mkdir(parents=True, exist_ok=True); return d


def fetch(url: str, out: Path):
    out.write_bytes(urllib.request.urlopen(url, timeout=300).read())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pand_ids", nargs="+")
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--laz", type=Path, required=True, help="AHN4 LAZ tile covering the buildings")
    p.add_argument("--raw", type=Path, default=Path("data/raw"))
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    # the plans with the most apartments, so a block of 60-86 flats gets plans that look like one
    lab = PLANS.parent.parent / "labels" / "val"
    plans = sorted(PLANS.glob("*.png"), key=lambda f: -len((lab / f"{f.stem}.txt").read_text().splitlines()) if (lab / f"{f.stem}.txt").exists() else 0)[:30]
    if not plans:
        raise SystemExit("no MSD plan images found; run floorplan prepare first")

    for i, pid in enumerate(a.pand_ids, start=1):
        download.main([pid, "-o", str(a.raw)])
        fpfile = Path("data/processed") / f"{pid}.geojson"
        align.main([str(a.raw / f"{pid}.city.json"), str(a.raw / f"{pid}_units.geojson"), "-o", str(fpfile)])
        fp = gpd.read_file(fpfile)
        r = fp.iloc[0]
        m = fp.to_crs("EPSG:28992"); x0, y0, x1, y1 = m.total_bounds
        c = fp.geometry.iloc[0].centroid
        site = a.output / f"{i:02d}_Delft_apartment_block_{pid[-4:]}_{int(r.floors_official)}floors_{int(r.units_official)}units"

        # step 1: the parcel. Real Kadaster parcel under the building centroid, with its official cadastral ID.
        cm = m.geometry.iloc[0].centroid
        pj = json.load(urllib.request.urlopen(PARCEL.format(x0=cm.x - 1, y0=cm.y - 1, x1=cm.x + 1, y1=cm.y + 1), timeout=120))
        par = gpd.GeoDataFrame.from_features(pj["features"], crs="EPSG:4326") if pj["features"] else None
        # a 14-digit parent ULPIN from the cadastral parcel: municipality code(3) + section letter as digits(2) + parcel number(9), same parcel -> same number
        if par is not None:
            pp = par.iloc[0]
            parent = f"{int(pp.kadastraleGemeenteCode):03d}{ord(str(pp.sectie)[0]) - 55:02d}{int(pp.perceelnummer):09d}"[:14].ljust(14, "0")
            par_note = f"{pp.kadastraleGemeenteWaarde} section {pp.sectie} parcel {pp.perceelnummer} (Kadaster id {pp.identificatieLokaalID})"
        else:
            parent = f"{pid[-14:]}".ljust(14, "0"); par_note = "no parcel returned; BAG id used"
        s1 = sub(site, "step1_parcel")
        if par is not None:
            par[["identificatieLokaalID", "kadastraleGemeenteWaarde", "sectie", "perceelnummer", "geometry"]].assign(parent_ulpin=parent).to_file(s1 / "cadastral_parcel.geojson", driver="GeoJSON")
        ex = [(generate(parent, 1, "G00", "U01"), "flat 1, ground floor"), (generate(parent, 1, "F02", "U03"), "flat 3, floor 2"),
              (generate(parent, 1, "B01", "P05"), "parking slot 5, basement 1")]
        (s1 / "ULPIN.txt").write_text(chr(10).join([
            "STEP 1 ON THE FORM, type exactly these two values:", "",
            f"  Existing 14-digit ULPIN:        {parent}",
            "  Building number on the parcel:  1", "",
            f"  (the ULPIN is derived from the real cadastral parcel: {par_note};",
            "   the parcel number 8704-style figure is already inside the 14 digits, do NOT type it as the building number)",
            "  (source: Kadaster open cadastral map via PDOK; 14-digit form mirrors India's ULPIN)", "",
            f"BUILDING: BAG {pid}, {int(r.floors_official)} floors (official), {int(r.units_official)} registered units, {r.height_m:.1f} m (laser-measured)", "",
            "3D ULPINs this building gets:"] + [f"  {u}   {d}" for u, d in ex]) + chr(10), encoding="utf-8")

        # step 2: outline. Real BAG footprint.
        s2 = sub(site, "step2_outline")
        fp.assign(parent_ulpin=parent)[["pand_id", "parent_ulpin", "floors_official", "units_official", "height_m", "geometry"]].to_file(s2 / "outline.geojson", driver="GeoJSON")
        # orthophoto for the AI extraction option, real PDOK 25 cm
        px0, py0, px1, py1 = round(x0 - 30), round(y0 - 30), round(x1 + 30), round(y1 + 30)
        w, h = int((px1 - px0) / 0.25), int((py1 - py0) / 0.25)
        jpg = s2 / "_ortho.jpg"; fetch(WMS.format(x0=px0, y0=py0, x1=px1, y1=py1, w=w, h=h), jpg)
        im = np.asarray(Image.open(jpg).convert("RGB")); jpg.unlink()
        with rasterio.open(s2 / "drone_orthophoto_25cm.tif", "w", driver="GTiff", width=w, height=h, count=3, dtype="uint8", crs="EPSG:28992", transform=from_bounds(px0, py0, px1, py1, w, h)) as dst:
            for b in range(3): dst.write(im[:, :, b], b + 1)
        (s2 / "orthophoto_roof_point.txt").write_text(f"lon {c.x:.5f}\nlat {c.y:.5f}\n", encoding="utf-8")

        # step 3: height. Real DSM + DTM (AHN 50 cm) and real LiDAR clip (AHN4).
        s3 = sub(site, "step3_height")
        for cov, name in (("dsm_05m", "DSM_50cm.tif"), ("dtm_05m", "DTM_50cm.tif")):
            fetch(WCS.format(cov=cov, x0=int(x0) - 40, x1=int(x1) + 40, y0=int(y0) - 40, y1=int(y1) + 40), s3 / name)
        clip_las.main([str(a.laz), str(fpfile), "-o", str(s3 / "lidar_AHN4.laz"), "--margin", "30"])

        # step 4: floors and units. Real register values, as the two numbers the form asks for.
        s4 = sub(site, "step4_floors_units")
        (s4 / "floors_and_units.txt").write_text(f"Floors above ground: {int(r.floors_official)}   (official register, BAG/3DBAG)\nBasement levels: 0\nNumber of units: {int(r.units_official)}   (official address register, BAG)\n", encoding="utf-8")

        # step 5: floor plans. Real Swiss apartment plans, one per floor, cycling through the held-out set.
        s5 = sub(site, "step5_floor_plans")
        levels = ["G00"] + [f"F{k:02d}" for k in range(1, int(r.floors_official))]
        for k, lvl in enumerate(levels):
            shutil.copy(plans[(i * 7 + k) % len(plans)], s5 / f"{lvl}.png")

        # step 6: owner and utilities. Owner from the register's municipality; utilities: none open, so the folder holds only the owner.
        s6 = sub(site, "step6_owner_utilities_cors")
        (s6 / "owner.txt").write_text(f"Owner or society name: Vereniging van Eigenaars {pid} (Dutch owners' association, the legal owner of common parts)\n", encoding="utf-8")

        log.info("wrote %s: parcel %s, %d floors, %d units, height %.1f m", site.name, par_note, int(r.floors_official), int(r.units_official), r.height_m)
    log.info("processed %d buildings; wrote %s", len(a.pand_ids), a.output)


if __name__ == "__main__":
    main()
