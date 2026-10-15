"""LOGIN  |  side: shared (student + staff)  |  route: /login  |  navbar: hidden

UI TODO
  [ ] App logo + title "CampusCare"
  [ ] TextField  "Institute email"   (email keyboard, inline error if not @config.ALLOWED_EMAIL_DOMAIN)
  [ ] TextField  "Password"          (password=True, can_reveal_password=True)
  [ ] Error text area (wrong credentials / unverified email / server unreachable)
  [ ] Button     "Log in"            (disabled + spinner while the request runs)
  [ ] TextButton "New student? Sign up"  -> go(page, "/signup")
  [ ] (optional, later) "Forgot password?"

Behaviour TODO
  [ ] Validate with validators (create core/validators.py when needed) before calling the API
  [ ] auth_service.login(email, password) -> {access, refresh, user{name,email,role}}
  [ ] session.set_session(...) then reset(page, home_path())   (role decides student vs staff home)
  [ ] Unverified email -> go(page, "/signup", step="otp", email=...)
  [ ] Network error vs wrong password must show different messages
"""
import flet as ft

import config
from core import session
from core.router import go, reset, home_path


def view(page: ft.Page, **params) -> ft.Control:
    controls = [ft.Text("Login", size=22, weight=ft.FontWeight.BOLD), ft.Text("TODO: see docstring")]
    controls.append(ft.TextButton("Sign up", on_click=lambda e: go(page, "/signup")))

    if config.DEV_MODE:  # REMOVE once real login works
        def dev_skip(e):
            session.set_session("dev", "dev", {"name": "Dev Student", "email": f"dev@{config.ALLOWED_EMAIL_DOMAIN}", "role": config.ROLE_STUDENT})
            reset(page, home_path())
        controls.append(ft.Button("DEV: skip login", on_click=dev_skip))

    return ft.Container(padding=16, content=ft.Column(controls))
