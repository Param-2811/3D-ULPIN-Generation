"""Floor plan -> one polygon per apartment. YOLO-seg fine-tuned on MSD (Modified Swiss Dwellings, HuggingFace copy).

prepare: parquet -> YOLO dataset (struct_in image, one 'apartment' polygon = union of that apartment's areas)
train:   fine-tune yolov8n-seg (COCO pretrained) on it; reports mask mAP on the held-out test split
predict: image -> apartment polygons, placed onto a building footprint by mapping the plan's bounding box
         onto the footprint's minimum rotated rectangle (the 'building corners as matching points' step)

Usage:
  python -m src.models.floorplan prepare data/raw/msd -o data/processed/msd_yolo
  python -m src.models.floorplan train data/processed/msd_yolo/data.yaml -o data/processed/floorplan --epochs 30
  python -m src.models.floorplan predict data/processed/floorplan/weights/best.pt plan.png --footprint data/processed/<id>.geojson --level F01 -o units.geojson
"""
import argparse
import io
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger(Path(__file__).stem)


def _apartment_polys(row):
    """Union of area polygons per apartment id, in plan metres."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    groups = {}
    for pts, apt in zip(row["graph_out_geometry"], row["graph_out_apartment_id"]):
        if apt and len(pts) >= 3:
            groups.setdefault(apt, []).append(Polygon(pts).buffer(0))
    out = []
    for polys in groups.values():
        g = unary_union(polys).buffer(0.05).buffer(-0.05)   # close hairline gaps between rooms
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda p: p.area)
        if g.area > 5:
            out.append(g)
    return out


def prepare(raw: Path, out: Path):
    import pyarrow.parquet as pq
    from PIL import Image
    for split, files in {"train": sorted(raw.glob("train-*.parquet")), "val": sorted(raw.glob("test-*.parquet"))}.items():
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        n_img = n_apt = 0
        for f in files:
            # struct_x/struct_y are the pixel->metre axes of struct_in; full_x/full_y belong to full_out and differ for some plans.
            t = pq.read_table(f, columns=["plan_id", "struct_in", "graph_out_geometry", "graph_out_apartment_id", "struct_x", "struct_y"])
            for row in t.to_pylist():
                polys = _apartment_polys(row)
                if not polys:
                    continue
                im = Image.open(io.BytesIO(row["struct_in"]["bytes"])).convert("L")
                W, H = im.size
                # axes are quantised floats: derive the metre-per-pixel scale from the full range, not from one step
                sx, sy = row["struct_x"], row["struct_y"]
                x0, dx = sx[0], (sx[-1] - sx[0]) / (len(sx) - 1)
                y0, dy = sy[0], (sy[-1] - sy[0]) / (len(sy) - 1)
                # Plans sit small in the middle of a 512 canvas; crop to the drawn content so apartments are not tiny.
                import numpy as np
                ys, xs = np.nonzero(np.asarray(im) < 250)
                px = [((x - x0) / dx, (y - y0) / dy) for g in polys for x, y in g.exterior.coords]
                if len(xs) == 0:
                    continue
                cx0 = max(0, int(min(xs.min(), min(u for u, _ in px))) - 12)
                cy0 = max(0, int(min(ys.min(), min(v for _, v in px))) - 12)
                cx1 = min(W, int(max(xs.max(), max(u for u, _ in px))) + 12)
                cy1 = min(H, int(max(ys.max(), max(v for _, v in px))) + 12)
                im = im.crop((cx0, cy0, cx1, cy1))
                w, h = im.size
                lines = []
                for g in polys:
                    pts = [(((x - x0) / dx - cx0) / w, ((y - y0) / dy - cy0) / h) for x, y in g.exterior.coords]
                    pts = [(min(max(u, 0), 1), min(max(v, 0), 1)) for u, v in pts]
                    lines.append("0 " + " ".join(f"{u:.5f} {v:.5f}" for u, v in pts))
                name = f"{row['plan_id']}"
                im.save(out / "images" / split / f"{name}.png")
                (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
                n_img += 1
                n_apt += len(lines)
            log.info("%s: read %s -> %d plans, %d apartments so far", split, f.name, n_img, n_apt)
    (out / "data.yaml").write_text(f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: apartment\n")
    log.info("wrote %s", out / "data.yaml")


def train(data_yaml: Path, out: Path, epochs: int, imgsz: int = 512, base: str = "yolov8n-seg.pt"):
    import shutil
    from ultralytics import YOLO
    model = YOLO(base)
    # Ultralytics nests a relative `project` under runs/segment/, so read back its real save_dir.
    # No mosaic: it tiles four plans at quarter size and destroys thin walls. Flips are safe for floor plans.
    # workers=2: each dataloader worker is a full Python process on Windows; the default 8 exhausted 16 GB of RAM.
    model.train(data=str(data_yaml), epochs=epochs, imgsz=imgsz, batch=16, device=0, project=str(out.parent.resolve()),
                name=out.name, exist_ok=True, plots=True, verbose=False, mosaic=0.0, flipud=0.5, fliplr=0.5, degrees=0.0,
                workers=2)
    best = Path(model.trainer.save_dir) / "weights" / "best.pt"
    (out / "weights").mkdir(parents=True, exist_ok=True)
    if best.resolve() != (out / "weights" / "best.pt").resolve():
        shutil.copy(best, out / "weights" / "best.pt")
    return evaluate(out / "weights" / "best.pt", data_yaml, out, imgsz, epochs)


def evaluate(weights: Path, data_yaml: Path, out: Path, imgsz: int = 512, epochs=None):
    """Honest score on the held-out split: mask mAP (how well predicted outlines overlap the true ones)."""
    from ultralytics import YOLO
    metrics = YOLO(str(weights)).val(data=str(data_yaml), imgsz=imgsz, device=0, plots=False, verbose=False)
    rep = {"mask_mAP50": round(float(metrics.seg.map50), 3), "mask_mAP50-95": round(float(metrics.seg.map), 3),
           "mask_precision": round(float(metrics.seg.mp), 3), "mask_recall": round(float(metrics.seg.mr), 3),
           "box_mAP50": round(float(metrics.box.map50), 3), "epochs": epochs, "weights": str(weights)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, indent=2))
    return rep


def predict(weights: Path, image: Path, footprint, level: str):
    """Apartment polygons from one plan image, mapped onto the footprint (EPSG:4326 in, 4326 out)."""
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import Polygon
    from ultralytics import YOLO
    res = YOLO(str(weights)).predict(str(image), imgsz=512, conf=0.25, verbose=False)[0]
    if res.masks is None:
        return gpd.GeoDataFrame(columns=["level_code", "conf", "geometry"], geometry="geometry", crs="EPSG:4326")
    h, w = res.orig_shape
    pix = [Polygon(seg).buffer(0) for seg in res.masks.xy if len(seg) >= 3]
    # a self-crossing mask outline splits into parts after buffer(0); keep the largest
    pix = [max(p.geoms, key=lambda g: g.area) if p.geom_type == "MultiPolygon" else p for p in pix if not p.is_empty]
    m = footprint.to_crs(footprint.estimate_utm_crs())
    rect = m.geometry.iloc[0].minimum_rotated_rectangle
    c = list(rect.exterior.coords)[:4]
    # image corners (0,0),(w,0),(w,h),(0,h) -> rectangle corners; solve the affine with 3 point pairs
    src = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1]], dtype=float)
    dst = np.array(c[:3], dtype=float)
    A = np.linalg.solve(src, dst)            # rows: coefficients for x and y
    mapped = [Polygon(np.c_[np.array(p.exterior.coords), np.ones(len(p.exterior.coords))] @ A).intersection(m.geometry.iloc[0])
              for p in pix]
    g = gpd.GeoDataFrame({"level_code": level, "conf": [float(x) for x in res.boxes.conf], "geometry": mapped}, crs=m.crs)
    return g[~g.geometry.is_empty].to_crs("EPSG:4326")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("prepare"); a1.add_argument("raw", type=Path); a1.add_argument("-o", "--output", type=Path, required=True)
    a2 = sub.add_parser("train"); a2.add_argument("data", type=Path); a2.add_argument("-o", "--output", type=Path, required=True); a2.add_argument("--epochs", type=int, default=30); a2.add_argument("--base", default="yolov8n-seg.pt")
    a4 = sub.add_parser("eval"); a4.add_argument("weights", type=Path); a4.add_argument("data", type=Path); a4.add_argument("-o", "--output", type=Path, required=True)
    a3 = sub.add_parser("predict"); a3.add_argument("weights", type=Path); a3.add_argument("image", type=Path)
    a3.add_argument("--footprint", type=Path, required=True); a3.add_argument("--level", default="F01"); a3.add_argument("-o", "--output", type=Path, required=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if a.cmd == "prepare":
        if not list(a.raw.glob("*.parquet")):
            sys.exit(f"no parquet files in {a.raw}")
        prepare(a.raw, a.output)
    elif a.cmd == "train":
        if not a.data.exists():
            sys.exit(f"input not found: {a.data}")
        print(json.dumps(train(a.data, a.output, a.epochs, base=a.base), indent=2))
    elif a.cmd == "eval":
        if not a.weights.exists() or not a.data.exists():
            sys.exit("weights or data.yaml not found")
        print(json.dumps(evaluate(a.weights, a.data, a.output), indent=2))
    else:
        import geopandas as gpd
        for f in (a.weights, a.image, a.footprint):
            if not f.exists():
                sys.exit(f"input not found: {f}")
        fp = gpd.read_file(a.footprint)
        log.info("read %s and %s", a.image, a.footprint)
        out = predict(a.weights, a.image, fp, a.level)
        out.to_file(a.output, driver="GeoJSON")
        log.info("processed 1 plan: %d apartments on level %s; wrote %s", len(out), a.level, a.output)


if __name__ == "__main__":
    main()
