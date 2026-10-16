"""LOGIN  |  side: shared (student + staff)  |  route: /login  |  navbar: hidden
UI TODO
[=] App logo + title "CampusCare"
[=] TextField  "Institute email"   (email keyboard, inline error if not @config.ALLOWED_EMAIL_DOMAIN)
[=] TextField  "Password"          (password=True, can_reveal_password=True)
[=] Error text area (wrong credentials / unverified email / server unreachable)
[=] Button     "Log in"            (disabled + spinner while the request runs)
[=] TextButton "New student? Sign up"  -> go(page, "/signup")
[ ] (optional, later) "Forgot password?"
Behaviour TODO
[ ] Validate with validators (create core/validators.py when needed) before calling the API
[ ] auth_service.login(email, password) -> {access, refresh, user{name,email,role}}
[ ] session.set_session(...) then reset(page, home_path())   (role decides student vs staff home)
[ ] Unverified email -> go(page, "/signup", step="otp", email=...)
[ ] Network error vs wrong password must show different messages
"""
import inspect
import re
import flet as ft
import config
from core import session
from core.router import go, reset, home_path
from services import auth_service
# ---------------------------------------------------------------------------
# Visual system — light lavender, white surfaces, and a vivid purple accent.
# ---------------------------------------------------------------------------
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
  """Return the configured institute domain without a leading @."""
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


def _exception_details(exc: Exception) -> tuple[str, str]:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    detail = str(exc)

    if response is not None:
        try:
            body = response.json()
            if isinstance(body, dict):
                raw_detail = body.get("detail", body.get("message", body.get("error")))
                if raw_detail:
                    detail = str(raw_detail)
        except (ValueError, TypeError):
            detail = response.text or detail

    lowered = detail.lower()

    if any(value in lowered for value in ("unverified", "not verified", "email verification required")):
        return "unverified", "Verify your institute email before signing in."

    if any(
        value in lowered
        for value in ("email not confirmed", "email not verified", "not verified")
    ):
        return "unverified", "Your email is not verified. Please verify your email using the link sent to your inbox."

    if status == 401:
        return "credentials", "Invalid email or password. Your account may not exist."

    if status == 401:
        return "credentials", "That email and password combination doesn't look right."

    if status in (400, 422):
        return "validation", detail

    name = type(exc).__name__.lower()

    if any(value in name for value in ("timeout", "connecterror", "networkerror")):
        return "network", "We couldn't reach CampusCare. Check your connection and try again."

    return "generic", detail or "We couldn't sign you in right now. Please try again."


