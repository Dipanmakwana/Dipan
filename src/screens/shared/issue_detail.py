"""ISSUE DETAIL  |  side: shared (student view now, staff view later)  |  route: /issue  |  navbar: hidden
Param: id (issue id), e.g. go(page, "/issue", id=42). Shows a back button instead of the navbar.

Works on Flet 0.x and 1.x (see the compatibility block below).
"""
from datetime import datetime, timezone

import flet as ft

from core.router import back

# =====================================================================
# Theme (white + purple)
# =====================================================================
PURPLE = "#6C3FC5"
PURPLE_DARK = "#4F2A9C"
PURPLE_LIGHT = "#F3EEFC"
BORDER = "#E6DDF7"
TEXT = "#1F1B2E"
MUTED = "#7A7391"
GREEN = "#2E9E6B"
AMBER = "#E0922B"
RED = "#D64545"

STEPS = ["reported", "assigned", "acknowledged", "in_progress", "resolved", "closed"]
STEP_LABEL = {
    "reported": "Reported",
    "assigned": "Assigned",
    "acknowledged": "Acknowledged",
    "in_progress": "In progress",
    "resolved": "Resolved",
    "closed": "Closed",
    "reopened": "Reopened",
}

# staff action -> button label (which ones show comes from the backend list)
STAFF_ACTIONS = {
    "acknowledge": "Acknowledge",
    "start_work": "Start work",
    "resolve": "Resolve",
    "reassign": "Reassign",
}

# =====================================================================
# Flet 0.x / 1.x compatibility
# =====================================================================
NEW = hasattr(ft, "Padding")  # True on Flet 1.x


def pad_all(v):
    return (ft.Padding if NEW else ft.padding).all(v)


def pad_sym(horizontal=0, vertical=0):
    return (ft.Padding if NEW else ft.padding).symmetric(horizontal=horizontal, vertical=vertical)


def pad_only(**kw):
    return (ft.Padding if NEW else ft.padding).only(**kw)


def mar_only(**kw):
    return (ft.Margin if NEW else ft.margin).only(**kw)


def border_all(width, color):
    return (ft.Border if NEW else ft.border).all(width, color)


def border_only(**kw):
    return (ft.Border if NEW else ft.border).only(**kw)


ALIGN_CENTER = ft.Alignment(0, 0)
ALIGN_TL = ft.Alignment(-1, -1)
ALIGN_BR = ft.Alignment(1, 1)

_Fit = ft.BoxFit if hasattr(ft, "BoxFit") else ft.ImageFit
FIT_COVER, FIT_CONTAIN = _Fit.COVER, _Fit.CONTAIN


def _open(page, dlg):
    if hasattr(page, "show_dialog"):
        page.show_dialog(dlg)
    elif hasattr(page, "open"):
        page.open(dlg)
    else:
        page.dialog = dlg
        dlg.open = True
        page.update()


def _close(page, dlg):
    if hasattr(page, "pop_dialog"):
        page.pop_dialog()
    elif hasattr(page, "close"):
        page.close(dlg)
    else:
        dlg.open = False
        page.update()


def _snack(page, msg):
    _open(page, ft.SnackBar(ft.Text(msg)))


def _launch(page, url):
    try:
        if NEW:
            page.run_task(page.launch_url, url)  # async in Flet 1.x
        else:
            page.launch_url(url)
    except Exception as ex:
        _snack(page, f"Couldn't open: {ex}")


def _btn(cls, text, on_click, icon, style):
    if NEW:
        return cls(content=text, icon=icon, on_click=on_click, style=style)
    return cls(text, icon=icon, on_click=on_click, style=style)


