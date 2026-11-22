"""WORKER SCHEDULER - recommends workers for a complaint, sorted best first.

Used by GET /admin/issues/{id}/recommended-workers (routers/admin.py). Pure function: no DB calls here,
the router loads the data and passes it in, so this file is easy to unit-test.

Inputs
  issue               {id, category, building_id, zone, priority: low|normal|high|urgent}
  workers             rows of public.workers (skills, zones, building_ids, shift_start, shift_end,
                      work_days [1=Mon..7=Sun], max_active, status, leave_from, leave_to, last_assigned_at)
  active_assignments  [{worker_id, issue_id, priority}]  - jobs in status assigned / in_progress
  now                 timezone-aware datetime in campus time (IST)
  stats (optional)    {worker_id: {avg_resolution_h, reopen_rate, assigned_today}}
  category_avg_h      average resolution hours for this category (for the performance term)

Algorithm
  1. Effort-weighted load = sum of PRIORITY_EFFORT[priority] over the worker's active jobs.
  2. Hard filters (eligible): available (not inactive, not inside leave dates), has the category skill,
     works today and shift not over, effort load < max_active, covers the building / zone.
  3. Score (0..100) = weighted sum of skill, capacity, proximity, shift, perf minus a fairness penalty.
     Urgent / high priority issues use URGENT_WEIGHTS (capacity + proximity matter more).
  4. Sort: score desc, then fewer active jobs, then least recently assigned (round robin).
  5. Fallback when nobody is eligible: relax load cap -> shift -> zone and return those candidates with
     flags (overloaded / off_shift / out_of_zone), eligible=False and a 40 % score penalty.
     Workers on leave, inactive or without the skill are never recommended (use the manual list).

Output (best first)
  {"worker": {...}, "score": int 0-100, "breakdown": {skill, capacity, proximity, shift, perf, fairness},
   "reasons": [str], "eta_text": str, "flags": [str], "eligible": bool}
"""
from datetime import date, datetime, time

PRIORITY_EFFORT = {"low": 0.5, "normal": 1.0, "high": 1.5, "urgent": 2.0}

DEFAULT_WEIGHTS = {"skill": 0.30, "capacity": 0.25, "proximity": 0.20, "shift": 0.10, "perf": 0.10, "fairness": 0.05}
URGENT_WEIGHTS = {"skill": 0.25, "capacity": 0.30, "proximity": 0.25, "shift": 0.10, "perf": 0.05, "fairness": 0.05}

FALLBACK_PENALTY = 0.6
_RELAXABLE = ("overloaded", "off_shift", "out_of_zone")


def _parse_time(value, default: time) -> time:
    if isinstance(value, time):
        return value
    if not value:
        return default
    parts = [int(p) for p in str(value).split(":")[:2]]
    return time(parts[0], parts[1] if len(parts) > 1 else 0)


def _parse_date(value):
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def is_on_leave(worker: dict, today: date) -> bool:
    if worker.get("status") != "on_leave":
        return False
    start, end = _parse_date(worker.get("leave_from")), _parse_date(worker.get("leave_to"))
    if start is None or end is None:
        return True
    return start <= today <= end


def worker_load(worker_id, active_assignments: list[dict]) -> tuple[int, float, list[dict]]:
    jobs = [a for a in active_assignments if a.get("worker_id") == worker_id]
    effort = sum(PRIORITY_EFFORT.get(a.get("priority") or "normal", 1.0) for a in jobs)
    return len(jobs), effort, jobs


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _fmt_time(value: time) -> str:
    return value.strftime("%H:%M")


