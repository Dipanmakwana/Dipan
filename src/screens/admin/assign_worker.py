"""ASSIGN WORKER  |  side: admin (PHO)  |  route: /admin/assign  |  navbar: hidden
Params: issue_id (required), reassign (bool, optional).

The ranking comes from the backend scheduler (backend/services/scheduler.py); this screen only displays it.

  [x] Complaint summary: category, building, priority, SLA due
  [x] Recommended list (sorted by score): score, load, ETA, reason chips, flags, "Best match"
  [x] Expandable score breakdown per worker
  [x] "Show all workers" -> manual override list (inactive / on leave greyed out)
  [x] Empty state with fallback candidates + link to /admin/workers
  [x] Confirm dialog: note, reason (required when reassigning), "Notify worker now" -> SMS / WhatsApp / Call
  [x] On success: snackbar + back to the complaint (detail reloads)

Data: admin_service.recommended_workers, list_workers, assign
"""
import flet as ft

from components.status_chip import build_priority_badge
from components.worker_card import build_worker_card
from core.router import back, go
from services import admin_service

from . import _ui as ui

BREAKDOWN_LABELS = [
    ("skill", "Skill match"),
    ("capacity", "Free capacity"),
    ("proximity", "Proximity"),
    ("shift", "Shift fit"),
    ("perf", "Past performance"),
    ("fairness", "Fairness penalty"),
]


