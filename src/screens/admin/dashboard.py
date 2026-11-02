"""ADMIN DASHBOARD  |  side: admin (PHO / staff)  |  route: /admin  |  navbar tab 1 (staff)

UI TODO
  [ ] Header: "Hi, <first name>" + today's date + refresh icon
  [ ] KPI cards row (tap -> /admin/complaints with that filter):
        Open | Unassigned | In progress | Overdue (SLA breached) | Resolved today
  [ ] "Needs attention" section (max 5 rows, IssueCard): urgent + unassigned, overdue, reopened
        tap -> go(page, "/admin/complaint", id=...)
  [ ] Team capacity strip: Available / Busy (at max load) / On leave counts
        tap -> go(page, "/admin/workers")
  [ ] Quick links: "All complaints" -> /admin/complaints, "Workload" -> /admin/workers,
        "Analytics" -> /admin/analytics
  [ ] Loading state (ProgressRing / skeleton) and error state with Retry
  [ ] Pull-to-refresh (or the refresh icon)

Data TODO
  [ ] admin_service.get_summary()   -> counts + needs_attention list + capacity counts (one call)
"""
import flet as ft


def view(page: ft.Page, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column([ft.Text("Dashboard", size=22, weight=ft.FontWeight.BOLD), ft.Text("TODO: see docstring")]),
    )
