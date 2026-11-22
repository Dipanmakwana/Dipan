"""ADMIN (PHO) ROUTER - complaint management, worker assignment, workload, analytics.

Every endpoint needs a PHO admin: Depends(require_staff) checks public.profiles.role == 'pho_admin'.
Queries use the admin's own token (get_user_supabase), so the RLS policies from the migration apply
(is_pho_admin() can read/update all issues and manage workers, assignments, issue_events, issue_notes).

Endpoints (all under /api/admin)
  GET   /meta                               categories, statuses, priorities, transitions, SLA, buildings
  GET   /summary                            dashboard KPIs, needs-attention list, team capacity
  GET   /issues                             list with filters, search, sort, pagination
  GET   /issues/{id}                        detail: reporter, worker, notes, timeline, allowed transitions
  PATCH /issues/{id}/status                 change status (validated against ALLOWED_TRANSITIONS)
  PATCH /issues/status                      bulk status change
  PATCH /issues/{id}/priority               change priority (recomputes due_at)
  POST  /issues/{id}/notes                  internal admin note
  GET   /issues/{id}/recommended-workers    scheduler ranking (services/scheduler.py)
  POST  /issues/{id}/assign                 assign / reassign a worker
  POST  /issues/{id}/unassign               remove the worker, back to open
  GET   /workers                            workload board (load, jobs by priority, overdue, availability)
  POST  /workers                            add worker
  GET   /workers/{id}                       worker detail + active jobs + stats
  PATCH /workers/{id}                       edit worker
  PATCH /workers/{id}/availability          available / on_leave (dates) / inactive
  GET   /workers/{id}/history               resolved / closed jobs
  GET   /analytics                          stats for a date range

Status model (same as issues_status_check in the DB and src/components/status_chip.py)
"""
import logging
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from dependencies import get_user_supabase, require_staff
from schemas.admin import (
    AssignRequest,
    AvailabilityUpdate,
    BulkStatusUpdate,
    NoteCreate,
    PriorityUpdate,
    StatusUpdate,
    UnassignRequest,
    WorkerCreate,
    WorkerUpdate,
)
from services.scheduler import PRIORITY_EFFORT, is_on_leave, recommend_workers
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

IST = timezone(timedelta(hours=5, minutes=30))

CATEGORIES = ["plumbing", "electrical", "civil", "housekeeping", "network", "furniture", "lighting", "other"]
STATUSES = ["open", "assigned", "in_progress", "resolved", "closed", "rejected"]
ACTIVE_STATUSES = ("open", "assigned", "in_progress")
WORKING_STATUSES = ("assigned", "in_progress")          # count towards a worker's load
PRIORITIES = ["urgent", "high", "normal", "low"]
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}
SLA_HOURS = {"urgent": 4, "high": 24, "normal": 72, "low": 168}

ALLOWED_TRANSITIONS = {
    "open": ["assigned", "rejected"],
    "assigned": ["in_progress", "open", "rejected"],
    "in_progress": ["resolved", "assigned"],
    "resolved": ["closed", "in_progress"],      # in_progress = reopened
    "closed": [],
    "rejected": ["open"],
}


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _now() -> datetime:
    return datetime.now(IST)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _today_start(now: datetime) -> datetime:
    return datetime.combine(now.date(), time.min, tzinfo=IST)


def _hours(start, end) -> float | None:
    start, end = _dt(start), _dt(end)
    if not start or not end:
        return None
    return max((end - start).total_seconds() / 3600, 0.0)


def _effective_due(issue: dict) -> datetime | None:
    due = _dt(issue.get("due_at"))
    if due:
        return due
    created = _dt(issue.get("created_at"))
    if not created:
        return None
    return created + timedelta(hours=SLA_HOURS.get(issue.get("priority") or "normal", 72))


def _is_overdue(issue: dict, now: datetime) -> bool:
    due = _effective_due(issue)
    return bool(due and issue.get("status") in ACTIVE_STATUSES and now > due)


def _run(builder, what: str):
    try:
        return builder.execute().data or []
    except Exception:
        logger.exception("Admin query failed: %s", what)
        raise HTTPException(status_code=500, detail=f"Unable to {what}. Please try again.")


def _buildings(sb) -> dict:
    rows = _run(sb.table("buildings").select("id, name, zone"), "load buildings")
    return {row["id"]: row for row in rows}


def _workers(sb) -> list[dict]:
    return _run(sb.table("workers").select("*").order("name"), "load workers")


def _profiles(sb, ids) -> dict:
    ids = sorted({i for i in ids if i})
    if not ids:
        return {}
    rows = _run(sb.table("profiles").select("id, full_name, roll_number").in_("id", ids), "load profiles")
    return {row["id"]: row for row in rows}


def _get_issue(sb, issue_id: int) -> dict:
    rows = _run(sb.table("issues").select("*").eq("id", issue_id).limit(1), "load the complaint")
    if not rows:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    return rows[0]