def view(page: ft.Page, **params) -> ft.Control:
  """Render the shared student/staff login screen for route ``/login``."""
  viewport_width = getattr(page, "width", None)
  compact = viewport_width is None or viewport_width < 1020
  card_width = max(240, min(440, int(viewport_width or 390) - 24))
  card_padding = 16 if (viewport_width or 390) < 480 else 28
  inner_width = max(200, card_width - (card_padding * 2))
  state = {"loading": False}
  email_field = ft.TextField(
      label="Institute email",
      hint_text=f"you@{_allowed_domain()}" if _allowed_domain() else "you@institute.edu",
      width=inner_width,
      keyboard_type=ft.KeyboardType.EMAIL,
      prefix_icon=ft.Icons.MAIL_OUTLINE_ROUNDED,
      text_style=ft.TextStyle(color=TEXT, size=14),
      label_style=ft.TextStyle(color=MUTED, size=13),
      hint_style=ft.TextStyle(color="#AAA5BC", size=13),
      cursor_color=PURPLE,
      border_color=BORDER,
      focused_border_color=PURPLE,
      error_style=ft.TextStyle(color=ERROR, size=11),
      border_radius=13,
      content_padding=16,
      on_change=None,  # assigned below after the error area is created
      value=params.get("email", ""),
  )
  password_field = ft.TextField(
      label="Password",
      hint_text="Enter your password",
      width=inner_width,
      password=True,
      can_reveal_password=True,
      prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
      text_style=ft.TextStyle(color=TEXT, size=14),
      label_style=ft.TextStyle(color=MUTED, size=13),
      hint_style=ft.TextStyle(color="#AAA5BC", size=13),
      cursor_color=PURPLE,
      border_color=BORDER,
      focused_border_color=PURPLE,
      error_style=ft.TextStyle(color=ERROR, size=11),
      border_radius=13,
      content_padding=16,
      on_submit=None,  # assigned below after the login handler is created
  )
  error_area = ft.Container(
      visible=False,
      width=inner_width,
      padding=12,
      border_radius=12,
      bgcolor=ERROR_BG,
  )
  def show_error(message: str, *, kind: str = "generic") -> None:
      icon = ft.Icons.WIFI_OFF_ROUNDED if kind == "network" else ft.Icons.ERROR_OUTLINE_ROUNDED
      error_area.bgcolor = SUCCESS_BG if kind == "unverified" else ERROR_BG
      error_color = PURPLE_DARK if kind == "unverified" else ERROR
      error_area.content = ft.Row(
          [
              ft.Icon(icon, color=error_color, size=19),
              ft.Text(message, color=error_color, size=12, expand=True),
          ],
          spacing=9,
          vertical_alignment=ft.CrossAxisAlignment.START,
      )
      error_area.visible = True
  def clear_error() -> None:
      error_area.visible = False
      error_area.content = None
  def show_notice(message: str) -> None:
    error_area.bgcolor = SUCCESS_BG
    error_area.content = ft.Row(
        [
            ft.Icon(
                ft.Icons.MARK_EMAIL_READ_OUTLINED,
                color=PURPLE_DARK,
                size=19,
            ),
            ft.Text(
                message,
                color=PURPLE_DARK,
                size=12,
                expand=True,
            ),
        ],
        spacing=9,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
    error_area.visible = True
  def on_email_change(e) -> None:
      value = email_field.value or ""
      # Avoid showing an error before the user has typed enough to form an address.
    #   email_field.error_text = _email_error(value) if "@" in value and "." in value.rsplit("@", 1)[-1] else None
      if error_area.visible:
          clear_error()
      page.update()
  def on_password_change(e) -> None:
    #   if password_field.error_text and password_field.value:
    #       password_field.error_text = None
      if error_area.visible:
          clear_error()
      page.update()
  email_field.on_change = on_email_change
  password_field.on_change = on_password_change
  def dev_skip(e) -> None:
      session.set_session(
          "dev",
          "dev",
          {
              "name": "Dev Student",
              "email": f"dev@{_allowed_domain() or 'example.edu'}",
              "role": config.ROLE_STUDENT,
          },
      )
      reset(page, home_path())
  def make_login_button_content(loading: bool) -> ft.Control:
      if loading:
          return ft.Row(
              [
                  ft.ProgressRing(width=17, height=17, stroke_width=2, color=WHITE),
                  ft.Text("Signing in...", color=WHITE, size=15, weight=ft.FontWeight.BOLD),
              ],
              alignment=ft.MainAxisAlignment.CENTER,
              vertical_alignment=ft.CrossAxisAlignment.CENTER,
              spacing=11,
          )
      return ft.Row(
          [
              ft.Text("Log in", color=WHITE, size=15, weight=ft.FontWeight.BOLD),
              ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, color=WHITE, size=19),
          ],
          alignment=ft.MainAxisAlignment.CENTER,
          vertical_alignment=ft.CrossAxisAlignment.CENTER,
          spacing=10,
      )
  login_button = ft.Button(
      content=make_login_button_content(False),
      width=inner_width,
      height=54,
      on_click=None,  # assigned after on_login is defined
      style=ft.ButtonStyle(
          bgcolor=PURPLE,
          color=WHITE,
          shape=ft.RoundedRectangleBorder(radius=14),
          elevation=0,
      ),
  )
  async def on_login(e) -> None:
      if state["loading"]:
          return
      email = (email_field.value or "").strip()
      password = password_field.value or ""
      email_err = _email_error(email, required=True)
      if email_err:
            email_err = email_err.msg if hasattr(email_err, "msg") else email_err
      password_err = "Enter your password." if not password else None
      clear_error()
      if email_err or password_err:
          show_error(email_err or password_err, kind="validation")
          page.update()
          return
      state["loading"] = True
      login_button.disabled = True
      login_button.content = make_login_button_content(True)
      page.update()
      try:
          login_fn = getattr(auth_service, "login", None)
          if not callable(login_fn):
              show_error(
                  "Sign-in is not connected to the server yet. The login UI is ready, but the auth service still needs to be implemented.",
                  kind="generic",
              )
              print("auth_service.login is not callable. Check that the auth_service module is implemented correctly.")
              return
          print("Calling auth_service.login with email:", email)
          result = login_fn(email, password)
          print("auth_service.login returned:", result)
          if inspect.isawaitable(result):
              result = await result
          print("Login result:", result)
          if not isinstance(result, dict):
              show_error("The server returned an unexpected response. Please try again.")
              return
          # Handle service implementations that return an error payload instead of raising.
          response_message = " ".join(
              str(result.get(key, "")) for key in ("detail", "message", "error", "code")
          ).lower()
          is_unverified = result.get("verified") is False or any(
              token in response_message for token in ("unverified", "not verified", "verify your email", "email verification required")
          )
          if is_unverified:
            show_error("Your email is not verified. Please verify your email using the link sent to your inbox.")
            return
          if result.get("success") is False or result.get("error"):
              status = result.get("status_code", result.get("status"))
              if status == 401 or any(token in response_message for token in ("invalid credentials", "incorrect password", "wrong password")):
                  show_error("That email and password combination doesn't look right.", kind="credentials")
              elif any(token in response_message for token in ("network", "unreachable", "timeout", "connection")):
                  show_error("We couldn't reach CampusCare. Check your connection and try again.", kind="network")
              else:
                  show_error(str(result.get("detail") or result.get("message") or "We couldn't sign you in right now."))
              return
          user = result.get("user")
          access = result.get("access")
          refresh = result.get("refresh", "")
          if not access or not isinstance(user, dict):
              show_error("The server response is missing account information. Please try again.")
              return
          session.set_session(str(access), str(refresh), user)
          # The current router has a single home route; role-specific homes can be
          # substituted here when the staff routes are registered.
          reset(page, home_path())
      except Exception as exc:
        kind, message = _exception_details(exc)
        show_error(message, kind=kind)
      finally:
        state["loading"] = False
        login_button.disabled = False
        login_button.content = make_login_button_content(False)
        page.update()
  login_button.on_click = on_login
  password_field.on_submit = on_login
  if params.get("notice"):
    show_notice(str(params["notice"]))
  # Use the supplied CampusCare logo asset instead of the old heart icon
  # and text-only wordmark. Keep the source relative to Flet's assets_dir.
  def campuscare_logo(width: int = 150, height: int = 150) -> ft.Image:
      return ft.Image(src="campuscare_logo.png", width=width, height=height)
  logo_lockup = ft.Column(
      [campuscare_logo(150, 150), ft.Text("Your campus, cared for.", size=11, color=MUTED)],
      spacing=0,
      horizontal_alignment=ft.CrossAxisAlignment.CENTER,
      tight=True,
  )
  def feature_row(icon, title, description):
      return ft.Row(
          [
              ft.Container(
                  width=42,
                  height=42,
                  border_radius=13,
                  bgcolor="#8976FA",
                  alignment=ft.Alignment(0, 0),
                  content=ft.Icon(icon, color=WHITE, size=21),
              ),
              ft.Column(
                  [
                      ft.Text(title, size=14, color=WHITE, weight=ft.FontWeight.BOLD),
                      ft.Text(description, size=12, color="#E3DEFF"),
                  ],
                  spacing=3,
                  tight=True,
                  expand=True,
              ),
          ],
          spacing=12,
          vertical_alignment=ft.CrossAxisAlignment.CENTER,
      )
  brand_panel = ft.Container(
      width=430,
      padding=24,
      border_radius=28,
      bgcolor=PURPLE_DARK,
      content=ft.Column(
          [
              # Logo and text side by side
              ft.Row(
                  [
                      campuscare_logo(125, 125),
                      ft.Column(
                          [
                              ft.Text(
                                  "CampusCare",
                                  size=25,
                                  color=WHITE,
                                  weight=ft.FontWeight.BOLD,
                              ),
                              ft.Text(
                                  "Student Community",
                                  size=13,
                                  color="#E3DEFF",
                              ),
                              ft.Text(
                                  "For Students & Staff",
                                  size=12,
                                  color="#C6BDFF",
                              ),
                          ],
                          spacing=5,
                          alignment=ft.MainAxisAlignment.CENTER,
                          expand=True,
                      ),
                  ],
                  spacing=12,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER,
              ),
              ft.Divider(color="#51418F", height=24),
              ft.Text(
                  "Speak with Confidence",
                  size=27,
                  weight=ft.FontWeight.BOLD,
                  color=WHITE,
              ),
              ft.Text(
                  "Your voice matters. Together, we make "
                  "campus life better.",
                  size=13,
                  color="#E3DEFF",
              ),
              ft.Container(height=8),
              ft.Container(
                  padding=16,
                  border_radius=18,
                  bgcolor="#493987",
                  content=ft.Column(
                      [
                          feature_row(
                              ft.Icons.FORUM_OUTLINED,
                              "Speak up with confidence",
                              "Report campus issues in a few steps.",
                          ),
                          ft.Container(height=12),
                          feature_row(
                              ft.Icons.FAVORITE_BORDER_ROUNDED,
                              "Support that follows through",
                              "Stay informed as your issue progresses.",
                          ),
                      ],
                      spacing=0,
                  ),
              ),
              ft.Container(expand=True),
              ft.Row(
                  [
                      ft.Icon(
                          ft.Icons.SHIELD_OUTLINED,
                          size=17,
                          color="#C6BDFF",
                      ),
                      ft.Text(
                          "A safer, more caring campus community",
                          size=11,
                          color="#E3DEFF",
                      ),
                  ],
                  spacing=8,
              ),
          ],
          spacing=10,
          expand=True,
          scroll=ft.ScrollMode.AUTO,
      ),
  )
  login_card = ft.Container(
      width=card_width,
      padding=card_padding,
      border_radius=26,
      bgcolor=WHITE,
      border=ft.Border.all(width=1, color=BORDER),
      shadow=ft.BoxShadow(
          blur_radius=28,
          spread_radius=0,
          color="#211B3612",
          offset=ft.Offset(0, 10),
      ),
      content=ft.Column(
          [
              ft.Text("WELCOME BACK", size=11, color=PURPLE, weight=ft.FontWeight.BOLD),
              ft.Text("Log in to CampusCare", size=25, color=TEXT, weight=ft.FontWeight.BOLD),
              ft.Text("Use your institute account to continue.", size=13, color=MUTED),
              ft.Container(height=3),
              email_field,
              password_field,
              error_area,
              login_button,
              ft.Row(
                  [
                      ft.Text("New student?", size=12, color=MUTED),
                      ft.TextButton(
                          "Sign up",
                          on_click=lambda e: go(page, "/signup"),
                          style=ft.ButtonStyle(color=PURPLE),
                      ),
                  ],
                  alignment=ft.MainAxisAlignment.CENTER,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER,
                  spacing=3,
              ),
              ft.Divider(height=1, color=BORDER),
              ft.Row(
                  [
                      ft.Icon(ft.Icons.SHIELD_OUTLINED, size=15, color=PURPLE_MID),
                      ft.Text("Your institute account keeps access campus-only.", size=10, color=MUTED),
                  ],
                  alignment=ft.MainAxisAlignment.CENTER,
                  spacing=6,
              ),
          ],
          spacing=15,
          horizontal_alignment=ft.CrossAxisAlignment.CENTER,
          tight=True,
      ),
  )
  compact_brand = ft.Row(
      [
          campuscare_logo(72, 72),
          ft.Column(
              [
                  ft.Text("CampusCare", size=22, color=TEXT, weight=ft.FontWeight.BOLD),
                  ft.Text("For Students & Staff", size=12, color=MUTED),
              ],
              spacing=2,
              alignment=ft.MainAxisAlignment.CENTER,
          ),
      ],
      alignment=ft.MainAxisAlignment.CENTER,
      vertical_alignment=ft.CrossAxisAlignment.CENTER,
      spacing=10,
  )
  body = ft.Column(
      [compact_brand, login_card],
      alignment=ft.MainAxisAlignment.START,
      horizontal_alignment=ft.CrossAxisAlignment.CENTER,
      spacing=14,
      scroll=ft.ScrollMode.AUTO,
      expand=True,
  )

  # Reflow the form when the browser or desktop window is resized.
  def on_resize(e):
      width = int(getattr(page, "width", None) or 390)
      card_w = max(240, min(440, width - 24))
      pad = 16 if width < 480 else 28
      field_w = max(200, card_w - (pad * 2))
      old_inner_width = getattr(email_field, "width", field_w)
      login_card.width = card_w
      login_card.padding = pad

      def resize_children(control):
          if control is None:
              return
          if isinstance(control, (list, tuple)):
              for child in control:
                  resize_children(child)
              return
          if hasattr(control, "width") and getattr(control, "width", None) == old_inner_width:
              try:
                  control.width = field_w
              except Exception:
                  pass
          for attr in ("content", "controls", "leading", "trailing"):
              try:
                  child = getattr(control, attr, None)
              except Exception:
                  child = None
              if child is not None and child is not control:
                  resize_children(child)

      resize_children(login_card.content)
      email_field.width = field_w
      password_field.width = field_w
      error_area.width = field_w
      login_button.width = field_w
      page.update()

  page.on_resize = on_resize

  return ft.Container(
      expand=True,
      padding=12,
      bgcolor=PAGE_BG,
      content=ft.Column(
          [body],
          expand=True,
          scroll=ft.ScrollMode.AUTO,
          horizontal_alignment=ft.CrossAxisAlignment.CENTER,
      ),
  )