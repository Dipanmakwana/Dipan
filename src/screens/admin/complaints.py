"""COMPLAINTS  |  side: admin (PHO / staff)  |  route: /admin/complaints  |  navbar tab 2 (staff)
Optional params (from dashboard KPI cards): status, overdue, unassigned, e.g. go(page, "/admin/complaints", status="open")

UI TODO
  [ ] Search field (description / room / building / issue id)
  [ ] Filter chips (horizontal scroll): Status | Category | Building | Priority | Assigned / Unassigned | Overdue
  [ ] Sort menu: Newest | Oldest | Priority (urgent first) | SLA due soonest
  [ ] List of IssueCard (components/issue_card.py) showing: id, category, building, StatusChip,
      priority badge, assigned worker name (or "Unassigned"), age / "Overdue" badge
      tap -> go(page, "/admin/complaint", id=...)
  [ ] Pagination: "Load more" or infinite scroll (limit/offset)
  [ ] Result count text ("42 complaints")
  [ ] Empty state per filter ("No overdue complaints"), loading state, error state with Retry
  [ ] (optional) Long-press multi-select -> bulk actions: change status / set priority

Data TODO
  [ ] admin_service.list_issues(status, category, building_id, priority, assigned, overdue, q, sort, limit, offset)
  [ ] issue_service.list_categories(), issue_service.list_buildings() for the filter options
  [ ] (optional) admin_service.bulk_update_status(ids, status, note)
"""
import flet as ft


def view(page: ft.Page, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column([ft.Text("Complaints", size=22, weight=ft.FontWeight.BOLD), ft.Text("TODO: see docstring")]),
    )