def _primary_btn(text, on_click, icon=None):
    style = ft.ButtonStyle(
        bgcolor=PURPLE, color=ft.Colors.WHITE,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    return _btn(ft.FilledButton, text, on_click, icon, style)


def _outline_btn(text, on_click, icon=None, color=PURPLE):
    style = ft.ButtonStyle(
        color=color, side=ft.BorderSide(1, color),
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    return _btn(ft.OutlinedButton, text, on_click, icon, style)


def _text_btn(text, on_click):
    return _btn(ft.TextButton, text, on_click, None, ft.ButtonStyle(color=PURPLE))


# =====================================================================
# Data (service with fallback sample data)
# =====================================================================
def _sample(id):
    return {
        "id": id,
        "category": "Plumbing",
        "status": "resolved",
        "priority": "high",
        "created_at": "2026-10-20T09:15:00+00:00",
        "sla_due": "2026-10-23T09:15:00+00:00",
        "description": "Water is leaking from the tap in the 2nd floor washroom and the floor is slippery.",
        "photos": [],
        "building": "Block A",
        "room": "2nd floor washroom",
        "assigned_to": {"name": "Ramesh Patil", "phone": "+910000000000", "email": "ramesh@campus.edu"},
        "timeline": [
            {"status": "reported", "at": "2026-10-20T09:15:00+00:00", "actor": "You"},
            {"status": "assigned", "at": "2026-10-20T10:00:00+00:00", "actor": "Admin"},
            {"status": "acknowledged", "at": "2026-10-20T11:30:00+00:00", "actor": "Ramesh Patil"},
            {"status": "in_progress", "at": "2026-10-21T08:45:00+00:00", "actor": "Ramesh Patil"},
            {"status": "resolved", "at": "2026-10-22T16:10:00+00:00", "actor": "Ramesh Patil"},
        ],
        "comments": [
            {"author": "Ramesh Patil", "at": "2026-10-22T16:12:00+00:00", "text": "Replaced the washer, please check."},
        ],
        "allowed_transitions": [],
    }


def _get_issue(id):
    try:
        from services import issue_service
        fn = getattr(issue_service, "get_issue", None)
    except ImportError:
        fn = None
    return fn(id) if fn else _sample(id)


def _call(fn_name, *args):
    try:
        from services import issue_service
        fn = getattr(issue_service, fn_name, None)
    except ImportError:
        fn = None
    if fn:
        fn(*args)

def _role():
    try:
        from core.session import session
        return session.role()
    except Exception:
        return "student"


# =====================================================================
# Helpers
# =====================================================================
def _parse(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _fmt(ts):
    d = _parse(ts) if ts else None
    return d.astimezone().strftime("%d %b, %I:%M %p") if d else "-"


def _sla_text(data):
    due = _parse(data.get("sla_due"))
    if not due:
        return "", MUTED
    if data["status"] in ("resolved", "closed"):
        return f"SLA was {_fmt(data['sla_due'])}", MUTED
    delta = due - datetime.now(timezone.utc)
    hrs = int(abs(delta.total_seconds()) // 3600)
    if delta.total_seconds() < 0:
        return f"Overdue by {hrs}h", RED
    return f"Due in {hrs}h", AMBER if hrs < 24 else GREEN


def _card(title, content, icon=None):
    header = ft.Row(
        [
            *([ft.Icon(icon, color=PURPLE, size=18)] if icon else []),
            ft.Text(title, weight=ft.FontWeight.W_600, size=15, color=TEXT),
        ],
        spacing=8,
    )
    return ft.Container(
        bgcolor=ft.Colors.WHITE,
        border=border_all(1, BORDER),
        border_radius=16,
        padding=pad_all(16),
        shadow=ft.BoxShadow(blur_radius=12, color="#146C3FC5", offset=ft.Offset(0, 3)),
        content=ft.Column([header, content], spacing=12),
    )


def _chip(text, color):
    return ft.Container(
        content=ft.Text(text, size=12, weight=ft.FontWeight.W_600, color=color),
        padding=pad_sym(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.18, color),
    )


# =====================================================================
# View
# =====================================================================
def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    body = ft.Container(expand=True)
    mounted = {"v": False}

    appbar = ft.Container(
        bgcolor=ft.Colors.WHITE,
        padding=pad_sym(horizontal=8, vertical=8),
        border=border_only(bottom=ft.BorderSide(1, BORDER)),
        content=ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_BACK, icon_color=PURPLE, on_click=lambda e: back(page)),
                ft.Text(f"Issue #{id}", size=20, weight=ft.FontWeight.BOLD, color=PURPLE_DARK),
            ]
        ),
    )

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------
    def header_card(d):
        sla, _ = _sla_text(d)
        status = d["status"]
        return ft.Container(
            border_radius=16,
            padding=pad_all(16),
            gradient=ft.LinearGradient(
                begin=ALIGN_TL, end=ALIGN_BR, colors=[PURPLE, PURPLE_DARK],
            ),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(d["category"], size=22, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE),
                            ft.Container(
                                content=ft.Text(STEP_LABEL.get(status, status.title()), size=12,
                                                weight=ft.FontWeight.W_600, color=PURPLE_DARK),
                                bgcolor=ft.Colors.WHITE, border_radius=20,
                                padding=pad_sym(horizontal=12, vertical=5),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            _chip(f"{d['priority'].title()} priority", ft.Colors.WHITE),
                            ft.Text(f"Reported {_fmt(d['created_at'])}", size=12, color="#E6DDF7"),
                        ],
                        wrap=True, spacing=10,
                    ),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TIMER_OUTLINED, size=16, color=ft.Colors.WHITE),
                            ft.Text(sla, size=13, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                        ],
                        spacing=6, visible=bool(sla),
                    ),
                ],
                spacing=10,
            ),
        )

    def zoom(url):
        dlg = ft.AlertDialog(
            content=ft.InteractiveViewer(
                min_scale=1, max_scale=5,
                content=ft.Image(src=url, fit=FIT_CONTAIN),
            ),
            actions=[_text_btn("Close", lambda e: _close(page, dlg))],
        )
        _open(page, dlg)

    def photos_card(d):
        photos = d.get("photos") or []
        if not photos:
            return None
        strip = ft.Row(
            [
                ft.Container(
                    content=ft.Image(src=u, width=130, height=130, fit=FIT_COVER, border_radius=12),
                    on_click=lambda e, u=u: zoom(u),
                    ink=True, border_radius=12,
                )
                for u in photos
            ],
            scroll=ft.ScrollMode.AUTO, spacing=10,
        )
        return _card("Photos", strip, ft.Icons.PHOTO_LIBRARY_OUTLINED)

    def description_card(d):
        return _card("Description", ft.Text(d["description"], size=14, color=TEXT), ft.Icons.NOTES)

    def location_card(d):
        rows = [
            ft.Row([ft.Icon(ft.Icons.APARTMENT, size=18, color=MUTED),
                    ft.Text(d.get("building") or "-", color=TEXT, weight=ft.FontWeight.W_500)],
                   spacing=8),
            ft.Row([ft.Icon(ft.Icons.MEETING_ROOM_OUTLINED, size=18, color=MUTED),
                    ft.Text(d.get("room") or "-", color=TEXT)], spacing=8),
        ]
        # TODO (later): small map with pin
        return _card("Location", ft.Column(rows, spacing=8), ft.Icons.LOCATION_ON_OUTLINED)

    def assigned_card(d):
        a = d.get("assigned_to")
        if not a:
            return None

        def launch(url):
            return lambda e: _launch(page, url)

        content = ft.Row(
            [
                ft.CircleAvatar(content=ft.Text(a["name"][:1].upper(), color=ft.Colors.WHITE),
                                bgcolor=PURPLE, radius=22),
                ft.Column([ft.Text(a["name"], weight=ft.FontWeight.W_600, color=TEXT),
                           ft.Text("Assigned staff", size=12, color=MUTED)],
                          spacing=2, expand=True),
                ft.IconButton(ft.Icons.CALL, icon_color=PURPLE, bgcolor=PURPLE_LIGHT,
                              on_click=launch(f"tel:{a.get('phone', '')}"),
                              visible=bool(a.get("phone"))),
                ft.IconButton(ft.Icons.EMAIL_OUTLINED, icon_color=PURPLE, bgcolor=PURPLE_LIGHT,
                              on_click=launch(f"mailto:{a.get('email', '')}"),
                              visible=bool(a.get("email"))),
            ],
            spacing=10,
        )
        return _card("Assigned to", content, ft.Icons.PERSON_OUTLINE)

    def timeline_card(d):
        events = d.get("timeline") or []
        done = {e["status"]: e for e in events if e["status"] in STEPS}
        current = d["status"] if d["status"] in STEPS else None
        items = []  # (dot, label, sub, reached, is_current)

        for s in STEPS:
            e = done.get(s)
            is_current = s == current
            reached = e is not None
            color = PURPLE if reached else BORDER
            dot = ft.Container(
                width=22, height=22, border_radius=11,
                bgcolor=color if reached else ft.Colors.WHITE,
                border=border_all(2, color),
                content=ft.Icon(ft.Icons.CHECK, size=13, color=ft.Colors.WHITE) if reached else None,
                alignment=ALIGN_CENTER,
                shadow=ft.BoxShadow(blur_radius=8, color="#556C3FC5") if is_current else None,
            )
            sub = f"{_fmt(e['at'])}  •  {e['actor']}" if e else "Pending"
            items.append((dot, STEP_LABEL[s], sub, reached, is_current))

            # reopen events show right after "resolved"
            if s == "resolved":
                for r in [x for x in events if x["status"] == "reopened"]:
                    rd = ft.Container(
                        width=22, height=22, border_radius=11, bgcolor=RED,
                        content=ft.Icon(ft.Icons.REPLAY, size=13, color=ft.Colors.WHITE),
                        alignment=ALIGN_CENTER,
                    )
                    note = f"\n{r['note']}" if r.get("note") else ""
                    items.append((rd, "Reopened", f"{_fmt(r['at'])}  •  {r['actor']}{note}", True, False))

        rows = []
        for i, (dot, label, sub, reached, is_current) in enumerate(items):
            last = i == len(items) - 1
            line = ft.Container(width=2, height=34, bgcolor=PURPLE if reached else BORDER,
                                visible=not last)
            rows.append(
                ft.Row(
                    [
                        ft.Column([dot, line], spacing=0,
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Container(
                            expand=True,
                            padding=pad_only(bottom=8, left=8, top=2),
                            bgcolor=PURPLE_LIGHT if is_current else None,
                            border_radius=10,
                            margin=mar_only(left=4),
                            content=ft.Column(
                                [
                                    ft.Text(label, size=14, color=TEXT if reached else MUTED,
                                            weight=ft.FontWeight.BOLD if is_current
                                            else ft.FontWeight.W_500),
                                    ft.Text(sub, size=12, color=MUTED),
                                ],
                                spacing=1,
                            ),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START, spacing=8,
                )
            )
        return _card("Timeline", ft.Column(rows, spacing=0), ft.Icons.TIMELINE)

    def comments_card(d):
        comments = d.get("comments") or []
        lst = ft.Column(
            [
                ft.Container(
                    bgcolor=PURPLE_LIGHT, border_radius=12, padding=pad_all(10),
                    content=ft.Column(
                        [
                            ft.Row(
                                [ft.Text(c["author"], weight=ft.FontWeight.W_600, size=13,
                                         color=PURPLE_DARK),
                                 ft.Text(_fmt(c["at"]), size=11, color=MUTED)],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(c["text"], size=13, color=TEXT),
                        ],
                        spacing=3,
                    ),
                )
                for c in comments
            ] or [ft.Text("No comments yet", size=13, color=MUTED)],
            spacing=8,
        )
        field = ft.TextField(
            hint_text="Add a comment", expand=True, border_radius=12, border_color=BORDER,
            focused_border_color=PURPLE, cursor_color=PURPLE, dense=True, text_size=14,
        )

        def send(e):
            text = (field.value or "").strip()
            if not text:
                return
            try:
                _call("add_comment", id, text)
            except Exception as ex:
                _snack(page, f"Couldn't send: {ex}")
                return
            load()

        field.on_submit = send
        send_btn = ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color=ft.Colors.WHITE,
                                 bgcolor=PURPLE, on_click=send)
        return _card("Comments", ft.Column([lst, ft.Row([field, send_btn], spacing=8)], spacing=12),
                     ft.Icons.CHAT_BUBBLE_OUTLINE)

    # ------------------------------------------------------------------
    # Student actions
    # ------------------------------------------------------------------
    def confirm_dialog(e):
        state = {"rating": 0}
        stars = ft.Row(spacing=0)
        feedback = ft.TextField(
            hint_text="Feedback (optional)", multiline=True, min_lines=2, max_lines=4,
            border_radius=12, border_color=BORDER, focused_border_color=PURPLE,
        )
        err = ft.Text("", color=RED, size=12)

        def set_rating(i):
            state["rating"] = i
            paint()
            stars.update()

        def paint():
            stars.controls = [
                ft.IconButton(
                    ft.Icons.STAR if i <= state["rating"] else ft.Icons.STAR_BORDER,
                    icon_color=AMBER, icon_size=32,
                    on_click=lambda e, i=i: set_rating(i),
                )
                for i in range(1, 6)
            ]

        paint()

        def submit(e):
            if state["rating"] == 0:
                err.value = "Please select a rating"
                err.update()
                return
            try:
                _call("submit_feedback", id, state["rating"], (feedback.value or "").strip())
            except Exception as ex:
                err.value = str(ex)
                err.update()
                return
            _close(page, dlg)
            load()

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm & close", color=PURPLE_DARK),
            content=ft.Container(
                width=320,
                content=ft.Column(
                    [ft.Text("How was the resolution?", color=MUTED), stars, feedback, err],
                    tight=True,
                ),
            ),
            actions=[_text_btn("Cancel", lambda e: _close(page, dlg)),
                     _primary_btn("Submit", submit)],
        )
        _open(page, dlg)

    def reopen_dialog(e):
        reason = ft.TextField(
            hint_text="Why are you reopening?", multiline=True, min_lines=2, max_lines=4,
            border_radius=12, border_color=BORDER, focused_border_color=PURPLE,
        )

        def submit(e):
            if not (reason.value or "").strip():
                reason.error_text = "Reason is required"
                reason.update()
                return
            try:
                _call("reopen", id, reason.value.strip())
            except Exception as ex:
                reason.error_text = str(ex)
                reason.update()
                return
            _close(page, dlg)
            load()

        dlg = ft.AlertDialog(
            title=ft.Text("Reopen issue", color=PURPLE_DARK),
            content=ft.Container(reason, width=320),
            actions=[_text_btn("Cancel", lambda e: _close(page, dlg)),
                     _primary_btn("Reopen", submit)],
        )
        _open(page, dlg)

    def student_actions(d):
        if d["status"] != "resolved":
            return None
        return _card(
            "Is this fixed?",
            ft.Row(
                [_primary_btn("Confirm & close", confirm_dialog, ft.Icons.CHECK_CIRCLE_OUTLINE),
                 _outline_btn("Reopen", reopen_dialog, ft.Icons.REPLAY, RED)],
                wrap=True, spacing=10,
            ),
            ft.Icons.TASK_ALT,
        )

    # ------------------------------------------------------------------
    # Staff actions (buttons come from backend allowed_transitions)
    # ------------------------------------------------------------------
    def staff_actions(d):
        allowed = d.get("allowed_transitions") or []
        btns = [
            _primary_btn(STAFF_ACTIONS.get(t, t.replace("_", " ").title()),
                         lambda e, t=t: _snack(page, f"TODO: {t}"))
            for t in allowed
        ]
        if not btns:
            return None
        return _card("Actions", ft.Row(btns, wrap=True, spacing=10), ft.Icons.BOLT)

    # ------------------------------------------------------------------
    # States
    # ------------------------------------------------------------------
    def loading_view():
        return ft.Container(alignment=ALIGN_CENTER, content=ft.ProgressRing(color=PURPLE))

    def error_view(msg):
        return ft.Container(
            alignment=ALIGN_CENTER, padding=pad_all(24),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=RED),
                    ft.Text("Couldn't load this issue", size=16, weight=ft.FontWeight.W_600, color=TEXT),
                    ft.Text(str(msg), size=12, color=MUTED, text_align=ft.TextAlign.CENTER),
                    _primary_btn("Retry", lambda e: load(), ft.Icons.REFRESH),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, tight=True,
            ),
        )

    def content_view(d):
        role = _role()
        parts = [
            header_card(d),
            student_actions(d) if role == "student" else staff_actions(d),
            photos_card(d),
            description_card(d),
            location_card(d),
            assigned_card(d),
            timeline_card(d),
            comments_card(d),
        ]
        return ft.Column([p for p in parts if p is not None], spacing=14,
                         scroll=ft.ScrollMode.AUTO, expand=True)

    def load():
        body.content = loading_view()
        if mounted["v"]:
            body.update()
        try:
            data = _get_issue(id)
            body.content = ft.Container(content=content_view(data), padding=pad_all(16), expand=True)
        except Exception as ex:
            body.content = error_view(ex)
        if mounted["v"]:
            body.update()

    load()
    mounted["v"] = True

    return ft.Container(
        bgcolor=ft.Colors.WHITE, expand=True,
        content=ft.Column([appbar, body], spacing=0, expand=True),
    )