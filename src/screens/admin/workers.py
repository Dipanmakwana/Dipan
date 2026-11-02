"""WORKERS / WORKLOAD  |  side: admin (PHO / staff)  |  route: /admin/workers  |  navbar tab 3 (staff)
Workers have NO app accounts. The admin manages them here and informs them by phone / SMS / WhatsApp.

UI TODO
  [ ] Header: "Workers" + team summary text ("12 workers - 7 available - 3 at full load - 2 on leave")
  [ ] Search field (name / phone)
  [ ] Filter chips: Skill (category) | Zone / building | Availability (Available, Busy, On leave, Inactive)
  [ ] Sort menu: Load (high -> low) | Load (low -> high) | Name | Overdue jobs
  [ ] Worker cards (components/worker_card.py), each showing:
        - name, skills, availability dot + label, shift hours
        - load bar: active / max_active (green < 60%, amber < 100%, red = full)
        - active job counts by priority (Urgent 1 - High 2 - Normal 1) + overdue count
      tap -> go(page, "/admin/worker", id=...)
  [ ] (optional) Toggle "Board view": columns per worker with their active complaint chips
  [ ] FAB "Add worker" -> go(page, "/admin/worker_form")
  [ ] Empty state (no workers yet -> "Add your first worker"), loading state, error state with Retry
  [ ] Pull-to-refresh

Data TODO
  [ ] admin_service.get_workload(skill, zone, availability, q, sort)  -> workers with load + job counts
"""
import flet as ft


def view(page: ft.Page, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column([ft.Text("Workers", size=22, weight=ft.FontWeight.BOLD), ft.Text("TODO: see docstring")]),
    )
