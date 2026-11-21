import itertools
import pytest
from src.ulpin.generate import generate, parse, validate, clockwise_from_northwest

P = "27021500123456"
LEVELS = ["G00", "F01", "F05", "F99", "B01", "B09", "R00", "A01", "A09"]
UNITS = ["U01", "P12", "C01", "T01"]


@pytest.mark.parametrize("level,unit", itertools.product(LEVELS, UNITS))
def test_round_trip(level, unit):
    x = dict(parent_ulpin=P, building_no=1, level_code=level, unit_code=unit)
    uid = generate(**x)
    assert parse(uid) == x
    assert validate(uid)
    assert uid == uid.upper() and " " not in uid


def test_deterministic():
    assert generate(P, 1, "F05", "U03") == generate(P, 1, "F05", "U03")


def test_example_shape():
    uid = generate(P, 1, "F05", "U03")
    assert uid.startswith("27021500123456-B01-F05-U03-") and len(uid) == 28


def test_any_single_digit_typo_is_caught():
    uid = generate(P, 1, "F05", "U03")
    for i, ch in enumerate(uid):
        if not ch.isdigit():
            continue
        for d in "0123456789":
            if d != ch:
                assert not validate(uid[:i] + d + uid[i + 1:]), (i, d)


def test_parse_normalises_input():
    uid = generate(P, 1, "F05", "U03")
    assert parse(f"  {uid.lower()} ") == parse(uid)


@pytest.mark.parametrize("bad", [
    dict(parent_ulpin="123", building_no=1, level_code="F01", unit_code="U01"),
    dict(parent_ulpin=P, building_no=100, level_code="F01", unit_code="U01"),
    dict(parent_ulpin=P, building_no=1, level_code="F00", unit_code="U01"),
    dict(parent_ulpin=P, building_no=1, level_code="B10", unit_code="U01"),
    dict(parent_ulpin=P, building_no=1, level_code="F01", unit_code="X01"),
    dict(parent_ulpin=P, building_no=1, level_code="f01", unit_code="U01"),
])
def test_bad_input_raises(bad):
    with pytest.raises(ValueError):
        generate(**bad)


@pytest.mark.parametrize("bad", ["", "garbage", P, "27021500123456-B01-F05-U03", "27021500123456-B01-F05-U03-77"])
def test_validate_rejects_bad_strings(bad):
    assert not validate(bad)


def test_clockwise_from_northwest():
    # 2x2 grid of flats, metres. Expected order: NW, NE, SE, SW.
    nw, ne, se, sw = (0, 10), (10, 10), (10, 0), (0, 0)
    assert clockwise_from_northwest([se, nw, sw, ne]) == [1, 3, 0, 2]
    assert clockwise_from_northwest([]) == []


def test_placeholder_ulpin_is_14_digits_and_stable():
    from src.ingest.osm import placeholder_ulpin
    a = placeholder_ulpin(22.5564, 72.9640)     # Anand
    b = placeholder_ulpin(23.0339, 72.5619)     # Ahmedabad
    assert len(a) == 14 and a.isdigit() and a == placeholder_ulpin(22.5564, 72.9640)
    assert a != b
    assert validate(generate(a, 1, "F01", "U01"))
