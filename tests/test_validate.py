"""Synthetic 2-floor, 2-unit-per-floor building; each test breaks it one way and expects that one finding."""
import geopandas as gpd
import pytest
from shapely import affinity
from shapely.geometry import box

from src.geometry.slice_floors import slice_floors
from src.geometry.units import make_units
from src.validate.checks import run_checks

P = "27021500123456"


@pytest.fixture
def building():
    # 20 x 10 m block near Anand, Gujarat, in metres (EPSG:32643) then stored as 4326
    fp = box(300000, 2480000, 300020, 2480010)
    solid = gpd.GeoDataFrame([{"pand_id": "T", "height_m": 6.0, "floors_official": 2, "z_min": 0.0, "z_max": 6.0,
                               "basements": 0, "geometry": fp}], crs="EPSG:32643").to_crs("EPSG:4326")
    floors = slice_floors(solid)
    units = make_units(floors, P, total_units=4)
    return units, floors


def checks_of(findings):
    return sorted({f["check"] for f in findings})


def test_clean_building_passes(building):
    units, floors = building
    assert run_checks(units, floors) == []
    assert len(units) == 4 and units.ulpin.is_unique


def test_overlap_detected(building):
    units, floors = building
    m = units.to_crs("EPSG:32643")
    m.loc[1, "geometry"] = affinity.translate(m.loc[1, "geometry"], xoff=-5)  # slide unit 2 onto unit 1
    f = run_checks(m.to_crs("EPSG:4326"), floors)
    assert "overlap" in checks_of(f)


def test_containment_detected(building):
    units, floors = building
    m = units.to_crs("EPSG:32643")
    m.loc[0, "geometry"] = affinity.translate(m.loc[0, "geometry"], xoff=-15)
    assert "containment" in checks_of(run_checks(m.to_crs("EPSG:4326"), floors))


def test_gap_detected(building):
    units, floors = building
    assert "gap" in checks_of(run_checks(units.drop(index=0), floors))


def test_floating_detected(building):
    units, floors = building
    units.loc[2, "z_min"] = 4.0
    assert "floating" in checks_of(run_checks(units, floors))


def test_duplicate_and_bad_id_detected(building):
    units, floors = building
    units.loc[1, "ulpin"] = units.loc[0, "ulpin"]
    units.loc[2, "ulpin"] = units.loc[2, "ulpin"][:-1] + "X"
    c = checks_of(run_checks(units, floors))
    assert "duplicate_id" in c and "bad_id" in c


def test_split_plan_unit_keeps_largest_piece():
    """A drawn flat that straddles a notch in the outline gets clipped into two pieces; a unit must be one polygon."""
    from shapely.geometry import Polygon
    # U-shaped building: the notch splits a flat spanning the top
    fp = Polygon([(0, 0), (30, 0), (30, 10), (20, 10), (20, 4), (10, 4), (10, 10), (0, 10)])
    solid = gpd.GeoDataFrame([{"pand_id": "T", "height_m": 3.0, "floors_official": 1, "z_min": 0.0, "z_max": 3.0, "basements": 0,
                               "geometry": affinity.translate(fp, 300000, 2480000)}], crs="EPSG:32643").to_crs("EPSG:4326")
    floors = slice_floors(solid)
    plan = gpd.GeoDataFrame({"level_code": ["G00"], "geometry": [affinity.translate(box(5, 5, 25, 10), 300000, 2480000)]}, crs="EPSG:32643").to_crs("EPSG:4326")
    units = make_units(floors, P, total_units=0, plan_units=plan)
    assert len(units) == 1 and units.geometry.iloc[0].geom_type == "Polygon"
    assert abs(units.area_m2.iloc[0] - 25) < 1     # the larger 5x5 arm, not both arms


def test_more_than_99_units_on_a_level_is_refused():
    solid = gpd.GeoDataFrame([{"pand_id": "T", "height_m": 3.0, "floors_official": 1, "z_min": 0.0, "z_max": 3.0, "basements": 0,
                               "geometry": box(300000, 2480000, 300100, 2480020)}], crs="EPSG:32643").to_crs("EPSG:4326")
    floors = slice_floors(solid)
    with pytest.raises(ValueError, match="99 per level"):
        make_units(floors, P, total_units=120)
    assert len(make_units(floors, P, total_units=99)) == 99
