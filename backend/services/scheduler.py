"""WORKER SCHEDULER - recommends workers for a complaint, sorted best first.

Used by GET /admin/issues/{id}/recommended-workers (routers/admin.py). Pure function: no DB calls here,
the router loads the data and passes it in, so this file is easy to unit-test.

Inputs
  issue               {id, category, building_id, zone, priority: low|normal|high|urgent, created_at, due_at}
  workers             [{id, name, phone, skills: [str], primary_skill, zones: [str], buildings: [str],
                        shift_start, shift_end, work_days: [0..6], max_active, status: available|on_leave|inactive,
                        leave_from, leave_to, last_assigned_at}]
  active_assignments  [{worker_id, issue_id, priority, due_at, assigned_at}]   (open / assigned / in_progress jobs)
  stats (optional)    {worker_id: {avg_resolution_h, reopen_rate, assigned_today}}, plus category averages
  now                 timezone-aware datetime (Asia/Kolkata)

Algorithm TODO
  [ ] 1. Effort-weighted load per worker: sum of PRIORITY_EFFORT[priority] over their active jobs
         PRIORITY_EFFORT = {"low": 0.5, "normal": 1.0, "high": 1.5, "urgent": 2.0}
  [ ] 2. Hard filters (eligible):
         - status == "available" and today not inside [leave_from, leave_to]
         - issue.category in worker.skills
         - effort_load < max_active
         - works today (now.weekday() in work_days)
  [ ] 3. Score each eligible worker, every term in 0..1:
         skill      1.0 if category == primary_skill else 0.7
         capacity   1 - effort_load / max_active
         proximity  1.0 same building, 0.6 same zone, 0.2 otherwise (1.0 if worker covers whole campus? -> 0.5)
         shift      1.0 on shift with >= 2h left, 0.5 on shift with < 2h left, 0.3 shift starts later today
         perf       mix of (category_avg_h / worker_avg_h, capped at 1) and (1 - reopen_rate); 0.5 if no data
         fairness   penalty = clamp((assigned_today - team_avg_today) / max(team_avg_today, 1), 0, 1)
       score = 100 * (W.skill*skill + W.capacity*capacity + W.proximity*proximity
                      + W.shift*shift + W.perf*perf - W.fairness*fairness)
       Default weights  W = {skill: .30, capacity: .25, proximity: .20, shift: .10, perf: .10, fairness: .05}
       Urgent / high priority: move weight to capacity + proximity (e.g. capacity .30, proximity .25, perf .05)
  [ ] 4. Sort: score desc, then fewer active jobs, then oldest last_assigned_at (round robin)
  [ ] 5. Fallback when nobody is eligible: relax filters in order (load cap -> shift -> zone) and return those
         candidates with flags ["overloaded"] / ["off_shift"] / ["out_of_zone"] and a lower score
  [ ] 6. Build human-readable reasons, e.g. "Primary skill: Plumbing", "Same building", "Light load (1/4)",
         "On shift till 18:00"; and eta_text: "Free now" if no active jobs else "After N jobs"
  [ ] 7. Unit tests: tie-break, leave dates, overloaded fallback, urgent weighting, empty worker list

Output (one dict per worker, best first)
  {"worker": {...}, "score": 0-100 (int), "breakdown": {skill, capacity, proximity, shift, perf, fairness},
   "reasons": [str], "eta_text": str, "flags": [str], "eligible": bool}
"""
from datetime import datetime

PRIORITY_EFFORT = {"low": 0.5, "normal": 1.0, "high": 1.5, "urgent": 2.0}

DEFAULT_WEIGHTS = {"skill": 0.30, "capacity": 0.25, "proximity": 0.20, "shift": 0.10, "perf": 0.10, "fairness": 0.05}
URGENT_WEIGHTS = {"skill": 0.25, "capacity": 0.30, "proximity": 0.25, "shift": 0.10, "perf": 0.05, "fairness": 0.05}


def recommend_workers(
    issue: dict,
    workers: list[dict],
    active_assignments: list[dict],
    now: datetime,
    stats: dict | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return workers sorted best-first for `issue`. See module docstring."""
    raise NotImplementedError("TODO: implement the scheduler (see module docstring)")
