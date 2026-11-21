"""The intake pipeline on a synthetic outline: files land where the viewer expects them and the result is clean."""
import json

import geopandas as gpd
import pytest
from shapely.geometry import box

from src import pipeline


def test_run_with_uploaded_outline(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "DATA", tmp_path)
    fp = tmp_path / "outline.geojson"
    gpd.GeoDataFrame(geometry=[box(300000, 2480000, 300030, 2480012)], crs="EPSG:32643").to_crs("EPSG:4326").to_file(fp, driver="GeoJSON")
    r = pipeline.run("27021500123456", 2, footprint_geojson=fp, height_m=9.0, floors_official=3, units_official=9, basements=1)
    assert r["pand_id"] == "27021500123456B02"
    assert r["levels"] == 4 and r["units"] == 9 + 20 and r["findings"] == 0
    rep = json.loads((tmp_path / "27021500123456B02_report.json").read_text())
    assert rep["findings"] == []
    units = gpd.read_file(tmp_path / "27021500123456B02_units3d.geojson")
    assert units.ulpin.is_unique and units.ulpin.str.startswith("27021500123456-B02-").all()


def test_run_refuses_without_height_or_units(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "DATA", tmp_path)
    fp = tmp_path / "outline.geojson"
    gpd.GeoDataFrame(geometry=[box(300000, 2480000, 300030, 2480012)], crs="EPSG:32643").to_crs("EPSG:4326").to_file(fp, driver="GeoJSON")
    with pytest.raises(ValueError, match="height"):
        pipeline.run("27021500123456", 1, footprint_geojson=fp, floors_official=2, units_official=4)
    with pytest.raises(ValueError, match="unit count"):
        pipeline.run("27021500123456", 1, footprint_geojson=fp, height_m=6.0, floors_official=2)


def test_estimate_mode_fills_gaps_and_labels_them(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "DATA", tmp_path)
    fp = tmp_path / "outline.geojson"
    gpd.GeoDataFrame(geometry=[box(300000, 2480000, 300030, 2480012)], crs="EPSG:32643").to_crs("EPSG:4326").to_file(fp, driver="GeoJSON")
    r = pipeline.run("27021500123456", 1, footprint_geojson=fp, mode="estimate")   # no height, floors or units given
    assert r["accuracy"] == "estimated" and r["mode"] == "estimate"
    assert any("height" in a for a in r["assumed"]) and any("unit count" in a for a in r["assumed"])
    assert r["units"] >= 1 and r["findings"] == 0
    units = gpd.read_file(tmp_path / "27021500123456B01_units3d.geojson")
    assert set(units.floors_source) <= {"estimated", "rule_of_thumb"}


def test_manual_mode_refuses_gaps_and_map_values(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "DATA", tmp_path)
    fp = tmp_path / "outline.geojson"
    gpd.GeoDataFrame(geometry=[box(300000, 2480000, 300030, 2480012)], crs="EPSG:32643").to_crs("EPSG:4326").to_file(fp, driver="GeoJSON")
    with pytest.raises(ValueError, match="manual mode"):
        pipeline.run("27021500123456", 1, footprint_geojson=fp, height_m=9.0, floors_official=3, mode="manual")   # no units
    with pytest.raises(ValueError, match="map-estimated"):
        pipeline.run("27021500123456", 1, footprint_geojson=fp, height_m=9.0, height_label="osm_levels_x3", floors_official=3, units_official=6, mode="manual")
    r = pipeline.run("27021500123456", 1, footprint_geojson=fp, height_m=9.0, floors_official=3, units_official=6, mode="manual")
    assert r["accuracy"] == "surveyed" and r["assumed"] == ["unit shapes are equal strips (no floor plan uploaded)"]
