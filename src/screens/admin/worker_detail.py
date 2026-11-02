"""WORKER DETAIL  |  side: admin (PHO / staff)  |  route: /admin/worker  |  navbar: hidden
Param: id (worker id), e.g. go(page, "/admin/worker", id=7)

UI TODO
  [ ] AppBar row: Back icon (back(page)) + worker name + Edit icon -> go(page, "/admin/worker_form", id=id)
  [ ] Profile card: avatar initials, name, phone, skills chips, zones, shift hours + work days
  [ ] Contact buttons: Call | SMS | WhatsApp
  [ ] Availability control: segmented Available | On leave | Inactive
        - On leave -> date range picker (from / to); scheduler skips the worker in that range
        - Warn if the worker still has active jobs ("Reassign 3 active complaints?") -> list them
  [ ] Load summary: load bar active / max_active + overdue count
  [ ] "Active assignments" list (IssueCard) tap -> go(page, "/admin/complaint", id=...)
  [ ] "History" list (resolved / closed, paginated)
  [ ] Stats row: jobs this week, avg resolution time, reopen rate, on-time %
  [ ] (optional) "Share today's job list" -> one SMS / WhatsApp message with all active jobs
  [ ] Loading + error/retry states

Data TODO
  [ ] admin_service.get_worker(id)                         (profile + active + stats)
  [ ] admin_service.worker_history(id, limit, offset)
  [ ] admin_service.set_availability(id, status, leave_from, leave_to)
"""
import flet as ft

from core.router import back


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.TextButton("< Back", on_click=lambda e: back(page)),
                ft.Text(f"Worker #{id}", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("TODO: see docstring"),
            ]
        ),
    )
