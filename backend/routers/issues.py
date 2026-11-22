import logging
import os
import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError

from dependencies import get_current_user, get_user_supabase
from schemas.issues import CommentCreate, ConfirmRequest, CreateIssueRequest, ReopenRequest
from services.geo import match_building
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/issues", tags=["Issues"])

# Keep in sync with issues_status_check (backend/migrations/001_admin_side.sql).
VALID_STATUSES = {"open", "assigned", "in_progress", "resolved", "closed", "rejected"}

PHOTO_BUCKET = os.environ.get("ISSUE_PHOTO_BUCKET", "issue-photos")
MAX_PHOTOS = 3
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # server-side hard limit (app compresses to ~1.5 MB)
ALLOWED_PHOTO_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


# ---------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------

@lru_cache(maxsize=1)
def _admin_client():
    """Optional service-role client used only for Storage uploads.

    Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to enable it. Uploads are
    still scoped to the logged-in user's folder by this code.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def _storage_client(user_supabase):
    return _admin_client() or user_supabase


def _prepare_photos(photos: list[UploadFile]):
    """Validate and read all photos BEFORE anything is uploaded."""
    photos = [p for p in photos if p and p.filename]
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(
            status_code=422,
            detail=f"You can attach a maximum of {MAX_PHOTOS} photos.",
        )

    prepared = []
    for photo in photos:
        content_type = (photo.content_type or "").lower()
        extension = ALLOWED_PHOTO_TYPES.get(content_type)
        if extension is None:
            raise HTTPException(
                status_code=422,
                detail=f"{photo.filename}: only JPG, PNG or WEBP images are allowed.",
            )

        data = photo.file.read(MAX_PHOTO_BYTES + 1)
        if not data:
            raise HTTPException(status_code=422, detail=f"{photo.filename} is empty.")
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{photo.filename} is larger than {MAX_PHOTO_BYTES // (1024 * 1024)} MB.",
            )
        prepared.append((data, extension, content_type))
    return prepared


def _upload_photos(storage_client, user_id: str, prepared):
    """Upload photos to Supabase Storage. Returns (public_urls, uploaded_paths)."""
    bucket = storage_client.storage.from_(PHOTO_BUCKET)
    urls: list[str] = []
    paths: list[str] = []

    try:
        for data, extension, content_type in prepared:
            path = f"{user_id}/{uuid.uuid4().hex}.{extension}"
            bucket.upload(
                path=path,
                file=data,
                file_options={"content-type": content_type},
            )
            paths.append(path)
            urls.append(bucket.get_public_url(path))
    except Exception:
        logger.exception("Photo upload to Supabase Storage failed")
        _remove_photos(storage_client, paths)
        raise HTTPException(
            status_code=502,
            detail="Photos could not be uploaded. Please try again.",
        )

    return urls, paths


def _remove_photos(storage_client, paths: list[str]):
    """Best-effort cleanup so failed submissions don't leave orphan files."""
    if not paths:
        return
    try:
        storage_client.storage.from_(PHOTO_BUCKET).remove(paths)
    except Exception:
        logger.exception("Could not clean up uploaded photos: %s", paths)


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

