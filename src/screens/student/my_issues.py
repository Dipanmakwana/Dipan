"""MY ISSUES  |  side: student  |  route: /issues  |  navbar tab 3
Optional param: status (pre-selects a filter, e.g. go(page, "/issues", status="open")).

UI TODO
  [ ] Filter chips row: All | Open | In progress | Resolved | Closed   (single select)
  [ ] Scrollable list of IssueCard (components/issue_card.py): category icon + title/description snippet,
      building, StatusChip (components/status_chip.py), created date, "Overdue" badge if SLA breached
  [ ] Tap a card -> go(page, "/issue", id=...)
  [ ] Empty state per filter ("No resolved issues yet")
  [ ] Loading + error/retry states, pull-to-refresh
  [ ] (later) pagination / infinite scroll, search box
  [ ] No charts on this screen

Data TODO
  [ ] issue_service.list_my_issues(status=...) sorted newest first
"""
import flet as ft

from core.router import go


def view(page: ft.Page, status: str | None = None, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.Text("My issues", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("TODO: see docstring"),
                ft.TextButton("DEV: open sample issue #1", on_click=lambda e: go(page, "/issue", id=1)),  # REMOVE later
            ]
        ),
    )
