"""ISSUE SERVICE - calls to the issue endpoints (backend/routers/issues.py) via core/api_client.py.

Implemented
  [x] list_buildings()              GET  /issues/buildings
  [x] create_issue(payload)         POST /issues               (multipart; photos are sent in the same request)
  [x] list_my_issues(status=None)   GET  /issues/mine

TODO (needs backend endpoints first)
  [ ] list_categories()             GET  /categories/
  [ ] match_building(lat, lng)      GET  /buildings/match/?lat=&lng=
  [ ] get_issue(issue_id)           GET  /issues/{id}          (includes timeline + allowed transitions)
  [ ] add_comment(issue_id, text)   POST /issues/{id}/comments
  [ ] submit_feedback(issue_id, rating, text)   POST /issues/{id}/feedback
  [ ] reopen(issue_id, reason)      POST /issues/{id}/reopen
"""
import mimetypes

from core import api_client

# UI filter label (screens) -> backend status value
_STATUS_VALUES = {
    "open": "open",
    "assigned": "assigned",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "resolved": "resolved",
    "closed": "closed",
    "rejected": "rejected",
}


def _status_value(status: str | None) -> str | None:
    if not status or str(status).strip().lower() == "all":
        return None
    return _STATUS_VALUES.get(str(status).strip().lower(), str(status).strip().lower())


async def list_buildings() -> list[dict]:
    """[{id, name}, ...] sorted by name (public.buildings)."""
    data = await api_client.request("GET", "/issues/buildings")
    return data.get("buildings", []) if isinstance(data, dict) else []


async def list_my_issues(status: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """The logged-in user's issues, newest first. `status` accepts UI labels ("In progress") or backend values."""
    data = await api_client.request(
        "GET",
        "/issues/mine",
        params={"status": _status_value(status), "limit": limit, "offset": offset},
    )
    issues = data.get("issues", []) if isinstance(data, dict) else []
    for issue in issues:
        # Backend stores the building name inside location_text; screens read "building".
        if not issue.get("building") and issue.get("location_text"):
            issue["building"] = issue["location_text"]
    return issues


async def create_issue(payload: dict) -> dict:
    """Create an issue. Returns the created issue row (has "id").

    payload keys: category, description, building_id, building (name), room, location {latitude, longitude},
                  photos [{name, bytes}]  (optional, max 3 - uploaded in the same request)
    """
    location = payload.get("location") or {}
    form = {
        "category": payload.get("category"),
        "description": payload.get("description") or "",
        "building_id": payload.get("building_id"),
        "room": payload.get("room"),
        "location_text": payload.get("building") or payload.get("location_text"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
    }
    files = []
    for photo in payload.get("photos") or []:
        name = photo.get("name") or "photo.jpg"
        mime = mimetypes.guess_type(name)[0] or "image/jpeg"
        files.append(("photos", (name, photo["bytes"], mime)))

    data = await api_client.request("POST", "/issues", data=form, files=files or None)
    return data.get("issue", data) if isinstance(data, dict) else {}