@router.get("/buildings")
def get_buildings(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    """Buildings for the Report Issue dropdown. Assumes a `buildings` table (id, name)."""
    try:
        response = (
            supabase.table("buildings").select("id, name").order("name").execute()
        )
        return {
            "success": True,
            "buildings": [
                {"id": str(row["id"]), "name": row.get("name") or str(row["id"])}
                for row in (response.data or [])
            ],
        }
    except Exception:
        logger.exception("Could not load buildings")
        raise HTTPException(
            status_code=500,
            detail="Unable to load buildings. Please try again.",
        )


def _buildings_with_coords(supabase) -> list[dict]:
    try:
        return (
            supabase.table("buildings").select("id, name, zone, latitude, longitude").execute()
        ).data or []
    except Exception:
        logger.exception("Could not load building coordinates")
        return []


@router.get("/buildings/match")
def match_building_route(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    accuracy: float | None = Query(default=None, ge=0, le=10000),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    """Nearest campus building for a GPS fix (Report Issue auto-selects it; the student can change it)."""
    result = match_building(lat, lng, _buildings_with_coords(supabase), accuracy)
    if not result:
        return {"success": True, "match": None, "candidates": []}
    return {
        "success": True,
        "match": {**result["building"], "distance_m": result["distance_m"], "confidence": result["confidence"]},
        "candidates": result["candidates"],
    }


@router.post("", status_code=201)
def create_issue(
    category: str = Form(...),
    description: str = Form(...),
    building_id: str | None = Form(default=None),
    room: str | None = Form(default=None),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    location_text: str | None = Form(default=None),
    photos: list[UploadFile] = File(default=[]),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    # 1. Validate the text fields with the existing schema.
    try:
        payload = CreateIssueRequest(
            category=category.strip().lower(),
            description=description,
            building_id=building_id or None,
            room=room or None,
            latitude=latitude,
            longitude=longitude,
            location_text=location_text or None,
            photo_urls=[],
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": ["body", *e["loc"]], "msg": e["msg"]} for e in exc.errors()
            ],
        )

    # 1b. Resolve the building: unknown ids are rejected; the name is also kept in
    #     location_text so lists can show it without a join.
    if payload.building_id:
        try:
            rows = (
                supabase.table("buildings").select("id, name")
                .eq("id", payload.building_id).limit(1).execute()
            ).data or []
        except Exception:
            rows = []
        if not rows:
            raise HTTPException(status_code=422, detail="Unknown building.")
        if not payload.location_text:
            payload.location_text = rows[0]["name"]
    elif payload.latitude is not None and payload.longitude is not None:
        # No building picked: use the nearest building to the GPS fix (if any) so routing still works.
        match = match_building(payload.latitude, payload.longitude, _buildings_with_coords(supabase))
        if match:
            payload.building_id = match["building"]["id"]
            if not payload.location_text:
                payload.location_text = match["building"]["name"]

    # 2. Validate photos, then upload them to Supabase Storage.
    prepared = _prepare_photos(photos)
    storage = _storage_client(supabase)
    photo_urls, uploaded_paths = (
        _upload_photos(storage, user["id"], prepared) if prepared else ([], [])
    )

    # 3. Insert the issue with the photo URLs in the same request.
    issue_data = payload.model_dump()
    issue_data["photo_urls"] = photo_urls
    issue_data["user_id"] = user["id"]
    issue_data["status"] = "open"

    try:
        response = supabase.table("issues").insert(issue_data).execute()
        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="The issue could not be created.",
            )

        return {
            "success": True,
            "message": "Issue reported successfully.",
            "issue": response.data[0],
        }
    except HTTPException:
        _remove_photos(storage, uploaded_paths)
        raise
    except Exception:
        logger.exception("Issue insert failed")
        _remove_photos(storage, uploaded_paths)
        raise HTTPException(
            status_code=500,
            detail="Unable to create the issue. Please try again.",
        )


@router.get("/mine")
def get_my_issues(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Invalid status filter.",
        )

    try:
        query = (
            supabase.table("issues")
            .select("*", count="exact")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if status is not None:
            query = query.eq("status", status)

        response = query.execute()
        admin = _admin_helpers()
        now = admin._now()
        buildings = _buildings_by_id(supabase)

        return {
            "success": True,
            "issues": [_student_issue_view(row, buildings, now) for row in response.data or []],
            "count": response.count or 0,
            "limit": limit,
            "offset": offset,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve your issues. Please try again.",
        )


# ---------------------------------------------------------
# Student side: summary, detail, comments, confirm / reopen
#
# Students can only READ their own issues + issue_events (RLS). Writes below use the
# service-role client, but ONLY after _own_issue() has proved (through the student's own
# RLS-scoped client AND an explicit user_id check) that the issue belongs to this student,
# and after the status rules here allow the action. Admin notes are never exposed.
# ---------------------------------------------------------

STUDENT_EVENT_TYPES_HIDDEN = {"priority_changed"}   # internal triage detail


def _admin_helpers():
    # Local import: routers.admin is large and only needed here (no import cycle either way).
    from routers import admin
    return admin


def _own_issue(supabase, user: dict, issue_id: int) -> dict:
    try:
        rows = (
            supabase.table("issues").select("*").eq("id", issue_id)
            .eq("user_id", user["id"]).limit(1).execute()
        ).data or []
    except Exception:
        logger.exception("Could not load issue %s", issue_id)
        raise HTTPException(status_code=500, detail="Unable to load this issue. Please try again.")
    if not rows or rows[0].get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return rows[0]


def _student_issue_view(issue: dict, buildings: dict, now) -> dict:
    admin = _admin_helpers()
    building = buildings.get(issue.get("building_id")) or {}
    due = admin._effective_due(issue)
    return {
        **issue,
        "building_name": building.get("name") or issue.get("location_text"),
        "zone": building.get("zone"),
        "due_at_effective": admin._iso(due),
        "overdue": admin._is_overdue(issue, now),
    }


def _buildings_by_id(supabase) -> dict:
    try:
        rows = supabase.table("buildings").select("id, name, zone").execute().data or []
    except Exception:
        rows = []
    return {row["id"]: row for row in rows}


def _parse_feedback(note: str | None) -> dict:
    """Feedback events store '<rating>/5' + optional ' · <text>' in issue_events.note."""
    note = note or ""
    head, _, text = note.partition(" · ")
    try:
        rating = int(head.split("/")[0])
    except ValueError:
        rating = None
    return {"rating": rating, "text": text or None}


def _student_actions(issue: dict) -> dict:
    status = issue.get("status")
    return {
        "can_confirm": status == "resolved",
        "can_reopen": status == "resolved",
        "can_comment": status not in ("closed", "rejected"),
    }


@router.get("/mine/summary")
def my_summary(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    """Counts per status + the 5 most recent issues (student Home screen)."""
    admin = _admin_helpers()
    now = admin._now()
    try:
        rows = (
            supabase.table("issues")
            .select("id, status, category, description, building_id, room, location_text, priority, "
                    "created_at, due_at, photo_urls")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .limit(1000)
            .execute()
        ).data or []
    except Exception:
        logger.exception("Could not load issue summary")
        raise HTTPException(status_code=500, detail="Unable to load your issues. Please try again.")

    counts = {status: 0 for status in sorted(VALID_STATUSES)}
    for row in rows:
        counts[row.get("status") or "open"] = counts.get(row.get("status") or "open", 0) + 1

    buildings = _buildings_by_id(supabase)
    views = [_student_issue_view(row, buildings, now) for row in rows]
    return {
        "success": True,
        "counts": counts,
        "total": len(rows),
        "active": sum(counts.get(s, 0) for s in ("open", "assigned", "in_progress")),
        "overdue": sum(1 for v in views if v["overdue"]),
        "awaiting_confirmation": [v for v in views if v.get("status") == "resolved"][:5],
        "recent": views[:5],
    }


@router.get("/{issue_id}")
def get_my_issue(
    issue_id: int,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    admin = _admin_helpers()
    now = admin._now()
    issue = _own_issue(supabase, user, issue_id)
    view = _student_issue_view(issue, _buildings_by_id(supabase), now)

    try:
        events = (
            supabase.table("issue_events").select("*").eq("issue_id", issue_id)
            .order("created_at").execute()
        ).data or []
    except Exception:
        logger.exception("Could not load events for issue %s", issue_id)
        events = []

    def actor(event):
        return "You" if event.get("actor_id") == user["id"] else "PHO office"

    timeline = [{
        "type": "created", "from_status": None, "to_status": "open",
        "created_at": issue.get("created_at"), "actor": "You", "note": None,
    }]
    comments, feedback = [], None
    for event in events:
        kind = event.get("type")
        if kind == "comment":
            comments.append({
                "id": event.get("id"),
                "text": event.get("note"),
                "created_at": event.get("created_at"),
                "author": actor(event),
                "mine": event.get("actor_id") == user["id"],
            })
        elif kind == "feedback":
            feedback = {**_parse_feedback(event.get("note")), "created_at": event.get("created_at")}
        elif kind not in STUDENT_EVENT_TYPES_HIDDEN:
            timeline.append({
                "type": kind,
                "from_status": event.get("from_status"),
                "to_status": event.get("to_status"),
                "created_at": event.get("created_at"),
                "actor": actor(event),
                "note": event.get("note"),
            })

    # Workers are not readable by students under RLS; expose only name + phone of the current one.
    worker = None
    if issue.get("assigned_worker_id"):
        try:
            rows = (
                get_supabase_client().table("workers").select("id, name, phone, primary_skill")
                .eq("id", issue["assigned_worker_id"]).limit(1).execute()
            ).data or []
            worker = rows[0] if rows else None
        except Exception:
            logger.exception("Could not load worker for issue %s", issue_id)
    if worker:
        assigned_at = next(
            (e["created_at"] for e in reversed(timeline) if e["type"] in ("assigned", "reassigned", "reopened")),
            None,
        )
        worker["assigned_at"] = assigned_at
    view["worker"] = worker

    return {
        "success": True,
        "issue": view,
        "timeline": timeline,
        "comments": comments,
        "feedback": feedback,
        **_student_actions(issue),
    }


@router.post("/{issue_id}/comments", status_code=201)
def add_comment(
    issue_id: int,
    payload: CommentCreate,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    issue = _own_issue(supabase, user, issue_id)
    if not _student_actions(issue)["can_comment"]:
        raise HTTPException(status_code=409, detail="This issue is finished; comments are closed.")
    admin = _admin_helpers()
    admin._event(get_supabase_client(), issue_id, user["id"], "comment", note=payload.text)
    return {"success": True, "message": "Comment added."}


@router.post("/{issue_id}/confirm")
def confirm_resolution(
    issue_id: int,
    payload: ConfirmRequest,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    """Student confirms the fix: resolved -> closed, plus a rating."""
    issue = _own_issue(supabase, user, issue_id)
    if issue.get("status") != "resolved":
        raise HTTPException(status_code=409, detail="Only resolved issues can be confirmed.")
    admin = _admin_helpers()
    sb = get_supabase_client()
    updated = admin._apply_status(sb, issue, "closed", "Confirmed fixed by the student.", user["id"])
    note = f"{payload.rating}/5" + (f" · {payload.feedback}" if payload.feedback else "")
    admin._event(sb, issue_id, user["id"], "feedback", note=note)
    return {"success": True, "message": "Thanks! The issue is now closed.", "issue": updated}


@router.post("/{issue_id}/reopen")
def reopen_issue(
    issue_id: int,
    payload: ReopenRequest,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    """Student says the problem persists: resolved -> in_progress (same worker) or open (no worker)."""
    issue = _own_issue(supabase, user, issue_id)
    if issue.get("status") != "resolved":
        raise HTTPException(status_code=409, detail="Only resolved issues can be reopened.")
    admin = _admin_helpers()
    sb = get_supabase_client()
    note = f"Reopened by the student: {payload.reason}"
    if issue.get("assigned_worker_id"):
        updated = admin._apply_status(sb, issue, "in_progress", note, user["id"])
    else:
        rows = admin._run(
            sb.table("issues").update({"status": "open", "resolved_at": None}).eq("id", issue_id),
            "reopen the issue",
        )
        admin._event(sb, issue_id, user["id"], "reopened", "resolved", "open", note)
        updated = rows[0] if rows else issue
    return {"success": True, "message": "Issue reopened. The PHO office has been notified.", "issue": updated}