def recommend_workers(
    issue: dict,
    workers: list[dict],
    active_assignments: list[dict],
    now: datetime,
    stats: dict | None = None,
    limit: int = 10,
    category_avg_h: float | None = None,
) -> list[dict]:
    """Return workers sorted best-first for `issue`. See module docstring."""
    stats = stats or {}
    category = (issue.get("category") or "").strip().lower()
    priority = issue.get("priority") or "normal"
    building_id = issue.get("building_id")
    zone = issue.get("zone")
    weights = URGENT_WEIGHTS if priority in ("urgent", "high") else DEFAULT_WEIGHTS
    today = now.date()
    now_t = now.time()

    pool = [
        w for w in workers
        if w.get("status") != "inactive"
        and not is_on_leave(w, today)
        and category in [s.lower() for s in (w.get("skills") or [])]
    ]
    if not pool:
        return []

    assigned_today = [float((stats.get(w["id"]) or {}).get("assigned_today", 0)) for w in pool]
    team_avg_today = sum(assigned_today) / len(assigned_today)

    results = []
    for w in pool:
        flags, reasons = [], []
        active_count, effort, _ = worker_load(w["id"], active_assignments)
        max_active = max(int(w.get("max_active") or 4), 1)

        # skill
        primary = (w.get("primary_skill") or "").lower()
        skill = 1.0 if primary == category else 0.7
        reasons.append(f"{'Primary skill' if skill == 1.0 else 'Skilled in'}: {category.title()}")

        # capacity
        capacity = _clamp(1 - effort / max_active)
        if effort >= max_active:
            flags.append("overloaded")
            reasons.append(f"Full load ({active_count}/{max_active})")
        elif active_count == 0:
            reasons.append("No active jobs")
        elif capacity >= 0.5:
            reasons.append(f"Light load ({active_count}/{max_active})")
        else:
            reasons.append(f"Busy ({active_count}/{max_active})")

        # proximity
        w_buildings = w.get("building_ids") or []
        w_zones = w.get("zones") or []
        if building_id and building_id in w_buildings:
            proximity = 1.0
            reasons.append("Covers this building")
        elif zone and zone in w_zones:
            proximity = 0.6
            reasons.append(f"Works in {zone} zone")
        elif not w_buildings and not w_zones:
            proximity = 0.5
            reasons.append("Covers whole campus")
        else:
            proximity = 0.2
            flags.append("out_of_zone")
            reasons.append("Outside usual area")

        # shift
        start = _parse_time(w.get("shift_start"), time(9, 0))
        end = _parse_time(w.get("shift_end"), time(18, 0))
        works_today = now.isoweekday() in (w.get("work_days") or [1, 2, 3, 4, 5, 6])
        eta_text = "Free now" if active_count == 0 else f"After {active_count} job{'s' if active_count > 1 else ''}"
        if works_today and start <= now_t < end:
            hours_left = (datetime.combine(today, end) - datetime.combine(today, now_t)).total_seconds() / 3600
            shift = 1.0 if hours_left >= 2 else 0.5
            reasons.append(f"On shift till {_fmt_time(end)}")
        elif works_today and now_t < start:
            shift = 0.3
            reasons.append(f"Shift starts {_fmt_time(start)}")
            eta_text = f"From {_fmt_time(start)}"
        else:
            shift = 0.0
            flags.append("off_shift")
            reasons.append("Off shift now" if works_today else "Not working today")
            eta_text = "Off shift"

        # performance
        worker_stats = stats.get(w["id"]) or {}
        avg_h = worker_stats.get("avg_resolution_h")
        reopen_rate = worker_stats.get("reopen_rate")
        if avg_h is not None and category_avg_h:
            speed = _clamp(category_avg_h / max(avg_h, 0.1))
            quality = 1 - _clamp(reopen_rate or 0.0)
            perf = 0.5 * speed + 0.5 * quality
            if speed >= 0.9:
                reasons.append("Fast resolver")
        else:
            perf = 0.5

        # fairness
        today_count = float(worker_stats.get("assigned_today", 0))
        fairness = _clamp((today_count - team_avg_today) / max(team_avg_today, 1))

        breakdown = {
            "skill": round(skill, 2),
            "capacity": round(capacity, 2),
            "proximity": round(proximity, 2),
            "shift": round(shift, 2),
            "perf": round(perf, 2),
            "fairness": round(fairness, 2),
        }
        raw = (
            weights["skill"] * skill
            + weights["capacity"] * capacity
            + weights["proximity"] * proximity
            + weights["shift"] * shift
            + weights["perf"] * perf
            - weights["fairness"] * fairness
        )
        eligible = not any(f in _RELAXABLE for f in flags)
        score = 100 * _clamp(raw) * (1 if eligible else FALLBACK_PENALTY)

        results.append({
            "worker": {
                "id": w["id"],
                "name": w.get("name"),
                "phone": w.get("phone"),
                "skills": w.get("skills") or [],
                "primary_skill": w.get("primary_skill"),
                "status": w.get("status"),
                "max_active": max_active,
                "active_count": active_count,
                "effort_load": round(effort, 1),
                "shift_start": _fmt_time(start),
                "shift_end": _fmt_time(end),
            },
            "score": int(round(score)),
            "breakdown": breakdown,
            "reasons": reasons,
            "eta_text": eta_text,
            "flags": flags,
            "eligible": eligible,
            "_last": _parse_dt(w.get("last_assigned_at")),
        })

    epoch = datetime.min.replace(tzinfo=now.tzinfo)

    def best_first(r):
        last = r["_last"] or epoch
        if (last.tzinfo is None) != (epoch.tzinfo is None):
            last = last.replace(tzinfo=epoch.tzinfo)
        return (-r["score"], r["worker"]["active_count"], last)

    def relax_rank(r):
        # Relax load -> shift -> zone: breaking only the load cap is the mildest.
        return tuple(f in r["flags"] for f in reversed(_RELAXABLE))

    eligible = [r for r in results if r["eligible"]]
    if eligible:
        chosen = sorted(eligible, key=best_first)
    else:
        chosen = sorted(results, key=lambda r: (relax_rank(r), best_first(r)))

    for r in chosen:
        r.pop("_last", None)
    return chosen[:limit]
