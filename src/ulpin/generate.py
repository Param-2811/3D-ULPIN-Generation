"""3D ULPIN: generate, parse, validate. Spec: docs/ULPIN_SPEC.md."""
import math
import re

_LEVEL = r"G00|F(?:0[1-9]|[1-9]\d)|B0[1-9]|R00|A0[1-9]"
_ID = re.compile(rf"^(\d{{14}})-B(\d{{2}})-({_LEVEL})-([UPCT]\d{{2}})-(\d)$")
_LEVEL_RE = re.compile(rf"^(?:{_LEVEL})$")
_UNIT_RE = re.compile(r"^[UPCT]\d{2}$")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _luhn_check_digit(digits: str) -> str:
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 0:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return str((10 - total % 10) % 10)


def generate(parent_ulpin: str, building_no: int, level_code: str, unit_code: str) -> str:
    if not re.fullmatch(r"\d{14}", parent_ulpin):
        raise ValueError(f"parent_ulpin must be 14 digits, got {parent_ulpin!r}")
    if not 0 <= building_no <= 99:
        raise ValueError(f"building_no must be 0-99, got {building_no}")
    if not _LEVEL_RE.match(level_code):
        raise ValueError(f"bad level_code {level_code!r} (G00, F01-F99, B01-B09, R00, A01-A09)")
    if not _UNIT_RE.match(unit_code):
        raise ValueError(f"bad unit_code {unit_code!r} (U/P/C/T + 2 digits)")
    body = f"{parent_ulpin}-B{building_no:02d}-{level_code}-{unit_code}"
    return f"{body}-{_luhn_check_digit(_digits(body))}"


def parse(ulpin_3d: str) -> dict:
    s = ulpin_3d.strip().upper()
    m = _ID.match(s)
    if not m:
        raise ValueError(f"not a 3D ULPIN: {ulpin_3d!r}")
    if _luhn_check_digit(_digits(s[:-2])) != m[5]:
        raise ValueError(f"check digit wrong: {ulpin_3d!r}")
    return {"parent_ulpin": m[1], "building_no": int(m[2]), "level_code": m[3], "unit_code": m[4]}


def validate(ulpin_3d: str) -> bool:
    try:
        parse(ulpin_3d)
        return True
    except ValueError:
        return False


def clockwise_from_northwest(centroids_xy: list[tuple[float, float]]) -> list[int]:
    """Deterministic unit order: start at the north-west-most centroid, go clockwise.
    Coordinates must be metres (EPSG:32643), never degrees. Returns original indices."""
    if not centroids_xy:
        return []
    cx = sum(x for x, _ in centroids_xy) / len(centroids_xy)
    cy = sum(y for _, y in centroids_xy) / len(centroids_xy)
    start = max(range(len(centroids_xy)), key=lambda i: centroids_xy[i][1] - centroids_xy[i][0])
    a0 = math.atan2(centroids_xy[start][1] - cy, centroids_xy[start][0] - cx)

    def clockwise_angle(i):
        x, y = centroids_xy[i]
        return (a0 - math.atan2(y - cy, x - cx)) % (2 * math.pi)

    return sorted(range(len(centroids_xy)), key=clockwise_angle)
