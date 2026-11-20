"""ANALYTICS  |  side: admin (PHO)  |  route: /admin/analytics  |  navbar: hidden (opened from dashboard)

  [x] Range: 7 days | 30 days | 90 days | Custom (date range picker)
  [x] Stat tiles: total, resolved, avg time to assign, avg time to resolve, SLA breach %, reopen %
  [x] Complaints by category (bar rows)
  [x] Complaints per week (column bars)
  [x] Hotspots: buildings with the most complaints (tap -> /admin/complaints filtered by building)
  [x] Worker performance: jobs done, avg resolution, on-time %, reopen % (tap -> /admin/worker)
  [x] Loading / error + Retry
  Charts are drawn with plain containers (no chart package needed).

Data: admin_service.get_analytics(days | date_from, date_to), get_meta
"""
from datetime import date, datetime, timedelta

import flet as ft

from components.issue_card import CATEGORY_ICONS
from core.router import go
from services import admin_service

from . import _ui as ui

RANGES = [("7", "7 days"), ("30", "30 days"), ("90", "90 days"), ("custom", "Custom")]


def _tile(label: str, value: str, icon, color: str = ui.PURPLE) -> ft.Control:
    return ft.Container(
        col={"xs": 6, "sm": 4, "md": 2},
        padding=14, border_radius=16, bgcolor=ui.WHITE, border=ft.Border.all(1, ui.BORDER),
        content=ft.Column([ft.Icon(icon, size=18, color=color),
                           ft.Text(value, size=22, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                           ft.Text(label, size=11, color=ui.MUTED)], spacing=4, tight=True),
    )


def _bar_row(label: str, count: int, total_max: int, icon=None, on_click=None) -> ft.Control:
    lead = [ft.Icon(icon, size=16, color=ui.PURPLE)] if icon else []
    return ft.Container(
        ink=on_click is not None, on_click=on_click, border_radius=8, padding=ft.Padding.symmetric(vertical=3),
        content=ft.Row(
            [*lead,
             ft.Text(label, size=12, color=ui.TEXT, width=150, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
             ft.ProgressBar(value=count / total_max if total_max else 0, color=ui.PURPLE, bgcolor="#EEEAF6",
                            bar_height=10, border_radius=6, expand=True),
             ft.Text(str(count), size=12, color=ui.TEXT, weight=ft.FontWeight.BOLD, width=34,
                     text_align=ft.TextAlign.RIGHT)],
            spacing=8,
        ),
    )


def _weekly_chart(weeks: list[dict]) -> ft.Control:
    peak = max([w["count"] for w in weeks] + [1])
    height = 120
    bars = []
    for week in weeks[-16:]:
        start = date.fromisoformat(week["week_start"])
        bars.append(ft.Column(
            [ft.Text(str(week["count"]) if week["count"] else "", size=10, color=ui.MUTED),
             ft.Container(width=22, height=max(3, height * week["count"] / peak), border_radius=6,
                          bgcolor=ui.PURPLE if week["count"] else ui.BORDER,
                          tooltip=f"Week of {start:%d %b}: {week['count']}"),
             ft.Text(start.strftime("%d/%m"), size=9, color=ui.MUTED)],
            spacing=4, tight=True, alignment=ft.MainAxisAlignment.END,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ))
    return ft.Container(height=height + 44, content=ft.Row(bars, spacing=10, scroll=ft.ScrollMode.AUTO,
                                                           vertical_alignment=ft.CrossAxisAlignment.END))


def view(page: ft.Page, **params) -> ft.Control:
    state = {"range": "30", "from": None, "to": None, "buildings": {}}
    range_row = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)
    range_text = ft.Text("", size=12, color=ui.MUTED)

    async def load():
        if not state["buildings"]:
            meta = await admin_service.get_meta()
            state["buildings"] = {b["name"]: b["id"] for b in meta.get("buildings", [])}
        if state["range"] == "custom" and state["from"]:
            return await admin_service.get_analytics(days=None, date_from=state["from"], date_to=state["to"])
        return await admin_service.get_analytics(days=int(state["range"]))

    def render(data: dict) -> ft.Control:
        totals = data.get("totals") or {}
        rng = data.get("range") or {}
        range_text.value = f"{rng.get('from')} → {rng.get('to')}"
        if not totals.get("complaints"):
            return ui.empty_view(ft.Icons.INSIGHTS, "No complaints in this period", "Pick a longer range.")

        def pct(value):
            return f"{value}%" if value is not None else "—"

        tiles = ft.ResponsiveRow([
            _tile("Complaints", str(totals.get("complaints", 0)), ft.Icons.INBOX_OUTLINED),
            _tile("Resolved", str(totals.get("resolved", 0)), ft.Icons.TASK_ALT, ui.SUCCESS),
            _tile("Avg time to assign", ui.fmt_hours(totals.get("avg_assign_h")), ft.Icons.PERSON_SEARCH_OUTLINED),
            _tile("Avg time to resolve", ui.fmt_hours(totals.get("avg_resolve_h")), ft.Icons.TIMER_OUTLINED),
            _tile("SLA breached", pct(totals.get("sla_breach_pct")), ft.Icons.ALARM, ui.ERROR),
            _tile("Reopened", pct(totals.get("reopen_pct")), ft.Icons.REPLAY, ui.WARNING),
        ], spacing=10, run_spacing=10)

        categories = data.get("by_category") or []
        cat_max = max([c["count"] for c in categories] + [1])
        hotspots = data.get("hotspots") or []
        hot_max = max([h["count"] for h in hotspots] + [1])

        def open_building(name):
            building_id = state["buildings"].get(name)
            if building_id:
                return lambda e: go(page, "/admin/complaints", status="", building_id=building_id)
            return None

        workers = data.get("workers") or []
        worker_rows = [
            ft.Container(
                ink=True, border_radius=10, padding=ft.Padding.symmetric(vertical=6, horizontal=4),
                on_click=lambda e, wid=w["worker_id"]: go(page, "/admin/worker", id=wid),
                content=ft.Row([
                    ft.Text(w["name"], size=13, color=ui.TEXT, weight=ft.FontWeight.W_600, expand=True,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(str(w["done"]), size=12, color=ui.TEXT, width=44, text_align=ft.TextAlign.RIGHT),
                    ft.Text(ui.fmt_hours(w.get("avg_resolution_h")), size=12, color=ui.TEXT, width=64,
                            text_align=ft.TextAlign.RIGHT),
                    ft.Text(pct(w.get("on_time_pct")), size=12, color=ui.TEXT, width=54, text_align=ft.TextAlign.RIGHT),
                    ft.Text(pct(w.get("reopen_pct")), size=12, color=ui.TEXT, width=54, text_align=ft.TextAlign.RIGHT),
                ]),
            )
            for w in workers
        ]
        worker_header = ft.Row([
            ft.Text("Worker", size=11, color=ui.MUTED, expand=True),
            ft.Text("Done", size=11, color=ui.MUTED, width=44, text_align=ft.TextAlign.RIGHT),
            ft.Text("Avg", size=11, color=ui.MUTED, width=64, text_align=ft.TextAlign.RIGHT),
            ft.Text("On time", size=11, color=ui.MUTED, width=54, text_align=ft.TextAlign.RIGHT),
            ft.Text("Reopen", size=11, color=ui.MUTED, width=54, text_align=ft.TextAlign.RIGHT),
        ])

        return ft.Column([
            tiles,
            ui.section("By category", [
                _bar_row(c["category"].title(), c["count"], cat_max, CATEGORY_ICONS.get(c["category"]))
                for c in categories
            ]),
            ui.section("Complaints per week", [_weekly_chart(data.get("weekly") or [])]),
            ui.section("Hotspots", [
                _bar_row(h["building"], h["count"], hot_max, ft.Icons.PLACE_OUTLINED, open_building(h["building"]))
                for h in hotspots
            ], subtitle="Buildings with the most complaints. Tap to see them."),
            ui.section("Worker performance",
                       [worker_header, *worker_rows] if worker_rows
                       else [ft.Text("No resolved complaints with a worker in this period.", size=13,
                                     color=ui.MUTED)]),
        ], spacing=14, tight=True)

    body, reload = ui.async_body(page, load, render, "Crunching numbers...")

    def render_ranges():
        range_row.controls = [ui.filter_chip(label, state["range"] == key, lambda e, k=key: set_range(k))
                              for key, label in RANGES]

    def set_range(key):
        if key == "custom":
            today = datetime.now(ui.IST).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

            def on_change(e):
                if picker.start_value and picker.end_value:
                    state.update(range="custom", **{"from": picker.start_value.date(), "to": picker.end_value.date()})
                    render_ranges()
                    page.run_task(reload)

            picker = ft.DateRangePicker(
                start_value=today - timedelta(days=29), end_value=today,
                first_date=today - timedelta(days=730), last_date=today, on_change=on_change,
            )
            page.show_dialog(picker)
            return
        state["range"] = key
        render_ranges()
        page.run_task(reload)

    render_ranges()
    page.run_task(reload)
    return ui.screen([
        ui.back_header(page, "Analytics", "How complaints are being handled",
                       actions=[ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", icon_color=ui.PURPLE,
                                              on_click=lambda e: page.run_task(reload))]),
        range_row,
        range_text,
        body,
    ])