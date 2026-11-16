"""GEO - match a GPS fix to the nearest campus building. Pure functions (no DB), easy to unit-test.

Building coordinates live in public.buildings.latitude / longitude (filled from OpenStreetMap, see
backend/data/building_coords.sql). They are building CENTRES, not outlines, so a match is a best guess:
the app shows it as "Detected: ... You can change it" and the student's own choice always wins.

match_building(lat, lng, buildings, accuracy_m=None) -> dict | None
  buildings: rows with id, name, zone, latitude, longitude (rows without coordinates are ignored)
  returns {"building": {id, name, zone}, "distance_m", "confidence": high|medium|low, "candidates": [...]}
  or None when the point is outside campus or further than the match radius from every building.
"""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000

# IIT Bombay campus (generous box: Powai lake side to the main gate). Points outside are never matched.
CAMPUS_BBOX = {"min_lat": 19.120, "max_lat": 19.142, "min_lng": 72.900, "max_lng": 72.925}

MATCH_RADIUS_M = 150          # max distance from a building centre for a match
MAX_RADIUS_M = 300            # radius cap when GPS accuracy is poor
HIGH_CONFIDENCE_M = 40
MEDIUM_CONFIDENCE_M = 90
AMBIGUOUS_GAP_M = 15          # runner-up this close to the winner -> confidence capped at "medium"


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def on_campus(lat: float, lng: float, bbox: dict = CAMPUS_BBOX) -> bool:
    return bbox["min_lat"] <= lat <= bbox["max_lat"] and bbox["min_lng"] <= lng <= bbox["max_lng"]


def _public(row: dict) -> dict:
    return {"id": str(row["id"]), "name": row.get("name") or str(row["id"]), "zone": row.get("zone")}


def match_building(lat, lng, buildings: list[dict], accuracy_m: float | None = None) -> dict | None:
    if lat is None or lng is None:
        return None
    lat, lng = float(lat), float(lng)
    if not on_campus(lat, lng):
        return None

    ranked = sorted(
        (
            (haversine_m(lat, lng, float(b["latitude"]), float(b["longitude"])), b)
            for b in buildings
            if b.get("latitude") is not None and b.get("longitude") is not None
        ),
        key=lambda pair: pair[0],
    )
    if not ranked:
        return None

    # A poor fix (large accuracy circle) may still be inside the building: widen the radius, up to a cap.
    radius = min(max(MATCH_RADIUS_M, float(accuracy_m or 0)), MAX_RADIUS_M)
    distance, best = ranked[0]
    if distance > radius:
        return None

    if distance <= HIGH_CONFIDENCE_M and (accuracy_m is None or accuracy_m <= 50):
        confidence = "high"
    elif distance <= MEDIUM_CONFIDENCE_M:
        confidence = "medium"
    else:
        confidence = "low"
    if len(ranked) > 1 and ranked[1][0] - distance < AMBIGUOUS_GAP_M and confidence == "high":
        confidence = "medium"

    return {
        "building": _public(best),
        "distance_m": round(distance),
        "confidence": confidence,
        "candidates": [
            {**_public(b), "distance_m": round(d)} for d, b in ranked[:3] if d <= MAX_RADIUS_M
        ],
    }
