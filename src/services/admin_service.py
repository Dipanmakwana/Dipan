"""ADMIN SERVICE - calls to the PHO/admin endpoints (backend/routers/admin.py) via core/api_client.py.
All endpoints require a staff token; the backend enforces it (require_staff), the app only hides screens.

TODO (agree endpoint names with the backend owner)
  Complaints
  [ ] get_summary()                                   GET   /admin/summary
  [ ] list_issues(status=None, category=None, building_id=None, priority=None,
                  assigned=None, overdue=None, q=None, sort="newest", limit=20, offset=0)
                                                      GET   /admin/issues
  [ ] get_issue(issue_id)                             GET   /admin/issues/{id}        (allowed_transitions, worker, notes, timeline)
  [ ] update_status(issue_id, status, note=None)      PATCH /admin/issues/{id}/status
  [ ] bulk_update_status(ids, status, note=None)      PATCH /admin/issues/status     (optional)
  [ ] set_priority(issue_id, priority)                PATCH /admin/issues/{id}/priority
  [ ] add_note(issue_id, text)                        POST  /admin/issues/{id}/notes
  Assignment
  [ ] recommended_workers(issue_id)                   GET   /admin/issues/{id}/recommended-workers
  [ ] assign(issue_id, worker_id, note=None, reason=None)   POST /admin/issues/{id}/assign
  [ ] unassign(issue_id, reason)                      POST  /admin/issues/{id}/unassign
  Workers
  [ ] list_workers()                                  GET   /admin/workers
  [ ] get_worker(worker_id)                           GET   /admin/workers/{id}
  [ ] worker_history(worker_id, limit, offset)        GET   /admin/workers/{id}/history
  [ ] create_worker(payload)                          POST  /admin/workers
  [ ] update_worker(worker_id, payload)               PATCH /admin/workers/{id}
  [ ] set_availability(worker_id, status, leave_from=None, leave_to=None)
                                                      PATCH /admin/workers/{id}/availability
  [ ] get_workload(skill=None, zone=None, availability=None, q=None, sort="load_desc")
                                                      GET   /admin/workload
  Analytics
  [ ] get_analytics(date_from, date_to)               GET   /admin/analytics
"""
