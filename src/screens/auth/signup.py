"""SIGNUP (+ email OTP verification)  |  side: student only  |  route: /signup  |  navbar: hidden
Staff accounts are NOT created here; the admin creates them in Django Admin.
This one file has two steps: step "form" and step "otp" (open the 2nd step with go(page, "/signup", step="otp", email=...)).

UI TODO - step 1 (form)
  [=] TextField  "Full name"
  [=] TextField  "Institute email"            (must end with @config.ALLOWED_EMAIL_DOMAIN)
  [=] TextField  "Roll number"                (optional)
  [ ] Dropdown   "Hostel / building"          (optional; options from backend buildings endpoint)
  [=] TextField  "Password"                   (min 8 chars, reveal toggle)
  [=] TextField  "Confirm password"           (must match)
  [=] Button     "Create account"             (spinner while loading)
  [=] TextButton "Already registered? Log in" -> back(page)

UI TODO - step 2 (OTP)
  [=] Text       "We sent a 6-digit code to <email>"
  [=] TextField  "Verification code"          (numeric keyboard, config.OTP_LENGTH digits)
  [ ] Button     "Verify"
  [=] TextButton "Resend code"                (30 s cooldown with countdown text)
  [ ] Error text (wrong / expired code, too many attempts)

Behaviour TODO
  [ ] Client-side validation, then auth_service.signup(...) -> server emails OTP
  [ ] auth_service.verify_otp(email, code) -> session.set_session(...) -> reset(page, home_path())
  [ ] Server must reject non-institute emails (client check is only for quick feedback)
"""

import asyncio
import inspect
import re

import flet as ft

import config
from core import session
from core.router import go, reset, home_path
from services import auth_service


# Keep these tokens aligned with the CampusCare login screen.
PURPLE = "#7054F6"
PURPLE_DARK = "#392A78"
PURPLE_MID = "#8C79FA"
LAVENDER = "#F0EDFF"
PAGE_BG = "#F8F7FF"
TEXT = "#211B36"
MUTED = "#77728C"
BORDER = "#E8E4F3"
WHITE = "#FFFFFF"
ERROR = "#B4234D"
ERROR_BG = "#FFF0F3"
SUCCESS_BG = "#F0ECFF"


def _allowed_domain() -> str:
    return str(getattr(config, "ALLOWED_EMAIL_DOMAIN", "")).strip().lstrip("@").lower()


def _email_error(value: str, *, required: bool = False) -> str | None:
    email = (value or "").strip()
    domain = _allowed_domain()
    if not email:
        return "Enter your institute email." if required else None
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return "Enter a valid email address."
    if domain and email.lower().split("@", 1)[1] != domain:
        return f"Use your @{domain} institute email."
    return None


def _error_message(exc: Exception) -> tuple[str, str]:
    """Map common API failures to clear, non-technical form messages."""
    response = getattr(exc, "response", None)
    bits = [str(exc)]
    if response is not None:
        bits.append(str(getattr(response, "text", "")))
        try:
            body = response.json()
            if isinstance(body, dict):
                bits.extend(str(body.get(key, "")) for key in ("detail", "message", "error", "code"))
        except Exception:
            pass
    detail = " ".join(item for item in bits if item).lower()
    status = getattr(exc, "status_code", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)

    if any(word in detail for word in ("already exists", "already registered", "email already")):
        return "conflict", "An account with this institute email already exists. Try logging in instead."
    if any(word in detail for word in ("invalid code", "incorrect code", "expired code", "otp", "verification code")):
        return "otp", "That verification code is invalid or expired. Check the code and try again."
    if status == 429 or any(word in detail for word in ("too many", "rate limit", "attempt limit")):
        return "limit", "Too many attempts. Please wait a little before trying again."

    name = type(exc).__name__.lower()
    module = type(exc).__module__.lower()
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)) or any(
        word in name for word in ("timeout", "connecterror", "networkerror", "requesterror")
    ) or ("httpx" in module and any(word in name for word in ("timeout", "connect", "network"))):
        return "network", "We couldn't reach CampusCare. Check your connection and try again."

    if status == 400 or status == 409:
        return "validation", "Please check your details. The server couldn't accept this registration."
    return "generic", "Something went wrong. Please try again."


