"""WORKERS / WORKLOAD  |  side: admin (PHO)  |  route: /admin/workers  |  navbar tab 3 (staff)
Workers have NO app accounts. The admin manages them here and informs them by phone / SMS / WhatsApp.

  [x] Team summary ("12 workers · 7 available · 3 at full load · 2 on leave")
  [x] Search (name / phone)
  [x] Filters: skill, zone, availability ; sort: load high/low, name, overdue
  [x] Worker cards: availability, shift, load bar (green/amber/red), jobs by priority, overdue -> /admin/worker
  [x] FAB "Add worker" -> /admin/worker_form
  [x] Empty / loading / error + Retry states

Data: admin_service.get_workload(skill, zone, availability, q, sort), get_meta()
"""
import flet as ft

from components.worker_card import build_worker_card
from core.router import go
from services import admin_service

from . import _ui as ui

AVAILABILITY_FILTERS = [("", "All"), ("available", "Available"), ("busy", "Full load"), ("on_leave", "On leave"),
                        ("off_today", "Off today"), ("inactive", "Inactive")]
SORTS = [("load_desc", "Load: high → low"), ("load_asc", "Load: low → high"), ("name", "Name"),
         ("overdue", "Most overdue")]


def view(page: ft.Page, **params) -> ft.Control:
    state = {"skill": "", "zone": "", "availability": params.get("availability") or "", "q": "",
             "sort": "load_desc", "meta": {}}

    summary = ft.Text("", size=13, color=ui.MUTED)
    chips_row = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)
    search = ui.text_field("Search workers", hint="Name or phone", prefix_icon=ft.Icons.SEARCH, dense=True,
                           expand=True)
    skill_dd = ui.dropdown("Skill", [("", "All skills")], value="", expand=True)
    zone_dd = ui.dropdown("Zone", [("", "All zones")], value="", expand=True)
    sort_dd = ui.dropdown("Sort", SORTS, value="load_desc", expand=True)

    async def load():
        if not state["meta"]:
            state["meta"] = await admin_service.get_meta()
            skill_dd.options = [ft.DropdownOption(key="", text="All skills")] + [
                ft.DropdownOption(key=c, text=c.title()) for c in state["meta"].get("categories", [])]
            zone_dd.options = [ft.DropdownOption(key="", text="All zones")] + [
                ft.DropdownOption(key=z, text=z.title()) for z in state["meta"].get("zones", [])]
        return await admin_service.get_workload(
            skill=state["skill"] or None, zone=state["zone"] or None,
            availability=state["availability"] or None, q=state["q"], sort=state["sort"],
        )

    def render(data: dict) -> ft.Control:
        team = data.get("team") or {}
        parts = [f"{team.get('total', 0)} workers"]
        for key, label in (("available", "available"), ("busy", "at full load"), ("on_leave", "on leave"),
                           ("off_today", "off today")):
            if team.get(key):
                parts.append(f"{team[key]} {label}")
        summary.value = " · ".join(parts)

        workers = data.get("workers") or []
        if not workers:
            filtered = any(state[k] for k in ("skill", "zone", "availability", "q"))
            return ui.empty_view(
                ft.Icons.ENGINEERING_OUTLINED,
                "No workers match" if filtered else "No workers yet",
                "Try other filters." if filtered else "Add your maintenance team to start assigning complaints.",
                action=None if filtered else ui.primary_button(
                    "Add your first worker", icon=ft.Icons.PERSON_ADD_ALT,
                    on_click=lambda e: go(page, "/admin/worker_form")),
            )
        return ft.ResponsiveRow(
            [ft.Container(build_worker_card(w, on_tap=lambda wid: go(page, "/admin/worker", id=wid)),
                          col={"xs": 12, "md": 6, "lg": 4})
             for w in workers],
            spacing=10,
            run_spacing=10,
        )

    body, reload = ui.async_body(page, load, render, "Loading workload...")

    def render_chips():
        chips_row.controls = [ui.filter_chip(label, state["availability"] == key,
                                             lambda e, k=key: set_filter("availability", k))
                              for key, label in AVAILABILITY_FILTERS]

    def set_filter(key, value):
        state[key] = value or ""
        if key == "availability":
            render_chips()
        page.run_task(reload)

    skill_dd.on_select = lambda e: set_filter("skill", e.control.value)
    zone_dd.on_select = lambda e: set_filter("zone", e.control.value)
    sort_dd.on_select = lambda e: set_filter("sort", e.control.value or "load_desc")

    def on_search(e):
        set_filter("q", (search.value or "").strip())

    search.on_submit = on_search
    search.suffix = ft.IconButton(ft.Icons.ARROW_FORWARD, icon_size=18, icon_color=ui.PURPLE, on_click=on_search)

    render_chips()
    page.run_task(reload)

    content = ui.screen([
        ui.page_title("Workers", "Workload and availability of your team",
                      actions=[ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", icon_color=ui.PURPLE,
                                             on_click=lambda e: page.run_task(reload))]),
        summary,
        ft.Row([search]),
        chips_row,
        ft.ResponsiveRow([ft.Container(dd, col={"xs": 12, "sm": 4}) for dd in (skill_dd, zone_dd, sort_dd)],
                         spacing=10, run_spacing=10),
        body,
        ft.Container(height=70),   # room for the FAB
    ])
    fab = ft.FloatingActionButton(
        icon=ft.Icons.PERSON_ADD_ALT, content="Add worker", bgcolor=ui.PURPLE,
        foreground_color=ui.WHITE, on_click=lambda e: go(page, "/admin/worker_form"),
    )
    return ft.Stack([content, ft.Container(fab, right=18, bottom=18)], expand=True)