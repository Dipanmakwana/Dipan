"""ANALYTICS  |  side: admin (PHO / staff)  |  route: /admin/analytics  |  navbar: hidden (opened from dashboard)

UI TODO
  [ ] AppBar row: Back icon (back(page)) + "Analytics"
  [ ] Date range selector: 7 days | 30 days | This semester | Custom
  [ ] Stat tiles: Total complaints, Avg time to assign, Avg time to resolve, SLA breach %, Reopen %
  [ ] Complaints by category (bar chart)                          - charts are later work; a table is fine first
  [ ] Complaints per week (line / bar trend)
  [ ] Hotspots: buildings with the most / repeat complaints (list, tap -> /admin/complaints?building=...)
  [ ] Worker performance table: jobs done, avg resolution, on-time %, reopen % (tap -> /admin/worker)
  [ ] (optional) Export CSV of the selected range
  [ ] Loading + error/retry states

Data TODO
  [ ] admin_service.get_analytics(date_from, date_to)
"""
import flet as ft

from core.router import back


def view(page: ft.Page, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.TextButton("< Back", on_click=lambda e: back(page)),
                ft.Text("Analytics", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("TODO: see docstring"),
            ]
        ),
    )
