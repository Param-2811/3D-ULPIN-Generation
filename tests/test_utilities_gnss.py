"""Utility volumes get B00/T codes at the right depth; GNSS control points shift the outline by the surveyed offset."""
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from src.geometry.utilities import make_utilities
from src.ingest.gnss import apply_control_points
from src.ulpin.generate import parse
from src.validate.checks import run_checks

P = "27021500123456"


def test_utility_volume_codes_and_depth():
    lines = gpd.GeoDataFrame({"network_type": ["water", "metro"], "depth_m": [1.5, 12.0], "diameter_m": [0.6, 6.0],
                              "geometry": [LineString([(300000, 2480000), (300040, 2480000)]), LineString([(300000, 2479990), (300040, 2479990)])]},
                             crs="EPSG:32643")
    u = make_utilities(lines, P)
    assert list(u.unit_code) == ["T01", "T02"] and u.ulpin.is_unique
    water, metro = u.iloc[0], u.iloc[1]
    assert parse(water.ulpin) == {"parent_ulpin": P, "building_no": 0, "level_code": "B01", "unit_code": "T01"}
    assert metro.level_code == "B05" and metro.z_min == -15.0 and metro.z_max == -9.0
    assert abs(water.area_m2 - 40 * 0.6) < 0.5


def test_utility_missing_field_rejected():
    lines = gpd.GeoDataFrame({"network_type": ["gas"], "depth_m": [2.0], "geometry": [LineString([(0, 0), (10, 0)])]}, crs="EPSG:32643")
    with pytest.raises(ValueError, match="diameter_m"):
        make_utilities(lines, P)


def test_gnss_shift_recovers_known_offset():
    fp = gpd.GeoDataFrame(geometry=[box(300000, 2480000, 300020, 2480010)], crs="EPSG:32643")
    # the surveyor measured the two western corners 1.5 m east and 0.8 m north of where the map has them
    pts = gpd.GeoSeries.from_xy([300001.5, 300001.5], [2480000.8, 2480010.8], crs="EPSG:32643").to_crs("EPSG:4326")
    csv = pd.DataFrame({"name": ["SW", "NW"], "lat": pts.y, "lon": pts.x})
    out, rep = apply_control_points(fp.to_crs("EPSG:4326"), csv)
    assert rep["points_used"] == 2 and abs(rep["shift_east_m"] - 1.5) < 0.02 and abs(rep["shift_north_m"] - 0.8) < 0.02
    assert rep["residual_m"] < 0.02 and out.outline_source.iloc[0] == "gnss_adjusted"


def test_gnss_needs_two_matches():
    fp = gpd.GeoDataFrame(geometry=[box(300000, 2480000, 300020, 2480010)], crs="EPSG:32643").to_crs("EPSG:4326")
    with pytest.raises(ValueError, match="control points"):
        apply_control_points(fp, pd.DataFrame({"name": ["far"], "lat": [22.0], "lon": [72.0]}))


def test_orthogonalise_squares_a_noisy_rectangle():
    from src.models.building import orthogonalise
    import numpy as np
    rng = np.random.default_rng(0)
    # a 40 x 12 m rectangle rotated 20 degrees, with 0.3 m pixel noise on 200 boundary points
    from shapely import affinity
    base = box(0, 0, 40, 12)
    pts = [base.exterior.interpolate(d).coords[0] for d in np.linspace(0, base.length, 200, endpoint=False)]
    from shapely.geometry import Polygon
    noisy = affinity.rotate(Polygon([(x + rng.normal(0, .3), y + rng.normal(0, .3)) for x, y in pts]).buffer(0), 20, origin=(0, 0))
    sq = orthogonalise(noisy)
    assert 4 <= len(sq.exterior.coords) - 1 <= 8
    assert abs(sq.area - 480) / 480 < 0.08


def test_village_lookup_and_structured_placeholder():
    from src.ingest.admin import village_at, placeholder_ulpin
    import pytest as _pt
    v = village_at(22.55047, 72.93107)
    if v is None:
        _pt.skip("Gujarat village layer not downloaded")
    assert v["state_code"] == "24" and v["district"] == "Anand" and len(v["village_code"]) == 6
    u, how = placeholder_ulpin(22.55047, 72.93107, v)
    assert len(u) == 14 and u.startswith("24482" + v["village_code"]) and "Bakrol" in how
    assert u == placeholder_ulpin(22.55047, 72.93107, v)[0]
    u2, how2 = placeholder_ulpin(51.9982, 4.3461)
    assert len(u2) == 14 and "location-based" in how2
