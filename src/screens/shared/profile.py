"""PROFILE  |  side: shared  |  route: /profile  |  navbar tab 4

UI TODO
  [ ] Avatar circle with initials
  [ ] Name, institute email, roll number, hostel/building (read-only to start)
  [ ] Role badge (Student / Staff)
  [ ] (later) Edit profile (name, hostel) and Change password
  [ ] (later) Notification preferences switch
  [ ] App version text
  [ ] Button "Log out" with a confirm dialog
  [ ] No charts on this screen

Behaviour TODO
  [ ] Logout: auth_service.logout(refresh_token) -> session.clear() (also remove stored token) -> reset(page, "/login")
"""
import flet as ft

from core import session
from core.router import reset


def view(page: ft.Page, **params) -> ft.Control:
    def on_logout(e):  # TODO: confirm dialog + auth_service.logout + remove stored token
        session.clear()
        reset(page, "/login")

    u = session.user()
    return ft.Container(
        padding=16,
        content=ft.Column(
            [
                ft.Text("Profile", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(f"{u.get('name', '-')}  |  {u.get('email', '-')}"),
                ft.Text("TODO: see docstring"),
                ft.Button("Log out", on_click=on_logout),
            ]
        ),
    )
