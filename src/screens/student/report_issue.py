"""REPORT ISSUE  |  side: student  |  route: /report  |  navbar tab 2
Core feature of the app. Start from the working camera + GPS test code (copy it from the old CampusCare-SL main.py).

UI TODO (form, top to bottom)
  [ ] Dropdown   "Category"            (options from backend: plumbing, electrical, civil, housekeeping, network, ...)
  [ ] TextField  "Description"         (multiline, max ~500 chars, live counter)
  [ ] Photos     Camera preview + "Take photo" button; thumbnails (max 3) with remove (x); "Retake"
  [ ] Location   Button "Use my location" -> shows "Lat, Lng (+/- accuracy m)"
                 Warning chip if accuracy is worse than ~30 m or location is outside campus
  [ ] Dropdown   "Building"            (auto-selected from backend match after GPS; manual fallback if GPS fails/denied)
  [ ] TextField  "Room / exact spot"   (optional)
  [ ] Button     "Submit report"       (disabled until category + description + building are filled; spinner while sending)
  [ ] Success state: "Report submitted, ID #123" -> go(page, "/issue", id=123, replace=True)
  [ ] Error banner + keep the form data on failure

Behaviour TODO
  [ ] Request camera + location permissions; handle "denied" gracefully
  [ ] Compress photo before upload (keep it small for campus Wi-Fi)
  [ ] Submit in 2 steps: issue_service.create_issue(payload incl. idempotency key), then upload_photo() per photo with retry
  [ ] (later) offline draft queue: save locally and retry when online
"""
import flet as ft


def view(page: ft.Page, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column([ft.Text("Report an issue", size=22, weight=ft.FontWeight.BOLD), ft.Text("TODO: see docstring")]),
    )