def _get_worker(sb, worker_id: int) -> dict:
    rows = _run(sb.table("workers").select("*").eq("id", worker_id).limit(1), "load the worker")
    if not rows:
        raise HTTPException(status_code=404, detail="Worker not found.")
    return rows[0]


def _working_issues(sb) -> list[dict]:
    """Issues that currently count towards a worker's load."""
    return _run(
        sb.table("issues")
        .select("id, assigned_worker_id, priority, status, category, description, location_text, "
                "building_id, room, created_at, due_at")
        .in_("status", list(WORKING_STATUSES))
        .not_.is_("assigned_worker_id", "null"),
        "load active assignments",
    )


def _issue_view(issue: dict, buildings: dict, workers_by_id: dict, now: datetime) -> dict:
    building = buildings.get(issue.get("building_id")) or {}
    worker = workers_by_id.get(issue.get("assigned_worker_id"))
    due = _effective_due(issue)
    return {
        **issue,
        "building_name": building.get("name") or issue.get("location_text"),
        "zone": building.get("zone"),
        "worker": (
            {"id": worker["id"], "name": worker.get("name"), "phone": worker.get("phone")}
            if worker else None
        ),
        "due_at_effective": _iso(due),
        "overdue": _is_overdue(issue, now),
    }


def allowed_transitions(issue: dict) -> list[str]:
    options = list(ALLOWED_TRANSITIONS.get(issue.get("status"), []))
    if not issue.get("assigned_worker_id"):
        # Moving to assigned / in_progress needs a worker: use the assign endpoint instead.
        options = [s for s in options if s not in ("assigned", "in_progress")]
    return options


def _event(sb, issue_id: int, actor_id: str, type_: str, from_status=None, to_status=None, note=None):
    _run(
        sb.table("issue_events").insert({
            "issue_id": issue_id,
            "actor_id": actor_id,
            "type": type_,
            "from_status": from_status,
            "to_status": to_status,
            "note": note,
        }),
        "record the timeline event",
    )


def _end_open_assignment(sb, issue_id: int, now: datetime):
    _run(
        sb.table("assignments").update({"ended_at": _iso(now)}).eq("issue_id", issue_id).is_("ended_at", "null"),
        "close the current assignment",
    )


def _apply_status(sb, issue: dict, new_status: str, note: str | None, actor_id: str) -> dict:
    current = issue["status"]
    if new_status == current:
        raise HTTPException(status_code=409, detail=f"Complaint #{issue['id']} is already {current}.")
    if new_status not in ALLOWED_TRANSITIONS.get(current, []):
        raise HTTPException(
            status_code=409,
            detail=f"Complaint #{issue['id']}: can't move from {current} to {new_status}.",
        )
    if new_status in ("assigned", "in_progress") and not issue.get("assigned_worker_id"):
        raise HTTPException(status_code=409, detail="Assign a worker first.")

    now = _now()
    updates = {"status": new_status}
    event_type = "status_changed"

    if new_status == "resolved":
        updates["resolved_at"] = _iso(now)
        _end_open_assignment(sb, issue["id"], now)
    elif new_status == "closed":
        updates["closed_at"] = _iso(now)
    elif new_status == "rejected":
        updates["assigned_worker_id"] = None
        _end_open_assignment(sb, issue["id"], now)
    elif new_status == "open" and issue.get("assigned_worker_id"):
        updates["assigned_worker_id"] = None
        _end_open_assignment(sb, issue["id"], now)
        event_type = "unassigned"
    elif new_status == "in_progress" and current == "resolved":
        updates["resolved_at"] = None
        event_type = "reopened"
        _run(
            sb.table("assignments").insert({
                "issue_id": issue["id"],
                "worker_id": issue["assigned_worker_id"],
                "assigned_by": actor_id,
                "note": "Reopened",
            }),
            "reopen the assignment",
        )

    rows = _run(sb.table("issues").update(updates).eq("id", issue["id"]), "update the complaint")
    _event(sb, issue["id"], actor_id, event_type, current, new_status, note)
    return rows[0] if rows else {**issue, **updates}


def _worker_load_view(worker: dict, jobs: list[dict], now: datetime) -> dict:
    """Worker row + load numbers + availability label for the workload board."""
    max_active = max(int(worker.get("max_active") or 4), 1)
    effort = sum(PRIORITY_EFFORT.get(j.get("priority") or "normal", 1.0) for j in jobs)
    by_priority = {p: 0 for p in PRIORITIES}
    for job in jobs:
        by_priority[job.get("priority") or "normal"] = by_priority.get(job.get("priority") or "normal", 0) + 1
    overdue = sum(1 for j in jobs if _is_overdue(j, now))

    if worker.get("status") == "inactive":
        availability = "inactive"
    elif is_on_leave(worker, now.date()):
        availability = "on_leave"
    elif effort >= max_active:
        availability = "busy"
    elif now.isoweekday() not in (worker.get("work_days") or [1, 2, 3, 4, 5, 6]):
        availability = "off_today"
    else:
        availability = "available"

    return {
        **worker,
        "active_count": len(jobs),
        "effort_load": round(effort, 1),
        "load_pct": round(min(effort / max_active, 1.5) * 100),
        "by_priority": by_priority,
        "overdue_count": overdue,
        "availability": availability,
    }


