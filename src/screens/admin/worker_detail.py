"""WORKER DETAIL  |  side: admin (PHO)  |  route: /admin/worker  |  navbar: hidden
Param: id (worker id), e.g. go(page, "/admin/worker", id=7)

  [x] Profile: initials, name, phone, skills (primary ★), zones / buildings, shift + work days, Edit
  [x] Contact: Call | SMS | WhatsApp ; "Share job list" (all active jobs in one message)
  [x] Availability: Available | On leave (date range) | Inactive ; warns about active jobs
  [x] Load bar + overdue count ; stats: jobs this week, resolved, avg resolution, on-time %, reopen %
  [x] Active assignments -> /admin/complaint ; History (resolved / closed, "Load more")
  [x] Loading / error + Retry

Data: admin_service.get_worker, worker_history, set_availability, get_meta
"""
from datetime import datetime, timedelta
from urllib.parse import quote

import flet as ft

from components.issue_card import build_issue_card
from components.worker_card import AVAILABILITY, build_load_bar, initials
from core.router import go
from services import admin_service

from . import _ui as ui

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _stat(label: str, value: str) -> ft.Control:
    return ft.Container(
        col={"xs": 6, "sm": 4, "md": 2.4},
        padding=12, border_radius=14, bgcolor=ui.PAGE_BG,
        content=ft.Column([ft.Text(value, size=18, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                           ft.Text(label, size=11, color=ui.MUTED)], spacing=2, tight=True),
    )


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    worker_id = id
    state = {"history": [], "history_done": False, "meta": {}}
    history_column = ft.Column(spacing=10, tight=True)
    history_more = ft.TextButton("Load more history")

    async def load():
        if not state["meta"]:
            state["meta"] = await admin_service.get_meta()
        data = await admin_service.get_worker(worker_id)
        hist = await admin_service.worker_history(worker_id, limit=10, offset=0)
        state["history"] = hist.get("issues") or []
        state["history_done"] = len(state["history"]) < 10
        return data

    def render(data: dict) -> ft.Control:
        worker = data["worker"]
        return ft.Column(
            [profile_card(worker, data.get("active_issues") or []),
             availability_card(worker, data.get("active_issues") or []),
             stats_card(worker, data.get("stats") or {}),
             active_card(data.get("active_issues") or []),
             history_card()],
            spacing=14,
            tight=True,
        )

    body, reload = ui.async_body(page, load, render, "Loading worker...")

    def profile_card(worker, active):
        label, color = AVAILABILITY.get(worker.get("availability"), ("", ui.MUTED))
        buildings = {b["id"]: b["name"] for b in state["meta"].get("buildings", [])}
        skills = ", ".join(s.title() + (" ★" if s == worker.get("primary_skill") else "")
                           for s in worker.get("skills") or []) or "—"
        coverage = [z.title() for z in worker.get("zones") or []] + \
                   [buildings.get(b, b) for b in worker.get("building_ids") or []]
        days = ", ".join(DAYS[d - 1] for d in worker.get("work_days") or [] if 1 <= d <= 7) or "—"
        job_list = "\n".join(f"#{i['id']} {str(i.get('category')).title()} – {i.get('building_name') or ''}"
                             f"{' ' + i['room'] if i.get('room') else ''} ({(i.get('priority') or 'normal').title()})"
                             for i in active)
        share = None
        if active:
            share = ui.secondary_button(
                "Share job list", icon=ft.Icons.SHARE,
                on_click=lambda e: page.run_task(
                    ui.open_url, page,
                    f"https://wa.me/{ui._intl(worker.get('phone'))}?text="
                    + quote(f"Your CampusCare jobs ({len(active)}):\n{job_list}")),
            )
        return ui.card(ft.Column(
            [
                ft.Row(
                    [
                        ft.CircleAvatar(content=ft.Text(initials(worker.get("name")), size=18,
                                                        weight=ft.FontWeight.BOLD, color=ui.PURPLE_DARK),
                                        bgcolor=ui.LAVENDER, radius=30),
                        ft.Column([
                            ft.Text(worker.get("name") or "Worker", size=20, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                            ft.Row([ft.Icon(ft.Icons.CIRCLE, size=10, color=color),
                                    ft.Text(label, size=12, color=color, weight=ft.FontWeight.W_600)], spacing=4),
                            ft.Text(worker.get("phone") or "", size=13, color=ui.MUTED, selectable=True),
                        ], spacing=2, tight=True, expand=True),
                    ],
                    spacing=14,
                ),
                ft.Row([ui.contact_buttons(page, worker.get("phone")), *([share] if share else [])],
                       spacing=10, wrap=True),
                ft.Divider(height=1, color=ui.BORDER),
                ui.info_row(ft.Icons.HANDYMAN_OUTLINED, "Skills", skills),
                ui.info_row(ft.Icons.MAP_OUTLINED, "Covers", ", ".join(coverage) or "Whole campus"),
                ui.info_row(ft.Icons.SCHEDULE, "Shift",
                            f"{str(worker.get('shift_start'))[:5]}–{str(worker.get('shift_end'))[:5]} · {days}"),
                ui.info_row(ft.Icons.STACKED_BAR_CHART, "Capacity", f"Up to {worker.get('max_active')} active jobs"),
            ],
            spacing=12,
            tight=True,
        ))

    def availability_card(worker, active):
        current = worker.get("status") or "available"
        selector = ft.SegmentedButton(
            segments=[ft.Segment(value="available", label=ft.Text("Available")),
                      ft.Segment(value="on_leave", label=ft.Text("On leave")),
                      ft.Segment(value="inactive", label=ft.Text("Inactive"))],
            selected=[current], allow_empty_selection=False, show_selected_icon=False,
        )
        leave_text = ft.Text("", size=12, color=ui.MUTED)
        if current == "on_leave" and worker.get("leave_from"):
            leave_text.value = f"On leave {worker['leave_from']} → {worker.get('leave_to')}"

        async def save(status, leave_from=None, leave_to=None, force=False):
            try:
                result = await admin_service.set_availability(worker_id, status, leave_from, leave_to, force)
            except Exception as exc:
                ui.snack(page, ui.error_text(exc), error=True)
                await reload(silent=True)
                return
            jobs = result.get("active_issues") or []
            msg = {"available": "Marked available.", "on_leave": "Leave saved.", "inactive": "Worker deactivated."}[status]
            if status != "available" and jobs:
                msg += f" {len(jobs)} active complaint(s) should be reassigned."
            ui.snack(page, msg, error=status != "available" and bool(jobs))
            await reload(silent=True)

        def pick_leave():
            today = datetime.now(ui.IST).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

            def on_range(e):
                start, end = picker.start_value, picker.end_value
                if start and end:
                    page.run_task(save, "on_leave", start.date(), end.date())

            picker = ft.DateRangePicker(
                start_value=today, end_value=today + timedelta(days=1),
                first_date=today - timedelta(days=30), last_date=today + timedelta(days=365),
                on_change=on_range,
                on_dismiss=lambda e: page.run_task(reload, True),
            )
            page.show_dialog(picker)

        def on_change(e):
            value = (e.control.selected or ["available"])[0]
            if value == "on_leave":
                pick_leave()
            elif value == "inactive":
                async def confirmed(dialog, button):
                    page.pop_dialog()
                    await save("inactive", force=True)
                body_text = (f"{worker.get('name')} has {len(active)} active complaint(s). They will stay assigned "
                             "until you reassign them." if active else
                             f"{worker.get('name')} won't be recommended for new complaints.")
                dialog = ui.confirm_dialog(page, "Deactivate worker?", body_text, "Deactivate", confirmed, danger=True)
                dialog.on_dismiss = lambda e: page.run_task(reload, True)
            else:
                page.run_task(save, "available")

        selector.on_change = on_change
        controls = [ft.Row([selector], scroll=ft.ScrollMode.AUTO), leave_text]
        if current != "available" and active:
            controls.append(ft.Text(f"⚠ {len(active)} active complaint(s) still assigned. Open them below to reassign.",
                                    size=12, color=ui.WARNING))
        return ui.section("Availability", controls)

    def stats_card(worker, stats):
        avg = stats.get("avg_resolution_h")
        on_time = stats.get("on_time_pct")
        reopen = stats.get("reopen_rate")
        return ui.section("Load & performance", [
            build_load_bar(worker),
            *([ui.pill(f"{worker['overdue_count']} overdue", ui.WHITE, ui.ERROR, ft.Icons.ALARM)]
              if worker.get("overdue_count") else []),
            ft.ResponsiveRow([
                _stat("Jobs this week", str(stats.get("jobs_this_week", 0))),
                _stat("Resolved (all time)", str(stats.get("resolved_count", 0))),
                _stat("Avg resolution", ui.fmt_hours(avg)),
                _stat("On time", f"{on_time}%" if on_time is not None else "—"),
                _stat("Reopened", f"{round(reopen * 100)}%" if reopen is not None else "—"),
            ], spacing=8, run_spacing=8),
        ])

    def active_card(active):
        items = [build_issue_card(i, on_tap=lambda iid: go(page, "/admin/complaint", id=iid), show_worker=False)
                 for i in active] or [ft.Text("No active complaints.", size=13, color=ui.MUTED)]
        return ui.section(f"Active assignments ({len(active)})", items)

    def render_history():
        history_column.controls = [
            build_issue_card(i, on_tap=lambda iid: go(page, "/admin/complaint", id=iid), show_worker=False)
            for i in state["history"]
        ] or [ft.Text("No completed jobs yet.", size=13, color=ui.MUTED)]
        history_more.visible = not state["history_done"]

    async def more_history(e):
        hist = await admin_service.worker_history(worker_id, limit=10, offset=len(state["history"]))
        new = hist.get("issues") or []
        state["history"] += new
        new = hist.get("issues") or []
        state["history"] += new
        state["history_done"] = len(new) < 10
        render_history()
        page.update()

    history_more.on_click = more_history

    def history_card():
        render_history()
        return ui.section("History", [history_column, history_more], subtitle="Resolved and closed complaints")

    page.run_task(reload)
    return ui.screen([
        ui.back_header(page, "Worker", f"Worker #{worker_id}", actions=[
            ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Edit worker", icon_color=ui.PURPLE,
        new = hist.get("issues") or []
        state["history"] += new
        state["history_done"] = len(new) < 10
        render_history()
        page.update()

    history_more.on_click = more_history

    def history_card():
        render_history()
        return ui.section("History", [history_column, history_more], subtitle="Resolved and closed complaints")

    page.run_task(reload)
    return ui.screen([
        ui.back_header(page, "Worker", f"Worker #{worker_id}", actions=[
            ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Edit worker", icon_color=ui.PURPLE,
        state["history_done"] = len(new) < 10
        render_history()
        page.update()

    history_more.on_click = more_history

    def history_card():
        render_history()
        return ui.section("History", [history_column, history_more], subtitle="Resolved and closed complaints")

    page.run_task(reload)
    return ui.screen([
        ui.back_header(page, "Worker", f"Worker #{worker_id}", actions=[
            ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Edit worker", icon_color=ui.PURPLE,
                          on_click=lambda e: go(page, "/admin/worker_form", id=worker_id)),
            ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", icon_color=ui.PURPLE,
                          on_click=lambda e: page.run_task(reload)),
        ]),
        body,
    ])