def view(page: ft.Page, issue_id: int | None = None, reassign: bool = False, **params) -> ft.Control:
    state = {"data": None, "show_all": False, "all_workers": None}
    list_column = ft.Column(spacing=10, tight=True)
    summary_holder = ft.Container()
    toggle = ft.Switch(label="Show all workers (manual pick)", value=False, active_color=ui.PURPLE)

    async def load():
        state["data"] = await admin_service.recommended_workers(issue_id, limit=20)
        if state["show_all"]:
            state["all_workers"] = await admin_service.list_workers(include_inactive=True)
        return state["data"]

    def breakdown_view(breakdown: dict) -> ft.Control:
        rows = []
        for key, label in BREAKDOWN_LABELS:
            value = float(breakdown.get(key, 0))
            penalty = key == "fairness"
            rows.append(ft.Row(
                [ft.Text(label, size=11, color=ui.MUTED, width=110),
                 ft.ProgressBar(value=value, color=ui.ERROR if penalty else ui.PURPLE, bgcolor="#EEEAF6",
                                bar_height=6, border_radius=4, expand=True),
                 ft.Text(f"{'-' if penalty and value else ''}{round(value * 100)}%", size=11, color=ui.TEXT, width=40,
                         text_align=ft.TextAlign.RIGHT)],
                spacing=8,
            ))
        return ft.Container(padding=ft.Padding.only(left=14, right=14, bottom=8),
                            content=ft.Column(rows, spacing=6, tight=True))

    def render(data: dict) -> ft.Control:
        issue = data.get("issue") or {}
        due, due_color = ui.due_text(issue)
        summary_holder.content = ui.card(ft.Column(
            [
                ft.Row([ft.Text(f"#{issue.get('id')} · {str(issue.get('category') or '').title()}", size=15,
                                color=ui.TEXT, weight=ft.FontWeight.BOLD, expand=True),
                        build_priority_badge(issue.get("priority"))]),
                ft.Text(issue.get("description") or "", size=13, color=ui.TEXT, max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Row([ft.Icon(ft.Icons.PLACE_OUTLINED, size=14, color=ui.MUTED),
                        ft.Text((issue.get("building_name") or "Location not given")
                                + (f" · {issue['room']}" if issue.get("room") else ""), size=12, color=ui.MUTED,
                                expand=True),
                        *([ft.Text(due, size=12, color=due_color, weight=ft.FontWeight.W_600)] if due else [])]),
            ],
            spacing=6, tight=True,
        ), bgcolor=ui.LAVENDER)

        list_column.controls.clear()
        if state["show_all"]:
            render_all_workers()
        else:
            render_recommendations(data)
        return list_column

    def render_recommendations(data):
        recs = data.get("recommendations") or []
        if not recs:
            list_column.controls.append(ui.empty_view(
                ft.Icons.PERSON_SEARCH_OUTLINED, "No worker has this skill",
                "Nobody available has the skill for this category. Add a worker or pick one manually.",
                action=ft.Row([ui.secondary_button("Workers", icon=ft.Icons.ENGINEERING_OUTLINED,
                                                   on_click=lambda e: go(page, "/admin/workers")),
                               ui.secondary_button("Pick manually", icon=ft.Icons.LIST,
                                                   on_click=lambda e: set_show_all(True))],
                              spacing=8, alignment=ft.MainAxisAlignment.CENTER),
            ))
            return
        if not data.get("has_eligible"):
            list_column.controls.append(ui.card(ft.Row(
                [ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ui.WARNING),
                 ft.Text("No one is fully available right now. These are the closest options; "
                         "check the flags before assigning.", size=12, color=ui.TEXT, expand=True)],
                spacing=10,
            ), bgcolor="#FFF6E8"))
        for index, rec in enumerate(recs):
            rec = {**rec, "best": index == 0 and rec.get("eligible")}
            worker = rec["worker"]
            list_column.controls.append(ft.Column(
                [
                    build_worker_card(worker, on_tap=lambda wid, r=rec: ask_assign(r["worker"], r),
                                      compact=True, recommendation=rec),
                    ft.ExpansionTile(
                        title=ft.Text("Why this score?", size=12, color=ui.PURPLE),
                        tile_padding=ft.Padding.symmetric(horizontal=14),
                        controls=[breakdown_view(rec.get("breakdown") or {})],
                    ),
                ],
                spacing=0,
                tight=True,
            ))

    def render_all_workers():
        workers = state["all_workers"] or []
        if not workers:
            list_column.controls.append(ui.empty_view(
                ft.Icons.ENGINEERING_OUTLINED, "No workers yet", "Add workers to assign complaints.",
                action=ui.primary_button("Add worker", icon=ft.Icons.PERSON_ADD_ALT,
                                         on_click=lambda e: go(page, "/admin/worker_form"))))
            return
        current = (state["data"] or {}).get("issue", {}).get("assigned_worker_id")
        for worker in workers:
            blocked = worker.get("availability") == "inactive"
            card = build_worker_card(
                worker, compact=True,
                on_tap=None if blocked else (lambda wid, w=worker: ask_assign(w, None)),
                recommendation={"is_current": worker["id"] == current, "eligible": True,
                                "flags": [], "reasons": []} if worker["id"] == current else None,
            )
            list_column.controls.append(ft.Container(content=card, opacity=0.5 if blocked else 1))

    def set_show_all(value: bool):
        state["show_all"] = value
        toggle.value = value
        page.run_task(reload)

    toggle.on_change = lambda e: set_show_all(bool(e.control.value))

    def ask_assign(worker: dict, rec: dict | None):
        data = state["data"] or {}
        issue = data.get("issue") or {}
        current = issue.get("assigned_worker_id")
        if current == worker.get("id"):
            ui.snack(page, f"{worker.get('name')} is already assigned.", error=True)
            return
        is_reassign = bool(current) or bool(reassign)
        note = ui.text_field("Note to worker (optional)", hint="e.g. bring a ladder", multiline=True)
        reason = ui.text_field("Reason for reassigning", multiline=True, visible=is_reassign)
        notify = ft.Checkbox(label="Notify worker now (SMS / WhatsApp)", value=True)
        channel = ft.SegmentedButton(
            segments=[ft.Segment(value="whatsapp", label=ft.Text("WhatsApp")),
                      ft.Segment(value="sms", label=ft.Text("SMS")),
                      ft.Segment(value="call", label=ft.Text("Call"))],
            selected=["whatsapp"], allow_empty_selection=False, show_selected_icon=False,
        )
        error = ft.Text("", size=12, color=ui.ERROR)
        warnings = []
        flags = (rec or {}).get("flags") or []
        if worker.get("availability") in ("on_leave", "busy", "off_today") or flags:
            text = ", ".join(f.replace("_", " ") for f in flags) or worker.get("availability", "").replace("_", " ")
            warnings.append(ft.Text(f"Heads up: {text}.", size=12, color=ui.WARNING))

        async def confirmed(dialog, button):
            if is_reassign and not (reason.value or "").strip():
                error.value = "A reason is required when reassigning."
                return
            try:
                result = await admin_service.assign(issue_id, worker["id"], (note.value or "").strip() or None,
                                                    (reason.value or "").strip() or None)
            except Exception as exc:
                error.value = ui.error_text(exc)
                return
            page.pop_dialog()
            ui.snack(page, result.get("message") or f"Assigned to {worker.get('name')}.")
            if notify.value and worker.get("phone"):
                message = ui.job_message(issue) + (f" Note: {note.value.strip()}" if (note.value or "").strip() else "")
                from urllib.parse import quote
                phone = ui._intl(worker["phone"])
                url = {
                    "whatsapp": f"https://wa.me/{phone}?text={quote(message)}",
                    "sms": f"sms:+{phone}?body={quote(message)}",
                    "call": f"tel:+{phone}",
                }[(channel.selected or ["whatsapp"])[0]]
                await ui.open_url(page, url)
            back(page)

        ui.confirm_dialog(
            page,
            f"{'Reassign' if is_reassign else 'Assign'} to {worker.get('name')}?",
            ft.Column([*warnings, note, reason, notify, channel, error], spacing=10, tight=True, width=380),
            "Assign",
            confirmed,
        )

    body, reload = ui.async_body(page, load, render, "Finding the best workers...")
    page.run_task(reload)

    return ui.screen([
        ui.back_header(page, "Reassign complaint" if reassign else "Assign complaint",
                       f"Complaint #{issue_id} · ranked by availability, skill and location",
                       actions=[ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", icon_color=ui.PURPLE,
                                              on_click=lambda e: page.run_task(reload))]),
        summary_holder,
        toggle,
        body,
    ])