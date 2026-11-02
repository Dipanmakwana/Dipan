"""WORKER CARD - one worker row (Workers/workload board, Assign worker list).

TODO
  [ ] build_worker_card(worker: dict, on_tap, compact: bool = False, recommendation: dict | None = None) -> ft.Control
  [ ] Shows: initials avatar, name, skills, availability dot (Available / Busy / On leave / Inactive), shift hours
  [ ] Load bar: active / max_active; colour green < 60%, amber < 100%, red at full load
  [ ] Active job counts by priority + overdue count (full mode)
  [ ] Recommendation mode (Assign screen): score, reason chips, ETA text, flags ("Overloaded", "Off shift")
  [ ] Whole card is tappable (on_tap(worker["id"]))
"""