def _result_error(result: dict) -> tuple[str, str] | None:
    """Read common error payload conventions without assuming one API schema."""
    if not isinstance(result, dict):
        return None
    message = " ".join(str(result.get(key, "")) for key in ("detail", "message", "error", "code")).strip()
    if result.get("success") is False or result.get("error"):
        lowered = message.lower()
        if any(word in lowered for word in ("already exists", "already registered", "email already")):
            return "conflict", "An account with this institute email already exists. Try logging in instead."
        if any(word in lowered for word in ("invalid code", "incorrect code", "expired code", "otp", "verification code")):
            return "otp", "That verification code is invalid or expired. Check the code and try again."
        if any(word in lowered for word in ("network", "unreachable", "timeout", "connection")):
            return "network", "We couldn't reach CampusCare. Check your connection and try again."
        if message:
            return "generic", message
        return "generic", "Something went wrong. Please try again."
    return None


def _campuscare_logo(width: int = 150, height: int = 150) -> ft.Image:
    """Display the supplied logo from the Flet assets directory."""
    return ft.Image(src="campuscare_logo.png", width=width, height=height)


def _brand_lockup(*, light: bool = False) -> ft.Control:
    return ft.Column(
        [
            _campuscare_logo(150, 150),
            ft.Text("Your campus, cared for.", size=11, color="#E3DEFF" if light else MUTED),
        ],
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )


def _field_style(width: int, *, label: str, hint: str, icon, password: bool = False, keyboard=None) -> ft.TextField:
    return ft.TextField(
        label=label,
        hint_text=hint,
        width=width,
        keyboard_type=keyboard or ft.KeyboardType.TEXT,
        password=password,
        can_reveal_password=password,
        prefix_icon=icon,
        text_style=ft.TextStyle(color=TEXT, size=14),
        label_style=ft.TextStyle(color=MUTED, size=13),
        hint_style=ft.TextStyle(color="#AAA5BC", size=12),
        cursor_color=PURPLE,
        border_color=BORDER,
        focused_border_color=PURPLE,
        error_style=ft.TextStyle(color=ERROR, size=11),
        border_radius=13,
        content_padding=15,
    )

