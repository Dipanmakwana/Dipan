"""WORKER CARD - one worker row (Workers/workload board, Assign worker list).

build_worker_card(worker, on_tap, compact=False, recommendation=None)
  worker: row from GET /admin/workers (name, phone, skills, availability, shift_start/end,
          active_count, max_active, effort_load, load_pct, by_priority, overdue_count)
  recommendation: an item from GET /admin/issues/{id}/recommended-workers
          ({worker, score, breakdown, reasons, eta_text, flags, eligible, is_current}) -> score, reasons, flags
"""
import flet as ft

TEXT = "#211B36"
MUTED = "#77728C"
BORDER = "#E8E4F3"
PURPLE = "#7054F6"
PURPLE_DARK = "#392A78"
LAVENDER = "#F0EDFF"

AVAILABILITY = {
    "available": ("Available", "#1E7A43"),
    "busy": ("At full load", "#C25A00"),
    "on_leave": ("On leave", "#B4234D"),
    "off_today": ("Off today", "#77728C"),
    "inactive": ("Inactive", "#9C98A8"),
}

FLAG_LABELS = {
    "overloaded": ("Overloaded", "#C25A00", "#FFF2DC"),
    "off_shift": ("Off shift", "#77728C", "#EFEEF2"),
    "out_of_zone": ("Out of zone", "#1F5FBF", "#E5EFFC"),
}


def load_color(pct: float) -> str:
    """Green < 60 %, amber < 100 %, red at full load."""
    if pct >= 100:
        return "#C62848"
    if pct >= 60:
        return "#E09A1F"
    return "#2E9D5B"


def initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def _chip(text: str, color: str, bg: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=12,
        bgcolor=bg,
        content=ft.Text(text, size=10, color=color, weight=ft.FontWeight.W_600),
    )


def build_load_bar(worker: dict, width: int | None = None) -> ft.Control:
    max_active = worker.get("max_active") or 4
    pct = float(worker.get("load_pct") if worker.get("load_pct") is not None
                else 100 * (worker.get("effort_load") or 0) / max_active)
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Load", size=11, color=MUTED),
                    ft.Text(f"{worker.get('active_count', 0)} / {max_active} jobs", size=11, color=TEXT,
                            weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.ProgressBar(value=min(pct / 100, 1), color=load_color(pct), bgcolor="#EEEAF6", bar_height=7,
                           border_radius=6, width=width),
        ],
        spacing=4,
        tight=True,
    )


def build_worker_card(worker: dict, on_tap=None, compact: bool = False, recommendation: dict | None = None) -> ft.Control:
    rec = recommendation or {}
    availability = worker.get("availability")
    avail_label, avail_color = AVAILABILITY.get(availability, ("", MUTED))

    header_right = []
    if rec:
        score = rec.get("score", 0)
        header_right.append(
            ft.Container(
                width=46, height=46, border_radius=23,
                bgcolor=PURPLE if rec.get("eligible", True) else "#C9C4D8",
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    [ft.Text(str(score), size=15, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                     ft.Text("score", size=8, color="#FFFFFF")],
                    spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            )
        )

    subtitle_bits = []
    if avail_label:
        subtitle_bits += [ft.Icon(ft.Icons.CIRCLE, size=9, color=avail_color),
                          ft.Text(avail_label, size=11, color=avail_color, weight=ft.FontWeight.W_600)]
    if worker.get("shift_start") and worker.get("shift_end"):
        subtitle_bits += [ft.Text(f"· {str(worker['shift_start'])[:5]}–{str(worker['shift_end'])[:5]}", size=11, color=MUTED)]
    if rec.get("eta_text"):
        subtitle_bits += [ft.Text(f"· {rec['eta_text']}", size=11, color=MUTED)]

    skills = worker.get("skills") or []
    primary = worker.get("primary_skill")
    skill_text = ", ".join(s.title() + (" ★" if s == primary else "") for s in skills) or "No skills"

    rows = [
        ft.Row(
            [
                ft.CircleAvatar(content=ft.Text(initials(worker.get("name")), size=13, weight=ft.FontWeight.BOLD,
                                                color=PURPLE_DARK), bgcolor=LAVENDER, radius=21),
                ft.Column(
                    [
                        ft.Text(worker.get("name") or "Unnamed", size=15, color=TEXT, weight=ft.FontWeight.BOLD,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row(subtitle_bits, spacing=4, wrap=True),
                    ],
                    spacing=2, tight=True, expand=True,
                ),
                *header_right,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        ft.Text(skill_text, size=12, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
    ]

    if rec:
        chips = []
        if rec.get("is_current"):
            chips.append(_chip("Currently assigned", PURPLE_DARK, LAVENDER))
        if rec.get("best"):
            chips.append(_chip("Best match", "#FFFFFF", "#2E9D5B"))
        for flag in rec.get("flags") or []:
            label, color, bg = FLAG_LABELS.get(flag, (flag, MUTED, "#EFEEF2"))
            chips.append(_chip(label, color, bg))
        chips += [_chip(r, "#4A4560", "#F4F2F9") for r in rec.get("reasons") or []]
        rows.append(ft.Row(chips, spacing=6, run_spacing=6, wrap=True))

    rows.append(build_load_bar(worker))

    if not compact and not rec:
        bp = worker.get("by_priority") or {}
        counts = [f"{label} {bp.get(key, 0)}" for key, label in
                  (("urgent", "Urgent"), ("high", "High"), ("normal", "Normal"), ("low", "Low")) if bp.get(key)]
        detail = [ft.Text(" · ".join(counts) if counts else "No active jobs", size=11, color=MUTED, expand=True)]
        if worker.get("overdue_count"):
            detail.append(_chip(f"{worker['overdue_count']} overdue", "#FFFFFF", "#B4234D"))
        rows.append(ft.Row(detail, spacing=6))

    return ft.Container(
        padding=14,
        border_radius=16,
        bgcolor="#FFFFFF" if availability != "inactive" else "#F6F5F9",
        border=ft.Border.all(2 if rec.get("best") else 1, "#2E9D5B" if rec.get("best") else BORDER),
        ink=True,
        on_click=(lambda e: on_tap(worker.get("id"))) if on_tap else None,
        content=ft.Column(rows, spacing=8, tight=True),
    )