def _worker_stats(sb, now: datetime, worker_ids=None) -> tuple[dict, dict]:
    """Per-worker {avg_resolution_h, reopen_rate, resolved_count, on_time_pct, assigned_today}
    and per-category average resolution hours."""
    query = (
        sb.table("issues")
        .select("id, assigned_worker_id, category, priority, created_at, due_at, resolved_at")
        .not_.is_("resolved_at", "null")
        .not_.is_("assigned_worker_id", "null")
    )
    if worker_ids:
        query = query.in_("assigned_worker_id", list(worker_ids))
    resolved = _run(query, "load worker statistics")
    reopened = _run(sb.table("issue_events").select("issue_id").eq("type", "reopened"), "load reopen events")
    today = _run(
        sb.table("assignments").select("worker_id").gte("assigned_at", _iso(_today_start(now))),
        "load today's assignments",
    )

    reopened_ids = {row["issue_id"] for row in reopened}
    stats: dict = {}
    by_category: dict = {}
    for issue in resolved:
        hours = _hours(issue.get("created_at"), issue.get("resolved_at"))
        if hours is None:
            continue
        s = stats.setdefault(issue["assigned_worker_id"], {"hours": [], "reopened": 0, "on_time": 0})
        s["hours"].append(hours)
        s["reopened"] += issue["id"] in reopened_ids
        due = _effective_due(issue)
        s["on_time"] += bool(due and _dt(issue["resolved_at"]) <= due)
        by_category.setdefault(str(issue.get("category") or "").lower(), []).append(hours)

    result = {}
    for worker_id, s in stats.items():
        n = len(s["hours"])
        result[worker_id] = {
            "avg_resolution_h": round(sum(s["hours"]) / n, 1),
            "reopen_rate": round(s["reopened"] / n, 2),
            "resolved_count": n,
            "on_time_pct": round(100 * s["on_time"] / n),
        }
    for row in today:
        result.setdefault(row["worker_id"], {}).setdefault("assigned_today", 0)
        result[row["worker_id"]]["assigned_today"] += 1

    category_avg = {cat: round(sum(h) / len(h), 1) for cat, h in by_category.items() if h}
    return result, category_avg


# ---------------------------------------------------------
# Scheduler glue (shared by recommended-workers and the "suggested worker" on lists / detail)
# ---------------------------------------------------------

def _ranking_context(sb, now: datetime) -> dict:
    """Everything the scheduler needs that doesn't depend on the issue. Load once per request."""
    stats, category_avg = _worker_stats(sb, now)
    return {"workers": _workers(sb), "working": _working_issues(sb), "stats": stats, "category_avg": category_avg}


def _rank_for(issue: dict, buildings: dict, ctx: dict, now: datetime, limit: int = 10) -> list[dict]:
    active_assignments = [
        {"worker_id": j["assigned_worker_id"], "issue_id": j["id"], "priority": j.get("priority")}
        for j in ctx["working"] if j["id"] != issue["id"]   # don't count this complaint against its own worker
    ]
    building = buildings.get(issue.get("building_id")) or {}
    return recommend_workers(
        {
            "id": issue["id"],
            "category": issue.get("category"),
            "building_id": issue.get("building_id"),
            "zone": building.get("zone"),
            "priority": issue.get("priority") or "normal",
        },
        ctx["workers"],
        active_assignments,
        now,
        stats=ctx["stats"],
        limit=limit,
        category_avg_h=ctx["category_avg"].get(str(issue.get("category") or "").lower()),
    )


def _needs_suggestion(issue: dict) -> bool:
    return issue.get("status") == "open" and not issue.get("assigned_worker_id")


def _suggestion(issue: dict, buildings: dict, ctx: dict, now: datetime) -> dict | None:
    """Top scheduler pick for an unassigned complaint. Suggest only: nothing is assigned here."""
    ranked = _rank_for(issue, buildings, ctx, now, limit=1)
    if not ranked:
        return None
    top = ranked[0]
    return {
        "worker": {"id": top["worker"]["id"], "name": top["worker"]["name"]},
        "score": top["score"],
        "eligible": top["eligible"],
        "reasons": top["reasons"][:3],
        "flags": top["flags"],
        "eta_text": top["eta_text"],
    }