def _brand_panel() -> ft.Control:
    return ft.Container(
        width=380,
        padding=28,
        border_radius=28,
        bgcolor=PURPLE_DARK,
        content=ft.Column(
            [
                # Logo and branding side by side
                ft.Row(
                    [
                        _campuscare_logo(100, 100),
                        ft.Column(
                            [
                                ft.Text(
                                    "CampusCare",
                                    size=23,
                                    weight=ft.FontWeight.BOLD,
                                    color=WHITE,
                                ),
                                ft.Text(
                                    "Student Community",
                                    size=12,
                                    color="#E3DEFF",
                                ),
                                ft.Text(
                                    "For Students & Staff",
                                    size=11,
                                    color="#C6BDFF",
                                ),
                            ],
                            spacing=5,
                            alignment=ft.MainAxisAlignment.CENTER,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(color="#51418F", height=24),
                ft.Text(
                    "Your voice matters.",
                    size=27,
                    weight=ft.FontWeight.BOLD,
                    color=WHITE,
                ),
                ft.Text(
                    "Report campus concerns, follow progress, "
                    "and connect with support.",
                    size=13,
                    color="#E3DEFF",
                ),
                ft.Container(height=12),
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.FORUM_OUTLINED,
                            color="#C6BDFF",
                            size=22,
                        ),
                        ft.Text(
                            "Speak up with confidence",
                            size=13,
                            color=WHITE,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.TRACK_CHANGES_ROUNDED,
                            color="#C6BDFF",
                            size=22,
                        ),
                        ft.Text(
                            "Track your concerns",
                            size=13,
                            color=WHITE,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.SHIELD_OUTLINED,
                            color="#C6BDFF",
                            size=22,
                        ),
                        ft.Text(
                            "Verified institute access",
                            size=13,
                            color=WHITE,
                        ),
                    ],
                    spacing=12,
                ),
            ],
            spacing=12,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

def view(page: ft.Page, step: str = "form", email: str = "", **params) -> ft.Control:
    """Render registration step (``form``) or email verification step (``otp``)."""
    viewport_width = getattr(page, "width", None)
    compact = viewport_width is None or viewport_width < 960
    card_width = max(280, min(460, int(viewport_width or 390) - 36)) if compact else 460
    inner_width = max(240, card_width - 60)
    state = {"loading": False, "resend_seconds": 0, "cooldown_task": None}
    show_otp = str(step).lower() == "otp"
    email = (email or "").strip()

    error_area = ft.Container(
        visible=False,
        width=inner_width,
        padding=12,
        border_radius=12,
        bgcolor=ERROR_BG,
    )

    def display_message(message: str, *, kind: str = "generic") -> None:
        is_success = kind == "success"
        is_network = kind == "network"
        error_area.bgcolor = SUCCESS_BG if is_success else ERROR_BG
        color = PURPLE_DARK if is_success else ERROR
        icon = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED if is_success else (
            ft.Icons.WIFI_OFF_ROUNDED if is_network else ft.Icons.ERROR_OUTLINE_ROUNDED
        )
        error_area.content = ft.Row(
            [ft.Icon(icon, color=color, size=19), ft.Text(message, color=color, size=12, expand=True)],
            spacing=9,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        error_area.visible = True

    def clear_message() -> None:
        error_area.visible = False
        error_area.content = None

    # ------------------------------------------------------------------
    # Step 1: registration form
    # ------------------------------------------------------------------
    if not show_otp:
        name_field = _field_style(
            inner_width, label="Full name", hint="Enter your name",
            icon=ft.Icons.PERSON_OUTLINE_ROUNDED, keyboard=ft.KeyboardType.NAME,
        )
        email_field = _field_style(
            inner_width, label="Institute email",
            hint=f"you@{_allowed_domain()}" if _allowed_domain() else "you@institute.edu",
            icon=ft.Icons.MAIL_OUTLINE_ROUNDED, keyboard=ft.KeyboardType.EMAIL,
        )
        roll_field = _field_style(
            inner_width, label="Roll number (optional)", hint="e.g. 23B1234",
            icon=ft.Icons.BADGE_OUTLINED,
        )
        password_field = _field_style(
            inner_width, label="Password", hint="At least 8 characters",
            icon=ft.Icons.LOCK_OUTLINE_ROUNDED, password=True,
        )
        confirm_field = _field_style(
            inner_width, label="Confirm password", hint="Re-enter your password",
            icon=ft.Icons.LOCK_RESET_ROUNDED, password=True,
        )

        # Building options should come from the backend. The router may pass a
        # list of {id, name} objects when a building endpoint becomes available.
        raw_buildings = params.get("buildings") or params.get("building_options") or []
        building_options: list[ft.DropdownOption] = []
        for building in raw_buildings:
            if isinstance(building, dict):
                key = building.get("id", building.get("value", building.get("name")))
                label = building.get("name", building.get("label", key))
            else:
                key = label = building
            if key is not None and label is not None:
                building_options.append(ft.DropdownOption(key=str(key), text=str(label)))

        building_field = ft.Dropdown(
            label="Hostel / building (optional)",
            hint_text="Select your hostel or building",
            width=inner_width,
            options=building_options,
            disabled=not bool(building_options),
            leading_icon=ft.Icons.APARTMENT_OUTLINED,
            text_style=ft.TextStyle(color=TEXT, size=14),
            label_style=ft.TextStyle(color=MUTED, size=13),
            hint_style=ft.TextStyle(color="#AAA5BC", size=12),
            border_color=BORDER,
            focused_border_color=PURPLE,
            border_radius=13,
            content_padding=ft.Padding.symmetric(horizontal=15, vertical=14),
            on_select=lambda e: clear_message(),
        )

        async def on_signup(e) -> None:
            if state["loading"]:
                return
            full_name = (name_field.value or "").strip()
            institute_email = (email_field.value or "").strip()
            password = password_field.value or ""
            confirm = confirm_field.value or ""

            name_field.error_text = "Enter your full name." if not full_name else None
            email_field.error_text = _email_error(institute_email, required=True)
            password_field.error_text = (
                "Use at least 8 characters." if len(password) < 8 else None
            )
            confirm_field.error_text = (
                "Passwords don't match." if confirm != password else ("Confirm your password." if not confirm else None)
            )
            clear_message()
            if name_field.error_text or email_field.error_text or password_field.error_text or confirm_field.error_text:
                page.update()
                return

            signup_fn = getattr(auth_service, "signup", None)
            if not callable(signup_fn):
                display_message(
                    "Account creation isn't connected to the server yet. The signup UI is ready, but auth_service.signup still needs implementation."
                )
                page.update()
                return

            state["loading"] = True
            create_button.disabled = True
            create_button.content = button_content("Creating account...", loading=True)
            page.update()
            try:
                result = signup_fn(
                    full_name,
                    institute_email,
                    password,
                    (roll_field.value or "").strip() or None,
                    building_field.value or None,
                )
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, dict):
                    err = _result_error(result)
                    if err:
                        display_message(err[1], kind=err[0])
                        return
                    # A signup response without an explicit error means the
                    # service accepted the request and sent an OTP.
                    go(page, "/signup", step="otp", email=institute_email)
                    return
                if result is True or result is None:
                    go(page, "/signup", step="otp", email=institute_email)
                else:
                    display_message("We couldn't confirm that your account was created. Please try again.")
            except Exception as exc:
                kind, message = _error_message(exc)
                display_message(message, kind=kind)
            finally:
                state["loading"] = False
                create_button.disabled = False
                create_button.content = button_content("Create account")
                page.update()

        def button_content(label: str, *, loading: bool = False) -> ft.Control:
            controls: list[ft.Control] = []
            if loading:
                controls.append(ft.ProgressRing(width=17, height=17, stroke_width=2, color=WHITE))
            controls.append(ft.Text(label, color=WHITE, size=14, weight=ft.FontWeight.BOLD))
            if not loading:
                controls.append(ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, color=WHITE, size=19))
            return ft.Row(
                controls,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            )

        create_button = ft.Button(
            content=button_content("Create account"),
            width=inner_width,
            height=52,
            on_click=on_signup,
            style=ft.ButtonStyle(
                bgcolor=PURPLE,
                color=WHITE,
                shape=ft.RoundedRectangleBorder(radius=14),
                elevation=0,
            ),
        )

        def clear_field_errors(e=None) -> None:
            if error_area.visible:
                clear_message()
            page.update()

        for field in (name_field, email_field, roll_field, password_field, confirm_field):
            field.on_change = clear_field_errors
        password_field.on_submit = on_signup
        confirm_field.on_submit = on_signup

        form_controls: list[ft.Control] = [
            ft.Text("LET'S GET YOU STARTED", size=10, color=PURPLE, weight=ft.FontWeight.BOLD),
            ft.Text("Create your account", size=25, color=TEXT, weight=ft.FontWeight.BOLD),
            ft.Text("Join CampusCare with your institute email.", size=12, color=MUTED),
            ft.Container(height=1),
            name_field,
            email_field,
            roll_field,
            building_field,
        ]
        if not building_options:
            form_controls.append(
                ft.Text(
                    "Building choices will appear when the campus directory is connected.",
                    size=10,
                    color=MUTED,
                    width=inner_width,
                )
            )
        form_controls.extend(
            [
                password_field,
                confirm_field,
                error_area,
                create_button,
                ft.Row(
                    [
                        ft.Text("Already registered?", size=12, color=MUTED),
                        ft.TextButton(
                            "Log in",
                            on_click=lambda e: go(page, "/login"),
                            style=ft.ButtonStyle(color=PURPLE),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
                ft.Divider(height=1, color=BORDER),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SHIELD_OUTLINED, size=15, color=PURPLE_MID),
                        ft.Text("Only verified institute accounts can continue.", size=10, color=MUTED),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
            ]
        )
        card_title = "Create an account"
        card_body = ft.Column(
            form_controls,
            spacing=11,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        )

    # ------------------------------------------------------------------
    # Step 2: email one-time password verification
    # ------------------------------------------------------------------
    else:
        otp_length = max(1, int(getattr(config, "OTP_LENGTH", 6) or 6))
        email_display = email or "your institute email"
        otp_field = _field_style(
            inner_width,
            label="Verification code",
            hint=f"Enter the {otp_length}-digit code",
            icon=ft.Icons.PASSWORD_ROUNDED,
            keyboard=ft.KeyboardType.NUMBER,
        )
        otp_field.max_length = otp_length

        resend_button = ft.TextButton(
            "Resend code",
            style=ft.ButtonStyle(color=PURPLE),
        )

        async def on_verify(e) -> None:
            if state["loading"]:
                return
            code = re.sub(r"\s+", "", otp_field.value or "")
            otp_field.error_text = None
            clear_message()
            if not email:
                display_message("The email address is missing. Return to sign up and try again.")
                page.update()
                return
            if not code.isdigit() or len(code) != otp_length:
                otp_field.error_text = f"Enter the complete {otp_length}-digit code."
                page.update()
                return

            verify_fn = getattr(auth_service, "verify_otp", None)
            if not callable(verify_fn):
                display_message(
                    "Email verification isn't connected to the server yet. The UI is ready, but auth_service.verify_otp still needs implementation."
                )
                page.update()
                return

            state["loading"] = True
            verify_button.disabled = True
            verify_button.content = otp_button_content("Verifying...", loading=True)
            page.update()
            try:
                result = verify_fn(email, code)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, dict):
                    err = _result_error(result)
                    if err:
                        display_message(err[1], kind=err[0])
                        return
                    access = result.get("access")
                    refresh = result.get("refresh", "")
                    user = result.get("user")
                    if not access or not isinstance(user, dict):
                        # Some APIs acknowledge the OTP but don't return tokens.
                        # Do not create a fake session; make the contract explicit.
                        display_message(
                            "The server accepted a response without account session details. The verification API must return access, refresh, and user data."
                        )
                        return
                    session.set_session(str(access), str(refresh), user)
                    reset(page, home_path())
                    return
                display_message("The server returned an unexpected response. Please try again.")
            except Exception as exc:
                kind, message = _error_message(exc)
                display_message(message, kind=kind)
            finally:
                state["loading"] = False
                verify_button.disabled = False
                verify_button.content = otp_button_content("Verify email")
                page.update()

        async def on_resend(e) -> None:
            if state["loading"] or state["resend_seconds"] > 0:
                return
            clear_message()
            resend_fn = getattr(auth_service, "resend_otp", None)
            if not callable(resend_fn):
                display_message(
                    "Resending isn't connected to the server yet. Implement auth_service.resend_otp to send a new code."
                )
                page.update()
                return
            state["loading"] = True
            resend_button.disabled = True
            resend_button.text = "Sending code..."
            page.update()
            try:
                result = resend_fn(email)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, dict):
                    err = _result_error(result)
                    if err:
                        display_message(err[1], kind=err[0])
                        return
                state["resend_seconds"] = 30
                display_message(f"A new verification code was requested for {email}.", kind="success")
                asyncio.create_task(run_resend_cooldown())
            except Exception as exc:
                kind, message = _error_message(exc)
                display_message(message, kind=kind)
            finally:
                state["loading"] = False
                page.update()

        async def run_resend_cooldown() -> None:
            while state["resend_seconds"] > 0:
                resend_button.disabled = True
                resend_button.text = f"Resend in {state['resend_seconds']}s"
                page.update()
                await asyncio.sleep(1)
                state["resend_seconds"] -= 1
            resend_button.disabled = False
            resend_button.text = "Resend code"
            page.update()

        def otp_button_content(label: str, *, loading: bool = False) -> ft.Control:
            controls: list[ft.Control] = []
            if loading:
                controls.append(ft.ProgressRing(width=17, height=17, stroke_width=2, color=WHITE))
            controls.append(ft.Text(label, color=WHITE, size=14, weight=ft.FontWeight.BOLD))
            if not loading:
                controls.append(ft.Icon(ft.Icons.CHECK_ROUNDED, color=WHITE, size=19))
            return ft.Row(
                controls,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            )

        verify_button = ft.Button(
            content=otp_button_content("Verify email"),
            width=inner_width,
            height=52,
            on_click=on_verify,
            style=ft.ButtonStyle(
                bgcolor=PURPLE,
                color=WHITE,
                shape=ft.RoundedRectangleBorder(radius=14),
                elevation=0,
            ),
        )
        resend_button.on_click = on_resend
        otp_field.on_change = lambda e: clear_message()
        otp_field.on_submit = on_verify

        card_body = ft.Column(
            [
                ft.Container(
                    width=66,
                    height=66,
                    border_radius=21,
                    bgcolor=LAVENDER,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.MARK_EMAIL_READ_OUTLINED, color=PURPLE, size=32),
                ),
                ft.Text("CHECK YOUR INBOX", size=10, color=PURPLE, weight=ft.FontWeight.BOLD),
                ft.Text("Verify your email", size=25, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Text("We sent a verification code to", size=12, color=MUTED),
                ft.Text(email_display, size=13, color=PURPLE_DARK, weight=ft.FontWeight.BOLD),
                ft.Container(height=7),
                otp_field,
                error_area,
                verify_button,
                ft.Row(
                    [ft.Text("Didn't receive the code?", size=11, color=MUTED), resend_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                ft.Divider(height=1, color=BORDER),
                ft.TextButton(
                    "Use a different email",
                    on_click=lambda e: go(page, "/signup", step="form"),
                    style=ft.ButtonStyle(color=PURPLE_DARK),
                ),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        )
        card_title = "Verify your email"

    signup_card = ft.Container(
        width=card_width,
        height=None if compact else (510 if show_otp else 700),
        padding=28 if compact else 30,
        border_radius=26,
        bgcolor=WHITE,
        border=ft.Border.all(width=1, color=BORDER),
        shadow=ft.BoxShadow(
            blur_radius=28,
            spread_radius=0,
            color="#211B3612",
            offset=ft.Offset(0, 10),
        ),
        content=card_body,
    )

    if compact:
        top_brand = ft.Row(
            [
                _campuscare_logo(85, 85),
                ft.Column(
                    [
                        ft.Text(
                            "CampusCare",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=PURPLE_DARK,
                        ),
                        ft.Text(
                            "Student Community",
                            size=11,
                            color=MUTED,
                        ),
                        ft.Text(
                            "For Students & Staff",
                            size=10,
                            color=MUTED,
                        ),
                    ],
                    spacing=3,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )
        body = ft.Column(
            [top_brand, signup_card],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    else:
        body = ft.Row(
            [_brand_panel(), signup_card],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=25,
            expand=True,
        )

    return ft.Container(
        expand=True,
        padding=16,
        bgcolor=PAGE_BG,
        content=body,
    )