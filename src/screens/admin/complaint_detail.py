"""COMPLAINT DETAIL (admin)  |  side: admin (PHO / staff)  |  route: /admin/complaint  |  navbar: hidden
Param: id (issue id), e.g. go(page, "/admin/complaint", id=42). Shows a back button instead of the navbar.

UI TODO
  [ ] AppBar row: Back icon (back(page)) + "Complaint #<id>" + overflow menu (copy id, open student view)
  [ ] Header: category, StatusChip, priority badge, created date, SLA due / "Overdue by Xh"
  [ ] Photo strip (horizontal scroll) with tap-to-zoom
  [ ] Description + location card (building, room, location text, lat/lng -> "Open in maps")
  [ ] Reporter card: student name + email (contact only if needed)
  [ ] Status section:
        - Dropdown with ONLY the allowed next statuses returned by the backend (no hard-coded rules)
        - Note field (required for rejected / closed, optional otherwise)
        - "Update status" button (disabled + spinner while saving), confirm dialog for rejected/closed
  [ ] Priority selector: Low | Normal | High | Urgent (changes SLA due time)
  [ ] Assigned worker card:
        - Unassigned: Button "Assign worker" -> go(page, "/admin/assign", issue_id=id)
        - Assigned: worker name, skill, phone with Call / SMS / WhatsApp buttons (url_launcher tel:/sms:/wa.me),
          assigned time, Buttons "Reassign" (-> /admin/assign, reason required) and "Unassign"
        - tap worker name -> go(page, "/admin/worker", id=worker_id)
  [ ] Internal notes (admin-only, NOT shown to the student): list + TextField + Add button
  [ ] Timeline (vertical): Reported -> Assigned -> In progress -> Resolved -> Closed, plus reassign /
      reopen / priority change events, each with time + actor + note
  [ ] Loading + error/retry states; refresh after any action

Data TODO
  [ ] admin_service.get_issue(id)                        (includes allowed_transitions, worker, notes, timeline)
  [ ] admin_service.update_status(id, status, note)
  [ ] admin_service.set_priority(id, priority)
  [ ] admin_service.unassign(id, reason)
  [ ] admin_service.add_note(id, text)
"""
import flet as ft

from core.router import back


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.TextButton("< Back", on_click=lambda e: back(page)),
                ft.Text(f"Complaint #{id}", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("TODO: see docstring"),
            ]
        ),
    )
