"""WORKER FORM (add / edit)  |  side: admin (PHO)  |  route: /admin/worker_form  |  navbar: hidden
Param: id (optional). No id -> "Add worker"; with id -> "Edit worker" (prefilled).

  [x] Full name, phone (10 digits; used for Call / SMS / WhatsApp)
  [x] Skills: multi-select chips from categories (>= 1) + primary skill
  [x] Zones and buildings covered (none = whole campus)
  [x] Shift start / end (time pickers) + work days (Mon..Sun chips)
  [x] Max active jobs (1..10) - capacity used by the scheduler
  [x] Inline field errors; Save with spinner; server errors shown
  [x] Edit mode: "Deactivate worker" (blocked by the server while they have active jobs)
  [x] Discard-changes confirm when going back with unsaved edits

Data: admin_service.get_meta, get_worker, create_worker, update_worker, set_availability
"""
from datetime import time

import flet as ft

from core.router import back, go
from services import admin_service

from . import _ui as ui

DAYS = [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri"), (6, "Sat"), (7, "Sun")]


def _parse_time(value, default: time) -> time:
    if not value:
        return default
    parts = str(value).split(":")
    try:
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except ValueError:
        return default


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    worker_id = id
    editing = worker_id is not None
    form = {
        "skills": set(), "primary_skill": None, "zones": set(), "building_ids": set(),
        "shift_start": time(9, 0), "shift_end": time(18, 0), "work_days": {1, 2, 3, 4, 5, 6},
        "max_active": 4, "dirty": False, "meta": {}, "status": "available",
    }

    name = ui.text_field("Full name *", max_length=120)
    phone = ui.text_field("Phone *", hint="10-digit mobile number", keyboard_type=ft.KeyboardType.PHONE,
                          prefix_icon=ft.Icons.PHONE_OUTLINED, max_length=13)
    skills_row = ft.Row(spacing=6, run_spacing=6, wrap=True)
    skills_error = ft.Text("", size=12, color=ui.ERROR, visible=False)
    primary_dd = ui.dropdown("Primary skill", [], expand=True, dense=False)
    zones_row = ft.Row(spacing=6, run_spacing=6, wrap=True)
    buildings_row = ft.Row(spacing=6, run_spacing=6, wrap=True)
    days_row = ft.Row(spacing=6, run_spacing=6, wrap=True)
    shift_start_btn = ui.secondary_button("09:00", icon=ft.Icons.SCHEDULE, expand=True)
    shift_end_btn = ui.secondary_button("18:00", icon=ft.Icons.SCHEDULE, expand=True)
    shift_error = ft.Text("", size=12, color=ui.ERROR, visible=False)
    max_text = ft.Text("4", size=20, color=ui.TEXT, weight=ft.FontWeight.BOLD, width=40,
                       text_align=ft.TextAlign.CENTER)
    form_error = ft.Text("", size=13, color=ui.ERROR, visible=False)
    save_btn = ui.primary_button("Save worker" if editing else "Add worker", icon=ft.Icons.CHECK, expand=True)

    def mark_dirty(e=None):
        form["dirty"] = True

    name.on_change = lambda e: (setattr(name, "error", None), mark_dirty(), page.update())
    phone.on_change = lambda e: (setattr(phone, "error", None), mark_dirty(), page.update())

    # ---------------- chips ----------------

    def toggle(key, value):
        target = form[key]
        target.remove(value) if value in target else target.add(value)
        mark_dirty()
        render_chips()
        page.update()

    def render_chips():
        meta = form["meta"]
        skills_row.controls = [ui.filter_chip(c.title(), c in form["skills"], lambda e, c=c: toggle("skills", c))
                               for c in meta.get("categories", [])]
        skills = sorted(form["skills"])
        primary_dd.options = [ft.DropdownOption(key=s, text=s.title()) for s in skills]
        if form["primary_skill"] not in form["skills"]:
            form["primary_skill"] = skills[0] if skills else None
        primary_dd.value = form["primary_skill"]
        primary_dd.disabled = not skills
        if skills:
            skills_error.visible = False
        zones_row.controls = [ui.filter_chip(z.title(), z in form["zones"], lambda e, z=z: toggle("zones", z))
                              for z in meta.get("zones", [])]
        buildings_row.controls = [
            ui.filter_chip(b["name"], b["id"] in form["building_ids"], lambda e, b=b["id"]: toggle("building_ids", b))
            for b in meta.get("buildings", [])
        ]
        days_row.controls = [ui.filter_chip(label, d in form["work_days"], lambda e, d=d: toggle("work_days", d))
                             for d, label in DAYS]

    def on_primary(e):
        form["primary_skill"] = e.control.value
        mark_dirty()

    primary_dd.on_select = on_primary

    # ---------------- shift + capacity ----------------

    def set_time_label(button, value: time):
        button.content.controls[-1].value = value.strftime("%H:%M")

    def pick_time(key, button):
        def on_change(e):
            if picker.value:
                form[key] = picker.value
                set_time_label(button, picker.value)
                shift_error.visible = False
                mark_dirty()
                page.update()

        picker = ft.TimePicker(value=form[key], on_change=on_change,
                               help_text="Shift start" if key == "shift_start" else "Shift end")
        page.show_dialog(picker)

    shift_start_btn.on_click = lambda e: pick_time("shift_start", shift_start_btn)
    shift_end_btn.on_click = lambda e: pick_time("shift_end", shift_end_btn)

    def change_max(delta):
        form["max_active"] = max(1, min(10, form["max_active"] + delta))
        max_text.value = str(form["max_active"])
        mark_dirty()
        page.update()

    # ---------------- load / save ----------------

    async def load():
        form["meta"] = await admin_service.get_meta()
        if editing:
            worker = (await admin_service.get_worker(worker_id))["worker"]
            name.value = worker.get("name") or ""
            phone.value = worker.get("phone") or ""
            form.update(
                skills=set(worker.get("skills") or []),
                primary_skill=worker.get("primary_skill"),
                zones=set(worker.get("zones") or []),
                building_ids=set(worker.get("building_ids") or []),
                shift_start=_parse_time(worker.get("shift_start"), time(9, 0)),
                shift_end=_parse_time(worker.get("shift_end"), time(18, 0)),
                work_days=set(worker.get("work_days") or [1, 2, 3, 4, 5, 6]),
                max_active=int(worker.get("max_active") or 4),
                status=worker.get("status") or "available",
            )
        set_time_label(shift_start_btn, form["shift_start"])
        set_time_label(shift_end_btn, form["shift_end"])
        max_text.value = str(form["max_active"])
        render_chips()
        form["dirty"] = False
        return form

    def validate() -> dict | None:
        ok = True
        if not (name.value or "").strip():
            name.error = "Enter the worker's name."
            ok = False
        digits = "".join(ch for ch in (phone.value or "") if ch.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if len(digits) != 10:
            phone.error = "Enter a 10-digit mobile number."
            ok = False
        if not form["skills"]:
            skills_error.value = "Pick at least one skill."
            skills_error.visible = True
            ok = False
        if form["shift_start"] >= form["shift_end"]:
            shift_error.value = "Shift end must be after shift start."
            shift_error.visible = True
            ok = False
        if not form["work_days"]:
            shift_error.value = "Pick at least one work day."
            shift_error.visible = True
            ok = False
        if not ok:
            return None
        return {
            "name": name.value.strip(),
            "phone": digits,
            "skills": sorted(form["skills"]),
            "primary_skill": form["primary_skill"],
            "zones": sorted(form["zones"]),
            "building_ids": sorted(form["building_ids"]),
            "shift_start": form["shift_start"].strftime("%H:%M"),
            "shift_end": form["shift_end"].strftime("%H:%M"),
            "work_days": sorted(form["work_days"]),
            "max_active": form["max_active"],
        }

    async def on_save(e):
        form_error.visible = False
        payload = validate()
        if payload is None:
            form_error.value = "Fix the highlighted fields."
            form_error.visible = True
            page.update()
            return
        ui.set_busy(save_btn, True, "Saving...")
        page.update()
        try:
            if editing:
                await admin_service.update_worker(worker_id, payload)
                ui.snack(page, "Worker updated.")
                form["dirty"] = False
                back(page)
            else:
                result = await admin_service.create_worker(payload)
                ui.snack(page, f"{payload['name']} added.")
                form["dirty"] = False
                new_id = (result.get("worker") or {}).get("id")
                go(page, "/admin/worker", replace=True, id=new_id) if new_id else back(page)
        except Exception as exc:
            ui.set_busy(save_btn, False)
            form_error.value = ui.error_text(exc)
            form_error.visible = True
            page.update()

    save_btn.on_click = on_save

    def deactivate(e):
        async def confirmed(dialog, button):
            try:
                await admin_service.set_availability(worker_id, "inactive")
            except Exception as exc:
                page.pop_dialog()
                ui.snack(page, ui.error_text(exc), error=True)
                return
            page.pop_dialog()
            ui.snack(page, "Worker deactivated.")
            back(page)

        ui.confirm_dialog(page, "Deactivate this worker?",
                          "They won't be recommended for new complaints. You can reactivate them later from "
                          "their page.", "Deactivate", confirmed, danger=True)

    def go_back(e):
        if not form["dirty"]:
            back(page)
            return

        async def discard(dialog, button):
            page.pop_dialog()
            back(page)

        ui.confirm_dialog(page, "Discard changes?", "Your edits will be lost.", "Discard", discard, danger=True)

    def render(_data) -> ft.Control:
        sections = [
            ui.section("Basic details", [name, phone]),
            ui.section("Skills *", [skills_row, skills_error, primary_dd],
                       subtitle="Complaint categories this worker can handle. ★ primary skill ranks higher."),
            ui.section("Coverage", [ft.Text("Zones", size=12, color=ui.MUTED), zones_row,
                                    ft.Text("Buildings", size=12, color=ui.MUTED), buildings_row],
                       subtitle="Leave empty if the worker covers the whole campus."),
            ui.section("Shift", [
                ft.Row([ft.Column([ft.Text("Starts", size=12, color=ui.MUTED), shift_start_btn], expand=True,
                                  tight=True),
                        ft.Column([ft.Text("Ends", size=12, color=ui.MUTED), shift_end_btn], expand=True,
                                  tight=True)], spacing=12),
                ft.Text("Work days", size=12, color=ui.MUTED),
                days_row,
                shift_error,
            ]),
            ui.section("Capacity", [ft.Row(
                [ft.Text("Max active jobs at a time", size=13, color=ui.TEXT, expand=True),
                 ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_color=ui.PURPLE, on_click=lambda e: change_max(-1)),
                 max_text,
                 ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=ui.PURPLE, on_click=lambda e: change_max(1))],
            )], subtitle="Urgent jobs count as 2, high 1.5, normal 1, low 0.5 towards this limit."),
            form_error,
            ft.Row([save_btn]),
        ]
        if editing and form["status"] != "inactive":
            sections.append(ft.Row([ft.TextButton("Deactivate worker", icon=ft.Icons.BLOCK, on_click=deactivate,
                                                  style=ft.ButtonStyle(color=ui.ERROR))],
                                   alignment=ft.MainAxisAlignment.CENTER))
        return ft.Column(sections, spacing=14, tight=True)

    body, reload = ui.async_body(page, load, render, "Loading form...")
    page.run_task(reload)

    header = ft.Row(
        [ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_color=ui.TEXT, tooltip="Back", on_click=go_back),
         ft.Column([ft.Text("Edit worker" if editing else "Add worker", size=19, color=ui.TEXT,
                            weight=ft.FontWeight.BOLD),
                    ft.Text("Workers don't need an app account", size=12, color=ui.MUTED)],
                   spacing=0, tight=True, expand=True)],
        spacing=4,
    )
    return ui.screen([header, body])