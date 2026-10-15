"""ISSUE DETAIL  |  side: shared (student view now, staff view later)  |  route: /issue  |  navbar: hidden
Param: id (issue id), e.g. go(page, "/issue", id=42). Shows a back button instead of the navbar.

UI TODO
  [ ] AppBar row: Back icon (back(page)) + "Issue #<id>"
  [ ] Header: category, StatusChip, priority badge, created date, SLA due/overdue text
  [ ] Photo strip (horizontal scroll) with tap-to-zoom
  [ ] Description text
  [ ] Location card: building name, room/spot, (later) small map with pin
  [ ] "Assigned to" card: staff name + call/email buttons (shown once assigned)
  [ ] Timeline (vertical list): Reported -> Assigned -> Acknowledged -> In progress -> Resolved -> Closed,
      each with timestamp and actor; highlight the current step; show reopen events
  [ ] Comments: list (author, time, text) + TextField "Add a comment" + Send button
  [ ] Student actions (shown by status):
        - Resolved: Button "Confirm & close" with rating (1-5 stars) + optional feedback text
        - Resolved: Button "Reopen" (reason required)
  [ ] Loading + error/retry states

Staff TODO (later, same file, branch on session.role())
  [ ] Buttons: Acknowledge / Start work / Resolve (+ resolution photo and note) / Reassign (+ reason)
  [ ] Which buttons to show must come from the backend's allowed-transitions list, not hard-coded rules

Data TODO
  [ ] issue_service.get_issue(id), add_comment(id, text), submit_feedback(id, rating, text), reopen(id, reason)
"""
import flet as ft

from core.router import back


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.TextButton("< Back", on_click=lambda e: back(page)),
                ft.Text(f"Issue #{id}", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("TODO: see docstring"),
            ]
        ),
    )
