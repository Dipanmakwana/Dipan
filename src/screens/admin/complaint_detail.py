"""COMPLAINT DETAIL (admin)  |  side: admin (PHO)  |  route: /admin/complaint  |  navbar: hidden
Param: id (issue id), e.g. go(page, "/admin/complaint", id=42).

  [x] Header: category, status, priority, created date, SLA due / overdue
  [x] Photo strip with tap-to-zoom
  [x] Description + location card (building, room, location text, "Open in maps")
  [x] Reporter card (name, roll number, email)
  [x] Status change limited to the backend's allowed transitions (note required for rejected / closed)
  [x] Priority selector (recomputes SLA due time)
  [x] Assigned worker card: Assign / Reassign (-> /admin/assign) / Unassign (reason), Call / SMS / WhatsApp
  [x] Internal admin notes (never shown to students)
  [x] Timeline of events with actor + note
  [x] Loading / error + Retry; reloads after every action

Data: admin_service.get_issue, update_status, set_priority, unassign, add_note
"""
import flet as ft

from components.issue_card import CATEGORY_ICONS
from components.status_chip import build_overdue_badge, build_priority_badge, build_status_chip, status_label
from core.router import go
from services import admin_service

from . import _ui as ui

EVENT_TEXT = {
    "created": ("Reported", ft.Icons.FLAG_OUTLINED),
    "status_changed": ("Status changed", ft.Icons.SYNC_ALT),
    "assigned": ("Worker assigned", ft.Icons.ENGINEERING_OUTLINED),
    "reassigned": ("Reassigned", ft.Icons.SWAP_HORIZ),
    "unassigned": ("Worker removed", ft.Icons.PERSON_REMOVE_OUTLINED),
    "priority_changed": ("Priority changed", ft.Icons.LOW_PRIORITY),
    "reopened": ("Reopened", ft.Icons.REPLAY),
    "comment": ("Student comment", ft.Icons.CHAT_BUBBLE_OUTLINE),
    "feedback": ("Student rating", ft.Icons.STAR_OUTLINE_ROUNDED),
}


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    issue_id = id
    state: dict = {}

    async def load():
        data = await admin_service.get_issue(issue_id)
        state.update(data)
        return data

    def render(data: dict) -> ft.Control:
        issue = data["issue"]
        return ft.Column(
            [
                header_card(issue),
                *([photos_card(issue)] if issue.get("photo_urls") else []),
                details_card(issue, data.get("reporter") or {}),
                status_card(issue, data.get("allowed_transitions") or []),
                worker_card(issue),
                notes_card(data.get("notes") or []),
                timeline_card(data.get("timeline") or []),
            ],
            spacing=14,
            tight=True,
        )

    body, reload = ui.async_body(page, load, render, "Loading complaint...")

    async def refresh():
        await reload(silent=True)

    # ---------------- sections ----------------

    def header_card(issue):
        category = str(issue.get("category") or "other").lower()
        badges = [build_status_chip(issue.get("status"), size=12), build_priority_badge(issue.get("priority"), size=12)]
        if issue.get("overdue"):
            badges.append(build_overdue_badge(size=12))
        due, due_color = ui.due_text(issue)
        lines = [ft.Text(f"Reported {ui.fmt_dt(issue.get('created_at'), with_year=True)}", size=12, color=ui.MUTED)]
        if due:
            lines.append(ft.Text(due, size=12, color=due_color, weight=ft.FontWeight.W_600))
        if issue.get("resolved_at"):
            lines.append(ft.Text(f"Resolved {ui.fmt_dt(issue['resolved_at'])}", size=12, color=ui.SUCCESS))
        return ui.card(ft.Row(
            [
                ft.Container(width=52, height=52, border_radius=16, bgcolor=ui.LAVENDER, alignment=ft.Alignment(0, 0),
                             content=ft.Icon(CATEGORY_ICONS.get(category, ft.Icons.REPORT_PROBLEM_OUTLINED),
                                             size=26, color=ui.PURPLE)),
                ft.Column(
                    [ft.Text(category.title(), size=20, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                     ft.Row(badges, spacing=6, wrap=True, run_spacing=6), *lines],
                    spacing=6, tight=True, expand=True,
                ),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ))

    def photos_card(issue):
        def zoom(url):
            page.show_dialog(ft.AlertDialog(
                content=ft.Image(src=url, fit=ft.BoxFit.CONTAIN, width=600, height=600),
                actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
            ))

        return ui.section("Photos", [ft.Row(
            [
                ft.Container(
                    width=120, height=120, border_radius=14, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    on_click=lambda e, u=url: zoom(u), ink=True,
                    content=ft.Image(src=url, fit=ft.BoxFit.COVER, width=120, height=120),
                )
                for url in issue.get("photo_urls") or []
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )])

    def details_card(issue, reporter):
        place = issue.get("building_name") or issue.get("location_text") or "Not given"
        rows = [
            ft.Text(issue.get("description") or "No description", size=14, color=ui.TEXT, selectable=True),
            ft.Divider(height=1, color=ui.BORDER),
            ui.info_row(ft.Icons.APARTMENT_OUTLINED, "Building", place),
        ]
        if issue.get("room"):
            rows.append(ui.info_row(ft.Icons.MEETING_ROOM_OUTLINED, "Room / spot", issue["room"]))
        if issue.get("location_text") and issue.get("location_text") != place:
            rows.append(ui.info_row(ft.Icons.NOTES, "Location note", issue["location_text"]))
        if issue.get("latitude") is not None and issue.get("longitude") is not None:
            url = f"https://www.google.com/maps/search/?api=1&query={issue['latitude']},{issue['longitude']}"
            rows.append(ui.info_row(
                ft.Icons.MY_LOCATION, "GPS", f"{issue['latitude']:.5f}, {issue['longitude']:.5f}",
                trailing=ft.TextButton("Open in maps", on_click=lambda e: page.run_task(ui.open_url, page, url)),
            ))
        rows.append(ft.Divider(height=1, color=ui.BORDER))
        who = reporter.get("name") or "Student"
        if reporter.get("roll_number"):
            who += f" · {reporter['roll_number']}"
        email = reporter.get("email")
        rows.append(ui.info_row(
            ft.Icons.PERSON_OUTLINE, "Reported by", who + (f"\n{email}" if email else ""),
            trailing=ft.IconButton(ft.Icons.MAIL_OUTLINE, icon_color=ui.PURPLE, tooltip="Email reporter",
                                   on_click=lambda e: page.run_task(
                                       ui.open_url, page, f"mailto:{email}?subject=Complaint%20%23{issue['id']}"))
            if email else None,
        ))
        return ui.section("Details", rows)

    def status_card(issue, allowed):
        controls = []
        if allowed:
            status_dd = ui.dropdown("Change status to", [(s, status_label(s)) for s in allowed], value=allowed[0])
            note = ui.text_field("Note", hint="Shown in the timeline. Required for closed / rejected.",
                                 multiline=True)
            update_btn = ui.primary_button("Update status", icon=ft.Icons.CHECK)

            async def do_update(new_status, note_text):
                await admin_service.update_status(issue_id, new_status, note_text)
                ui.snack(page, f"Status changed to {status_label(new_status)}.")
                await refresh()

            async def on_update(e):
                new_status = status_dd.value
                note_text = (note.value or "").strip() or None
                if new_status in ("closed", "rejected"):
                    if not note_text:
                        note.error = "Add a note for closed / rejected."
                        page.update()
                        return

                    async def confirmed(dialog, button):
                        try:
                            await do_update(new_status, note_text)
                            page.pop_dialog()
                        except Exception as exc:
                            page.pop_dialog()
                            ui.snack(page, ui.error_text(exc), error=True)

                    ui.confirm_dialog(page, f"Mark as {status_label(new_status).lower()}?",
                                      f"Complaint #{issue_id} will be {status_label(new_status).lower()}. "
                                      "The student will see this status.",
                                      status_label(new_status), confirmed, danger=new_status == "rejected")
                    return
                ui.set_busy(update_btn, True, "Updating...")
                page.update()
                try:
                    await do_update(new_status, note_text)
                except Exception as exc:
                    ui.set_busy(update_btn, False)
                    ui.snack(page, ui.error_text(exc), error=True)
                    page.update()

            def clear_error(e):
                note.error = None
                page.update()

            note.on_change = clear_error
            update_btn.on_click = on_update
            controls += [status_dd, note, ft.Row([update_btn], alignment=ft.MainAxisAlignment.END)]
        else:
            hint = "This complaint is closed." if issue.get("status") == "closed" else \
                "Assign a worker to move this complaint forward." if not issue.get("worker") else \
                "No status changes available."
            controls.append(ft.Text(hint, size=13, color=ui.MUTED))

        priority = ft.SegmentedButton(
            segments=[ft.Segment(value=p, label=ft.Text(p.title(), size=12)) for p in ("low", "normal", "high", "urgent")],
            selected=[issue.get("priority") or "normal"],
            allow_empty_selection=False,
            allow_multiple_selection=False,
            show_selected_icon=False,
        )

        async def on_priority(e):
            value = (e.control.selected or ["normal"])[0]
            try:
                await admin_service.set_priority(issue_id, value)
                ui.snack(page, f"Priority set to {value}. SLA due time updated.")
                await refresh()
            except Exception as exc:
                ui.snack(page, ui.error_text(exc), error=True)
                await refresh()

        priority.on_change = on_priority
        controls += [ft.Divider(height=1, color=ui.BORDER),
                     ft.Text("Priority", size=13, color=ui.MUTED),
                     ft.Row([priority], scroll=ft.ScrollMode.AUTO)]
        return ui.section("Status & priority", controls)

    def worker_card(issue):
        worker = issue.get("worker")
        active = issue.get("status") in ("open", "assigned", "in_progress")
        if not worker:
            controls = [ft.Row([ft.Icon(ft.Icons.PERSON_SEARCH_OUTLINED, color=ui.MUTED),
                                ft.Text("No worker assigned yet.", size=13, color=ui.MUTED, expand=True)])]
            suggestion = issue.get("suggestion") or {}
            suggested = suggestion.get("worker") or {}
            if active and suggested.get("id"):
                async def assign_suggested(e):
                    btn = e.control
                    ui.set_busy(btn, True, "Assigning...")
                    page.update()
                    try:
                        await admin_service.assign(issue_id, suggested["id"], reason="Suggested by scheduler")
                    except Exception as exc:  # noqa: BLE001
                        ui.set_busy(btn, False)
                        ui.snack(page, ui.error_text(exc), error=True)
                        page.update()
                        return
                    ui.snack(page, f"Assigned to {suggested.get('name')}.")
                    await refresh()

                controls.append(ft.Container(
                    padding=12, border_radius=14, bgcolor=ui.LAVENDER,
                    content=ft.Column(
                        [
                            ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=ui.PURPLE),
                                    ft.Text(f"Suggested: {suggested.get('name')}", size=14, color=ui.TEXT,
                                            weight=ft.FontWeight.BOLD, expand=True),
                                    ui.pill(f"Score {suggestion.get('score', 0)}")], spacing=6),
                            *[ft.Text(f"• {r}", size=12, color=ui.MUTED) for r in suggestion.get("reasons") or []],
                            *([ft.Text("Fallback pick: nobody fully matches (load, shift or area).", size=12,
                                       color=ui.WARNING)] if not suggestion.get("eligible", True) else []),
                        ],
                        spacing=4, tight=True,
                    ),
                ))
                controls.append(ft.Row(
                    [ui.primary_button("Assign suggested", icon=ft.Icons.CHECK, expand=True, on_click=assign_suggested),
                     ui.secondary_button("See all options", expand=True,
                                         on_click=lambda e: go(page, "/admin/assign", issue_id=issue_id))],
                    spacing=10,
                ))
            elif active:
                controls.append(ui.primary_button(
                    "Assign worker", icon=ft.Icons.AUTO_AWESOME, expand=True,
                    on_click=lambda e: go(page, "/admin/assign", issue_id=issue_id)))
            return ui.section("Assigned worker", controls)

        skills = ", ".join(s.title() for s in worker.get("skills") or [])
        controls = [
            ft.Container(
                ink=True, border_radius=12,
                on_click=lambda e: go(page, "/admin/worker", id=worker["id"]),
                content=ft.Row(
                    [
                        ft.CircleAvatar(content=ft.Text((worker.get("name") or "?")[:1].upper(),
                                                        color=ui.PURPLE_DARK, weight=ft.FontWeight.BOLD),
                                        bgcolor=ui.LAVENDER, radius=22),
                        ft.Column([ft.Text(worker.get("name") or "Worker", size=15, color=ui.TEXT,
                                           weight=ft.FontWeight.BOLD),
                                   ft.Text(skills or "—", size=12, color=ui.MUTED),
                                   ft.Text(f"{worker.get('phone') or ''}"
                                           + (f" · assigned {ui.fmt_dt(worker.get('assigned_at'))}"
                                              if worker.get("assigned_at") else ""),
                                           size=12, color=ui.MUTED)],
                                  spacing=1, tight=True, expand=True),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ui.MUTED),
                    ],
                    spacing=12,
                ),
            ),
            ft.Row([ft.Text("Inform worker", size=12, color=ui.MUTED, expand=True),
                    ui.contact_buttons(page, worker.get("phone"), ui.job_message(issue))]),
        ]
        if active:
            def ask_unassign(e):
                reason = ui.text_field("Reason", hint="Why is the worker being removed?", multiline=True)
                error = ft.Text("", size=12, color=ui.ERROR)

                async def confirmed(dialog, button):
                    if not (reason.value or "").strip():
                        error.value = "A reason is required."
                        return
                    try:
                        await admin_service.unassign(issue_id, reason.value.strip())
                    except Exception as exc:
                        error.value = ui.error_text(exc)
                        return
                    page.pop_dialog()
                    ui.snack(page, "Worker removed. Complaint is open again.")
                    await refresh()

                ui.confirm_dialog(page, f"Unassign {worker.get('name')}?",
                                  ft.Column([reason, error], tight=True, spacing=8, width=360),
                                  "Unassign", confirmed, danger=True)

            controls.append(ft.Row(
                [ui.secondary_button("Reassign", icon=ft.Icons.SWAP_HORIZ, expand=True,
                                     on_click=lambda e: go(page, "/admin/assign", issue_id=issue_id, reassign=True)),
                 ui.secondary_button("Unassign", icon=ft.Icons.PERSON_REMOVE_OUTLINED, expand=True,
                                     color=ui.ERROR, on_click=ask_unassign)],
                spacing=10,
            ))
        return ui.section("Assigned worker", controls)

    def notes_card(notes):
        field = ui.text_field("Add an internal note", hint="Only PHO admins can see notes", multiline=True)
        add_btn = ui.primary_button("Add note", icon=ft.Icons.NOTE_ADD_OUTLINED)

        async def on_add(e):
            text = (field.value or "").strip()
            if not text:
                field.error = "Write something first."
                page.update()
                return
            ui.set_busy(add_btn, True, "Saving...")
            page.update()
            try:
                await admin_service.add_note(issue_id, text)
                ui.snack(page, "Note added.")
                await refresh()
            except Exception as exc:
                ui.set_busy(add_btn, False)
                ui.snack(page, ui.error_text(exc), error=True)
                page.update()

        add_btn.on_click = on_add
        items = [
            ft.Container(
                padding=12, border_radius=12, bgcolor=ui.PAGE_BG,
                content=ft.Column([
                    ft.Row([ft.Text(n.get("author") or "Admin", size=12, color=ui.TEXT, weight=ft.FontWeight.BOLD,
                                    expand=True),
                            ft.Text(ui.fmt_dt(n.get("created_at")), size=11, color=ui.MUTED)]),
                    ft.Text(n.get("text") or "", size=13, color=ui.TEXT, selectable=True),
                ], spacing=4, tight=True),
            )
            for n in notes
        ] or [ft.Text("No notes yet.", size=13, color=ui.MUTED)]
        return ui.section("Internal notes", items + [field, ft.Row([add_btn], alignment=ft.MainAxisAlignment.END)],
                          subtitle="Visible to PHO admins only")

    def timeline_card(events):
        rows = []
        for index, event in enumerate(events):
            title, icon = EVENT_TEXT.get(event.get("type"), (str(event.get("type")).replace("_", " ").title(),
                                                             ft.Icons.CIRCLE_OUTLINED))
            if event.get("type") == "status_changed" and event.get("to_status"):
                title = f"{status_label(event.get('from_status'))} → {status_label(event['to_status'])}"
            last = index == len(events) - 1
            rows.append(ft.Row(
                [
                    ft.Column(
                        [ft.Container(width=30, height=30, border_radius=15,
                                      bgcolor=ui.PURPLE if last else ui.LAVENDER, alignment=ft.Alignment(0, 0),
                                      content=ft.Icon(icon, size=15, color=ui.WHITE if last else ui.PURPLE)),
                         ft.Container(width=2, height=26, bgcolor=ui.BORDER, visible=not last)],
                        spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        [ft.Text(title, size=13, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                         ft.Text(f"{event.get('actor') or ''} · {ui.fmt_dt(event.get('created_at'))}", size=11,
                                 color=ui.MUTED),
                         *([ft.Text(event["note"], size=12, color=ui.TEXT)] if event.get("note") else [])],
                        spacing=2, tight=True, expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ))
        return ui.section("Timeline", rows or [ft.Text("No events yet.", size=13, color=ui.MUTED)])

    page.run_task(reload)
    return ui.screen([
        ui.back_header(page, f"Complaint #{issue_id}", "Manage status, priority and assignment",
                       actions=[ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", icon_color=ui.PURPLE,
                                              on_click=lambda e: page.run_task(reload))]),
        body,
    ])