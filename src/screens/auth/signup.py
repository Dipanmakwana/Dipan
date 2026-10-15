"""SIGNUP (+ email OTP verification)  |  side: student only  |  route: /signup  |  navbar: hidden
Staff accounts are NOT created here; the admin creates them in Django Admin.
This one file has two steps: step "form" and step "otp" (open the 2nd step with go(page, "/signup", step="otp", email=...)).

UI TODO - step 1 (form)
  [ ] TextField  "Full name"
  [ ] TextField  "Institute email"            (must end with @config.ALLOWED_EMAIL_DOMAIN)
  [ ] TextField  "Roll number"                (optional)
  [ ] Dropdown   "Hostel / building"          (optional; options from backend buildings endpoint)
  [ ] TextField  "Password"                   (min 8 chars, reveal toggle)
  [ ] TextField  "Confirm password"           (must match)
  [ ] Button     "Create account"             (spinner while loading)
  [ ] TextButton "Already registered? Log in" -> back(page)

UI TODO - step 2 (OTP)
  [ ] Text       "We sent a 6-digit code to <email>"
  [ ] TextField  "Verification code"          (numeric keyboard, config.OTP_LENGTH digits)
  [ ] Button     "Verify"
  [ ] TextButton "Resend code"                (30 s cooldown with countdown text)
  [ ] Error text (wrong / expired code, too many attempts)

Behaviour TODO
  [ ] Client-side validation, then auth_service.signup(...) -> server emails OTP
  [ ] auth_service.verify_otp(email, code) -> session.set_session(...) -> reset(page, home_path())
  [ ] Server must reject non-institute emails (client check is only for quick feedback)
"""
import flet as ft

from core.router import back


def view(page: ft.Page, step: str = "form", email: str = "", **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.Text("Sign up", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(f"TODO: see docstring (step={step})"),
                ft.TextButton("Back to login", on_click=lambda e: back(page)),
            ]
        ),
    )
