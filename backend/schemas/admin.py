"""Request models for routers/admin.py.

TODO
  [ ] StatusUpdate        status: Literal[open, assigned, in_progress, resolved, closed, rejected], note: str | None
                          (validator: note required for rejected / closed)
  [ ] PriorityUpdate      priority: Literal[low, normal, high, urgent]
  [ ] NoteCreate          text: str (1..2000)
  [ ] AssignRequest       worker_id: str, note: str | None, reason: str | None (required when reassigning)
  [ ] UnassignRequest     reason: str
  [ ] WorkerCreate        name, phone (10 digits), skills: list[str] (>=1), primary_skill, zones, buildings,
                          shift_start, shift_end (time), work_days: list[int 0..6], max_active: int 1..10
  [ ] WorkerUpdate        same fields, all optional
  [ ] AvailabilityUpdate  status: Literal[available, on_leave, inactive], leave_from / leave_to: date | None
                          (validator: dates required for on_leave, leave_from <= leave_to)
"""
