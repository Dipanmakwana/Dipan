"""ADMIN (PHO / staff) ROUTER - complaint management, worker assignment, workload, analytics.

Auth TODO
  [x] require_staff dependency (dependencies.py): role comes from public.profiles.role == 'pho_admin'
      (NOT user_metadata, which users can edit). Use: user: dict = Depends(require_staff)
  [x] RLS: is_pho_admin() lets admins read/update all issues and manage workers, assignments,
      issue_events, issue_notes (migrations/001). Use get_user_supabase so RLS applies.

Endpoints TODO (all under /api/admin, all Depends(require_staff))
  Complaints
  [ ] GET   /summary                          KPI counts, needs-attention list, team capacity counts
  [ ] GET   /issues                           filters: status, category, building_id, priority, assigned, overdue,
                                              q, sort (newest|oldest|priority|due), limit, offset
  [ ] GET   /issues/{id}                      issue + reporter + worker + notes + timeline + allowed_transitions
  [ ] PATCH /issues/{id}/status               validate against ALLOWED_TRANSITIONS, write issue_events row,
                                              set resolved_at / closed_at
  [ ] PATCH /issues/status                    bulk version (optional)
  [ ] PATCH /issues/{id}/priority             recompute due_at from SLA_HOURS
  [ ] POST  /issues/{id}/notes                internal admin notes (never returned by student endpoints)
  Assignment
  [ ] GET   /issues/{id}/recommended-workers  load issue, workers, active assignments, stats
                                              -> services.scheduler.recommend_workers(...)
  [ ] POST  /issues/{id}/assign               close previous assignment (if any), insert assignment,
                                              set issues.assigned_worker_id, status open -> assigned, event row
  [ ] POST  /issues/{id}/unassign             end assignment, status back to open, event row
  Workers (no app accounts; managed only by staff)
  [ ] GET   /workers, POST /workers, GET /workers/{id}, PATCH /workers/{id}
  [ ] GET   /workers/{id}/history
  [ ] PATCH /workers/{id}/availability        warn / list active jobs when going on leave
  [ ] GET   /workload                         per worker: active count, effort load, by-priority counts, overdue
  Analytics
  [ ] GET   /analytics?date_from=&date_to=    by category, by building, weekly trend, avg assign/resolve time,
                                              SLA breach %, reopen %, per-worker performance

Status model TODO (keep identical to src/components/status_chip.py)
  STATUSES = open, assigned, in_progress, resolved, closed, rejected
  ALLOWED_TRANSITIONS = {
      "open":        ["assigned", "rejected"],
      "assigned":    ["in_progress", "open", "rejected"],
      "in_progress": ["resolved", "assigned"],
      "resolved":    ["closed", "in_progress"],      # in_progress = reopened
      "closed":      [],
      "rejected":    ["open"],
  }
  SLA_HOURS = {"urgent": 4, "high": 24, "normal": 72, "low": 168}

Database: DONE in backend/migrations/001_admin_side.sql (applied). Summary:
  workers(id uuid pk, name, phone, skills text[], primary_skill, zones text[], buildings text[],
          shift_start time, shift_end time, work_days int[], max_active int default 4,
          status text default 'available', leave_from date, leave_to date, last_assigned_at timestamptz,
          created_at timestamptz default now())
  assignments(id uuid pk, issue_id fk issues, worker_id fk workers, assigned_by uuid, note, reason,
              assigned_at timestamptz default now(), ended_at timestamptz)
  issue_events(id uuid pk, issue_id fk, actor_id uuid, type text, from_status, to_status, note,
               created_at timestamptz default now())
  issue_notes(id uuid pk, issue_id fk, author_id uuid, text, created_at)
  issues: add priority text default 'normal', assigned_worker_id uuid fk workers, due_at, resolved_at, closed_at
"""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["Admin"])