def _validation_error(exc: ValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    message = str(first.get("msg", "Invalid data.")).removeprefix("Value error, ")
    raise HTTPException(status_code=422, detail=message)


# ---------------------------------------------------------
# Meta + dashboard
# ---------------------------------------------------------

@router.get("/meta")
def meta(user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    buildings = sorted(_buildings(sb).values(), key=lambda b: b["name"])
    return {
        "success": True,
        "categories": CATEGORIES,
        "statuses": STATUSES,
        "priorities": PRIORITIES,
        "sla_hours": SLA_HOURS,
        "transitions": ALLOWED_TRANSITIONS,
        "buildings": buildings,
        "zones": sorted({b["zone"] for b in buildings if b.get("zone")}),
    }


@router.get("/summary")
def summary(user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    now = _now()
    issues = _run(
        sb.table("issues").select("*").order("created_at", desc=True).limit(2000),
        "load complaints",
    )
    workers = _workers(sb)
    buildings = _buildings(sb)
    workers_by_id = {w["id"]: w for w in workers}
    today_start = _today_start(now)

    active = [i for i in issues if i["status"] in ACTIVE_STATUSES]
    counts = {
        "open": sum(1 for i in issues if i["status"] == "open"),
        "unassigned": sum(1 for i in active if not i.get("assigned_worker_id")),
        "in_progress": sum(1 for i in issues if i["status"] == "in_progress"),
        "overdue": sum(1 for i in active if _is_overdue(i, now)),
        "resolved_today": sum(
            1 for i in issues if (_dt(i.get("resolved_at")) or datetime.min.replace(tzinfo=IST)) >= today_start
        ),
        "active": len(active),
    }

    def attention_rank(issue):
        return (
            not _is_overdue(issue, now),
            PRIORITY_RANK.get(issue.get("priority") or "normal", 2),
            bool(issue.get("assigned_worker_id")),
            _dt(issue.get("created_at")),
        )

    needs_attention = [
        i for i in active
        if _is_overdue(i, now) or not i.get("assigned_worker_id") or i.get("priority") in ("urgent", "high")
    ]
    needs_attention.sort(key=attention_rank)

    working = [i for i in issues if i["status"] in WORKING_STATUSES and i.get("assigned_worker_id")]
    capacity = {"available": 0, "busy": 0, "on_leave": 0, "off_today": 0, "inactive": 0}
    for worker in workers:
        jobs = [j for j in working if j["assigned_worker_id"] == worker["id"]]
        capacity[_worker_load_view(worker, jobs, now)["availability"]] += 1

    return {
        "success": True,
        "counts": counts,
        "needs_attention": [_issue_view(i, buildings, workers_by_id, now) for i in needs_attention[:5]],
        "capacity": capacity,
        "worker_count": len(workers),
    }


# ---------------------------------------------------------
# Complaints
# ---------------------------------------------------------

@router.get("/issues")
def list_issues(
    status: str | None = Query(default=None, description="one status or comma separated, or 'active'"),
    category: str | None = None,
    building_id: str | None = None,
    priority: str | None = None,
    assigned: bool | None = None,
    overdue: bool | None = None,
    worker_id: int | None = None,
    q: str | None = None,
    sort: str = Query(default="newest", pattern="^(newest|oldest|priority|due)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    with_suggestion: bool = Query(default=True, description="attach the scheduler's top pick to unassigned open rows"),
    user: dict = Depends(require_staff),
    sb=Depends(get_user_supabase),
):
    query = sb.table("issues").select("*")
    if status:
        wanted = list(ACTIVE_STATUSES) if status == "active" else [s.strip() for s in status.split(",") if s.strip()]
        if any(s not in STATUSES for s in wanted):
            raise HTTPException(status_code=422, detail="Invalid status filter.")
        query = query.in_("status", wanted)
    if category:
        query = query.ilike("category", category)      # older rows may be "Electrical" vs "electrical"
    if building_id:
        query = query.eq("building_id", building_id)
    if priority:
        if priority not in PRIORITIES:
            raise HTTPException(status_code=422, detail="Invalid priority filter.")
        query = query.eq("priority", priority)
    if worker_id is not None:
        query = query.eq("assigned_worker_id", worker_id)
    if assigned is True:
        query = query.not_.is_("assigned_worker_id", "null")
    elif assigned is False:
        query = query.is_("assigned_worker_id", "null")

    rows = _run(query.order("created_at", desc=True).limit(2000), "load complaints")
    now = _now()

    if overdue is not None:
        rows = [r for r in rows if _is_overdue(r, now) == overdue]
    if q and q.strip():
        needle = q.strip().lower().lstrip("#")
        rows = [
            r for r in rows
            if needle == str(r["id"])
            or any(needle in str(r.get(field) or "").lower() for field in ("description", "location_text", "room", "category"))
        ]

    if sort == "oldest":
        rows.sort(key=lambda r: _dt(r["created_at"]))
    elif sort == "priority":
        rows.sort(key=lambda r: (PRIORITY_RANK.get(r.get("priority") or "normal", 2), _effective_due(r) or now))
    elif sort == "due":
        rows.sort(key=lambda r: (r["status"] not in ACTIVE_STATUSES, _effective_due(r) or now))

    buildings = _buildings(sb)
    page = rows[offset: offset + limit]
    ctx = _ranking_context(sb, now) if with_suggestion and any(_needs_suggestion(r) for r in page) else None
    workers_by_id = {w["id"]: w for w in (ctx["workers"] if ctx else _workers(sb))}
    views = []
    for r in page:
        item = _issue_view(r, buildings, workers_by_id, now)
        if ctx and _needs_suggestion(r):
            item["suggestion"] = _suggestion(r, buildings, ctx, now)
        views.append(item)
    return {
        "success": True,
        "issues": views,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
    }


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    now = _now()
    issue = _get_issue(sb, issue_id)
    buildings = _buildings(sb)
    worker = _get_worker(sb, issue["assigned_worker_id"]) if issue.get("assigned_worker_id") else None
    workers_by_id = {worker["id"]: worker} if worker else {}

    notes = _run(sb.table("issue_notes").select("*").eq("issue_id", issue_id).order("created_at"), "load notes")
    events = _run(sb.table("issue_events").select("*").eq("issue_id", issue_id).order("created_at"), "load timeline")
    assignments = _run(
        sb.table("assignments").select("*").eq("issue_id", issue_id).order("assigned_at"),
        "load assignment history",
    )
    people = _profiles(
        sb,
        [issue.get("user_id")] + [n.get("author_id") for n in notes] + [e.get("actor_id") for e in events],
    )

    reporter = people.get(issue.get("user_id")) or {}
    reporter_email = None
    try:  # email lives in auth.users; only the service role can read it
        auth_user = get_supabase_client().auth.admin.get_user_by_id(issue["user_id"])
        reporter_email = auth_user.user.email if auth_user and auth_user.user else None
    except Exception:
        logger.debug("Could not load reporter email", exc_info=True)

    worker_names = {worker["id"]: worker["name"]} if worker else {}
    other_ids = {a["worker_id"] for a in assignments} - set(worker_names)
    if other_ids:
        for row in _run(sb.table("workers").select("id, name").in_("id", list(other_ids)), "load workers"):
            worker_names[row["id"]] = row["name"]

    def person(pid):
        return (people.get(pid) or {}).get("full_name") or "Admin"

    timeline = [{
        "type": "created",
        "to_status": "open",
        "created_at": issue["created_at"],
        "actor": reporter.get("full_name") or "Student",
        "note": None,
    }] + [
        {**e, "actor": person(e.get("actor_id"))} for e in events
    ]

    view = _issue_view(issue, buildings, workers_by_id, now)
    if _needs_suggestion(issue):
        view["suggestion"] = _suggestion(issue, buildings, _ranking_context(sb, now), now)
    if worker:
        view["worker"] = {k: worker.get(k) for k in ("id", "name", "phone", "skills", "primary_skill", "status")}
        open_assignment = next((a for a in reversed(assignments) if not a.get("ended_at")), None)
        view["worker"]["assigned_at"] = open_assignment.get("assigned_at") if open_assignment else None

    return {
        "success": True,
        "issue": view,
        "reporter": {
            "id": issue.get("user_id"),
            "name": reporter.get("full_name") or "Student",
            "roll_number": reporter.get("roll_number"),
            "email": reporter_email,
        },
        "allowed_transitions": allowed_transitions(issue),
        "notes": [{**n, "author": person(n.get("author_id"))} for n in reversed(notes)],
        "timeline": timeline,
        "assignments": [{**a, "worker_name": worker_names.get(a["worker_id"])} for a in assignments],
    }


@router.patch("/issues/status")
def bulk_update_status(payload: BulkStatusUpdate, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    updated, failed = [], []
    for issue_id in payload.ids:
        try:
            issue = _get_issue(sb, issue_id)
            _apply_status(sb, issue, payload.status, payload.note, user["id"])
            updated.append(issue_id)
        except HTTPException as exc:
            failed.append({"id": issue_id, "detail": exc.detail})
    return {"success": not failed, "updated": updated, "failed": failed}


@router.patch("/issues/{issue_id}/status")
def update_status(issue_id: int, payload: StatusUpdate, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    issue = _apply_status(sb, _get_issue(sb, issue_id), payload.status, payload.note, user["id"])
    return {"success": True, "issue": issue, "message": f"Status changed to {payload.status.replace('_', ' ')}."}


@router.patch("/issues/{issue_id}/priority")
def update_priority(issue_id: int, payload: PriorityUpdate, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    issue = _get_issue(sb, issue_id)
    if issue.get("priority") == payload.priority:
        return {"success": True, "issue": issue}
    created = _dt(issue["created_at"]) or _now()
    due = created + timedelta(hours=SLA_HOURS[payload.priority])
    rows = _run(
        sb.table("issues").update({"priority": payload.priority, "due_at": _iso(due)}).eq("id", issue_id),
        "update priority",
    )
    _event(sb, issue_id, user["id"], "priority_changed",
           note=f"Priority {issue.get('priority') or 'normal'} → {payload.priority}")
    return {"success": True, "issue": rows[0] if rows else issue}


@router.post("/issues/{issue_id}/notes", status_code=201)
def add_note(issue_id: int, payload: NoteCreate, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    _get_issue(sb, issue_id)
    rows = _run(
        sb.table("issue_notes").insert({"issue_id": issue_id, "author_id": user["id"], "text": payload.text}),
        "save the note",
    )
    return {"success": True, "note": rows[0] if rows else None}


# ---------------------------------------------------------
# Assignment
# ---------------------------------------------------------

@router.get("/issues/{issue_id}/recommended-workers")
def recommended_workers(
    issue_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    user: dict = Depends(require_staff),
    sb=Depends(get_user_supabase),
):
    now = _now()
    issue = _get_issue(sb, issue_id)
    buildings = _buildings(sb)
    ranked = _rank_for(issue, buildings, _ranking_context(sb, now), now, limit)
    current = issue.get("assigned_worker_id")
    for item in ranked:
        item["is_current"] = item["worker"]["id"] == current
    return {
        "success": True,
        "issue": _issue_view(issue, buildings, {}, now),
        "recommendations": ranked,
        "has_eligible": any(r["eligible"] for r in ranked),
    }


@router.post("/issues/{issue_id}/assign")
def assign(issue_id: int, payload: AssignRequest, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    now = _now()
    issue = _get_issue(sb, issue_id)
    if issue["status"] not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"A {issue['status']} complaint can't be assigned.")
    worker = _get_worker(sb, payload.worker_id)
    if worker.get("status") == "inactive":
        raise HTTPException(status_code=409, detail=f"{worker['name']} is inactive.")

    previous = issue.get("assigned_worker_id")
    if previous == worker["id"]:
        raise HTTPException(status_code=409, detail=f"Already assigned to {worker['name']}.")
    reason = (payload.reason or "").strip()
    if previous and not reason:
        raise HTTPException(status_code=422, detail="A reason is required when reassigning.")

    _end_open_assignment(sb, issue_id, now)
    _run(
        sb.table("assignments").insert({
            "issue_id": issue_id,
            "worker_id": worker["id"],
            "assigned_by": user["id"],
            "note": payload.note,
            "reason": reason or None,
        }),
        "save the assignment",
    )
    updates = {"assigned_worker_id": worker["id"], "status": "assigned"}
    if not issue.get("due_at"):
        updates["due_at"] = _iso(_effective_due(issue))
    rows = _run(sb.table("issues").update(updates).eq("id", issue_id), "assign the complaint")
    _run(sb.table("workers").update({"last_assigned_at": _iso(now)}).eq("id", worker["id"]), "update the worker")

    note = f"Assigned to {worker['name']}"
    if reason:
        note += f" (reason: {reason})"
    if payload.note:
        note += f" — {payload.note}"
    _event(sb, issue_id, user["id"], "reassigned" if previous else "assigned", issue["status"], "assigned", note)

    return {
        "success": True,
        "issue": rows[0] if rows else {**issue, **updates},
        "worker": {k: worker.get(k) for k in ("id", "name", "phone")},
        "message": f"Assigned to {worker['name']}.",
    }


@router.post("/issues/{issue_id}/unassign")
def unassign(issue_id: int, payload: UnassignRequest, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    issue = _get_issue(sb, issue_id)
    if not issue.get("assigned_worker_id"):
        raise HTTPException(status_code=409, detail="No worker is assigned.")
    if issue["status"] not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"A {issue['status']} complaint can't be unassigned.")
    _end_open_assignment(sb, issue_id, _now())
    rows = _run(
        sb.table("issues").update({"assigned_worker_id": None, "status": "open"}).eq("id", issue_id),
        "unassign the complaint",
    )
    _event(sb, issue_id, user["id"], "unassigned", issue["status"], "open", payload.reason)
    return {"success": True, "issue": rows[0] if rows else issue}


# ---------------------------------------------------------
# Workers
# ---------------------------------------------------------

@router.get("/workers")
def list_workers(
    skill: str | None = None,
    zone: str | None = None,
    availability: str | None = None,
    q: str | None = None,
    sort: str = Query(default="load_desc", pattern="^(load_desc|load_asc|name|overdue)$"),
    include_inactive: bool = False,
    user: dict = Depends(require_staff),
    sb=Depends(get_user_supabase),
):
    now = _now()
    working = _working_issues(sb)
    rows = []
    for worker in _workers(sb):
        jobs = [j for j in working if j["assigned_worker_id"] == worker["id"]]
        rows.append(_worker_load_view(worker, jobs, now))

    if not include_inactive and availability != "inactive":
        rows = [r for r in rows if r["availability"] != "inactive"]
    if skill:
        rows = [r for r in rows if skill in (r.get("skills") or [])]
    if zone:
        rows = [r for r in rows if zone in (r.get("zones") or []) or not (r.get("zones") or r.get("building_ids"))]
    if availability:
        rows = [r for r in rows if r["availability"] == availability]
    if q and q.strip():
        needle = q.strip().lower()
        rows = [r for r in rows if needle in (r.get("name") or "").lower() or needle in (r.get("phone") or "")]

    if sort == "load_desc":
        rows.sort(key=lambda r: (-r["load_pct"], r["name"].lower()))
    elif sort == "load_asc":
        rows.sort(key=lambda r: (r["load_pct"], r["name"].lower()))
    elif sort == "overdue":
        rows.sort(key=lambda r: (-r["overdue_count"], -r["load_pct"]))
    else:
        rows.sort(key=lambda r: r["name"].lower())

    team = {"total": len(rows), "available": 0, "busy": 0, "on_leave": 0, "off_today": 0, "inactive": 0}
    for r in rows:
        team[r["availability"]] += 1
    return {"success": True, "workers": rows, "team": team}


@router.post("/workers", status_code=201)
def create_worker(payload: dict, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    try:
        data = WorkerCreate(**payload)
    except ValidationError as exc:
        _validation_error(exc)
    row = data.model_dump(mode="json", exclude_none=True)
    row.setdefault("primary_skill", data.skills[0])
    rows = _run(sb.table("workers").insert(row), "add the worker")
    return {"success": True, "worker": rows[0] if rows else row}


@router.get("/workers/{worker_id}")
def get_worker(worker_id: int, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    now = _now()
    worker = _get_worker(sb, worker_id)
    buildings = _buildings(sb)
    jobs = [j for j in _working_issues(sb) if j["assigned_worker_id"] == worker_id]
    stats, _ = _worker_stats(sb, now, [worker_id])
    week_start = _today_start(now) - timedelta(days=now.weekday())
    this_week = _run(
        sb.table("assignments").select("id").eq("worker_id", worker_id).gte("assigned_at", _iso(week_start)),
        "load this week's jobs",
    )
    s = stats.get(worker_id) or {}
    jobs.sort(key=lambda j: (PRIORITY_RANK.get(j.get("priority") or "normal", 2), _effective_due(j) or now))
    return {
        "success": True,
        "worker": _worker_load_view(worker, jobs, now),
        "active_issues": [_issue_view(j, buildings, {worker_id: worker}, now) for j in jobs],
        "stats": {
            "jobs_this_week": len(this_week),
            "resolved_count": s.get("resolved_count", 0),
            "avg_resolution_h": s.get("avg_resolution_h"),
            "reopen_rate": s.get("reopen_rate"),
            "on_time_pct": s.get("on_time_pct"),
        },
    }


@router.patch("/workers/{worker_id}")
def update_worker(worker_id: int, payload: dict, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    current = _get_worker(sb, worker_id)
    try:
        data = WorkerUpdate(**payload)
    except ValidationError as exc:
        _validation_error(exc)
    changes = data.model_dump(mode="json", exclude_unset=True)
    skills = changes.get("skills", current.get("skills") or [])
    primary = changes.get("primary_skill", current.get("primary_skill"))
    if primary not in skills:
        changes["primary_skill"] = skills[0] if skills else None
    if not changes:
        return {"success": True, "worker": current}
    rows = _run(sb.table("workers").update(changes).eq("id", worker_id), "update the worker")
    return {"success": True, "worker": rows[0] if rows else {**current, **changes}}


@router.patch("/workers/{worker_id}/availability")
def set_availability(worker_id: int, payload: dict, user: dict = Depends(require_staff), sb=Depends(get_user_supabase)):
    try:
        data = AvailabilityUpdate(**payload)
    except ValidationError as exc:
        _validation_error(exc)
    worker = _get_worker(sb, worker_id)
    buildings = _buildings(sb)
    now = _now()
    jobs = [j for j in _working_issues(sb) if j["assigned_worker_id"] == worker_id]
    if data.status == "inactive" and jobs and not data.force:
        raise HTTPException(
            status_code=409,
            detail=f"{worker['name']} still has {len(jobs)} active complaint(s). Reassign them first.",
        )
    changes = {
        "status": data.status,
        "leave_from": data.leave_from.isoformat() if data.leave_from else None,
        "leave_to": data.leave_to.isoformat() if data.leave_to else None,
    }
    rows = _run(sb.table("workers").update(changes).eq("id", worker_id), "update availability")
    updated = rows[0] if rows else {**worker, **changes}
    return {
        "success": True,
        "worker": _worker_load_view(updated, jobs, now),
        "active_issues": [_issue_view(j, buildings, {worker_id: worker}, now) for j in jobs],
    }


@router.get("/workers/{worker_id}/history")
def worker_history(
    worker_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_staff),
    sb=Depends(get_user_supabase),
):
    _get_worker(sb, worker_id)
    now = _now()
    rows = _run(
        sb.table("issues").select("*", count="exact")
        .eq("assigned_worker_id", worker_id)
        .in_("status", ["resolved", "closed"])
        .order("resolved_at", desc=True)
        .range(offset, offset + limit - 1),
        "load worker history",
    )
    buildings = _buildings(sb)
    return {
        "success": True,
        "issues": [
            {**_issue_view(r, buildings, {}, now),
             "resolution_h": _hours(r.get("created_at"), r.get("resolved_at"))}
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------
# Analytics
# ---------------------------------------------------------

@router.get("/analytics")
def analytics(
    days: int | None = Query(default=30, ge=1, le=366),
    date_from: date | None = None,
    date_to: date | None = None,
    user: dict = Depends(require_staff),
    sb=Depends(get_user_supabase),
):
    now = _now()
    end_day = date_to or now.date()
    start_day = date_from or (end_day - timedelta(days=(days or 30) - 1))
    if start_day > end_day:
        raise HTTPException(status_code=422, detail="'from' must be before 'to'.")
    start = datetime.combine(start_day, time.min, tzinfo=IST)
    end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=IST)

    issues = _run(
        sb.table("issues").select("*").gte("created_at", _iso(start)).lt("created_at", _iso(end)).limit(5000),
        "load analytics",
    )
    ids = [i["id"] for i in issues]
    assignments = _run(
        sb.table("assignments").select("issue_id, worker_id, assigned_at").in_("issue_id", ids), "load assignments"
    ) if ids else []
    reopened = {
        e["issue_id"] for e in _run(
            sb.table("issue_events").select("issue_id").eq("type", "reopened").in_("issue_id", ids), "load events"
        )
    } if ids else set()
    buildings = _buildings(sb)
    workers = {w["id"]: w for w in _workers(sb)}

    first_assigned = {}
    for a in assignments:
        at = _dt(a["assigned_at"])
        if a["issue_id"] not in first_assigned or at < first_assigned[a["issue_id"]]:
            first_assigned[a["issue_id"]] = at

    by_category, by_building, by_status, weekly = {}, {}, {}, {}
    assign_hours, resolve_hours = [], []
    breached = resolved_count = 0
    per_worker = {}
    for issue in issues:
        cat = str(issue.get("category") or "other").strip().lower()
        by_category[cat] = by_category.get(cat, 0) + 1
        by_status[issue["status"]] = by_status.get(issue["status"], 0) + 1
        name = (buildings.get(issue.get("building_id")) or {}).get("name") or issue.get("location_text") or "Unknown"
        by_building[name] = by_building.get(name, 0) + 1
        created = _dt(issue["created_at"]).astimezone(IST)
        week = (created.date() - timedelta(days=created.weekday())).isoformat()
        weekly[week] = weekly.get(week, 0) + 1

        if issue["id"] in first_assigned:
            assign_hours.append(_hours(created, first_assigned[issue["id"]]))
        due = _effective_due(issue)
        resolved_at = _dt(issue.get("resolved_at"))
        if resolved_at:
            resolved_count += 1
            resolve_hours.append(_hours(created, resolved_at))
            if due and resolved_at > due:
                breached += 1
        elif _is_overdue(issue, now):
            breached += 1

        wid = issue.get("assigned_worker_id")
        if wid and resolved_at:
            w = per_worker.setdefault(wid, {"done": 0, "hours": [], "on_time": 0, "reopened": 0})
            w["done"] += 1
            w["hours"].append(_hours(created, resolved_at))
            w["on_time"] += bool(due and resolved_at <= due)
            w["reopened"] += issue["id"] in reopened

    def avg(values):
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 1) if values else None

    def pct(part, whole):
        return round(100 * part / whole) if whole else None

    # every week in range, including empty ones
    trend, cursor = [], start_day - timedelta(days=start_day.weekday())
    while cursor <= end_day:
        trend.append({"week_start": cursor.isoformat(), "count": weekly.get(cursor.isoformat(), 0)})
        cursor += timedelta(days=7)

    measured = resolved_count + sum(1 for i in issues if not i.get("resolved_at") and _is_overdue(i, now))
    return {
        "success": True,
        "range": {"from": start_day.isoformat(), "to": end_day.isoformat()},
        "totals": {
            "complaints": len(issues),
            "resolved": resolved_count,
            "avg_assign_h": avg(assign_hours),
            "avg_resolve_h": avg(resolve_hours),
            "sla_breach_pct": pct(breached, measured),
            "reopen_pct": pct(len(reopened), resolved_count),
        },
        "by_category": sorted(({"category": k, "count": v} for k, v in by_category.items()), key=lambda r: -r["count"]),
        "by_status": by_status,
        "hotspots": sorted(({"building": k, "count": v} for k, v in by_building.items()), key=lambda r: -r["count"])[:8],
        "weekly": trend,
        "workers": sorted(
            (
                {
                    "worker_id": wid,
                    "name": (workers.get(wid) or {}).get("name", f"Worker #{wid}"),
                    "done": w["done"],
                    "avg_resolution_h": avg(w["hours"]),
                    "on_time_pct": pct(w["on_time"], w["done"]),
                    "reopen_pct": pct(w["reopened"], w["done"]),
                }
                for wid, w in per_worker.items()
            ),
            key=lambda r: -r["done"],
        ),
    }
