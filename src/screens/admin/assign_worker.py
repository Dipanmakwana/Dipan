"""ASSIGN WORKER  |  side: admin (PHO / staff)  |  route: /admin/assign  |  navbar: hidden
Params: issue_id (required), reassign (bool, optional), e.g. go(page, "/admin/assign", issue_id=42)

The ranking comes from the backend scheduler (backend/services/scheduler.py). This screen only DISPLAYS it;
never re-rank on the client.

UI TODO
  [ ] AppBar row: Back icon (back(page)) + "Assign complaint #<issue_id>"
  [ ] Compact complaint summary at top: category, building, priority badge, SLA due
  [ ] "Recommended" list (already sorted by score), each row (components/worker_card.py, compact mode):
        - name, skills, score (0-100) as a small bar or number
        - current load "2 / 4 active" + ETA text ("Free now" / "Free after 2 jobs")
        - reason chips from the scheduler: "Plumbing expert", "Same building", "Light load", "On shift till 6 PM"
        - badges: "Best match" on row 1, warning badges "Overloaded" / "Off shift" for fallback candidates
        - expandable score breakdown (skill, capacity, proximity, shift, performance, fairness)
  [ ] Toggle "Show all workers" -> manual override list (includes ineligible workers, greyed with reason)
  [ ] Empty state: "No worker available right now" + show fallback candidates + link to /admin/workers
  [ ] Tap a worker -> confirm dialog:
        - note to worker (optional), reason (required when reassigning)
        - checkbox "Notify worker now" -> after success open SMS / WhatsApp / Call with a prefilled message
          ("Complaint #42: Plumbing, Hostel 3 Room 214, priority High")
        - Confirm button (spinner while saving)
  [ ] On success: snackbar "Assigned to <name>" then back(page) (detail screen reloads)
  [ ] Loading + error/retry states

Data TODO
  [ ] admin_service.recommended_workers(issue_id)   -> [{worker, score, breakdown, reasons, eta_text, flags}]
  [ ] admin_service.list_workers()                  (for "Show all workers")
  [ ] admin_service.assign(issue_id, worker_id, note, reason)
"""
import flet as ft

from core.router import back


def view(page: ft.Page, issue_id: int | None = None, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.TextButton("< Back", on_click=lambda e: back(page)),
                ft.Text(f"Assign complaint #{issue_id}", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("TODO: see docstring"),
            ]
        ),
    )
