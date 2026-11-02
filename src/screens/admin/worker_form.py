"""WORKER FORM (add / edit)  |  side: admin (PHO / staff)  |  route: /admin/worker_form  |  navbar: hidden
Param: id (optional). No id -> "Add worker"; with id -> "Edit worker" (prefilled).

UI TODO
  [ ] AppBar row: Back icon (back(page)) + "Add worker" / "Edit worker"
  [ ] TextField "Full name" (required)
  [ ] TextField "Phone" (required, phone keyboard, 10 digits) - used for Call / SMS / WhatsApp
  [ ] Skills: multi-select chips from issue categories (required, at least 1); mark one as primary
  [ ] Zones / buildings covered: multi-select (empty = whole campus)
  [ ] Shift: start time + end time pickers, work days (Mon..Sun toggle chips)
  [ ] "Max active jobs" number stepper (default 4, 1..10) - capacity used by the scheduler
  [ ] Save button (disabled + spinner while saving); inline field errors
  [ ] Edit mode only: "Deactivate worker" (confirm dialog; blocked while they have active jobs)
  [ ] Discard-changes confirm when going back with unsaved edits

Data TODO
  [ ] issue_service.list_categories(), issue_service.list_buildings()
  [ ] admin_service.get_worker(id)            (edit mode prefill)
  [ ] admin_service.create_worker(payload) / admin_service.update_worker(id, payload)
"""
import flet as ft

from core.router import back


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    title = "Edit worker" if id is not None else "Add worker"
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.TextButton("< Back", on_click=lambda e: back(page)),
                ft.Text(title, size=22, weight=ft.FontWeight.BOLD),
                ft.Text("TODO: see docstring"),
            ]
        ),
    )
