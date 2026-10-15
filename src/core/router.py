"""Router + app shell (content area + bottom navbar).

- Every screen module exposes:  def view(page, **params) -> ft.Control
- Navigate:  go(page, "/issue", id=42)      Back:  back(page)
- After login/logout use reset(page, path) to clear the back stack.
- Screens are imported lazily (see _resolve) because screens import `go` from here.
"""
import importlib

import flet as ft

from components.bottom_nav import TAB_PATHS, build_bottom_nav
from core import session

# path -> module containing view()
ROUTES = {
    "/login": "screens.auth.login",
    "/signup": "screens.auth.signup",
    "/home": "screens.student.home",
    "/report": "screens.student.report_issue",
    "/issues": "screens.student.my_issues",
    "/issue": "screens.shared.issue_detail",
    "/profile": "screens.shared.profile",
}

PUBLIC = {"/login", "/signup"}      # everything else requires login
# TODO (staff work): STAFF_ONLY routes + role check in _guard(), staff tab set in bottom_nav.

_shell: dict = {}                   # {"content": Container, "nav": NavigationBar}
_history: list = []                 # [(path, params), ...]


def init(page: ft.Page) -> None:
    """Build the shell once at startup: [ content area | bottom navbar ]."""
    content = ft.Container(expand=True)
    nav = build_bottom_nav(lambda path: go(page, path))
    _shell.update(content=content, nav=nav)
    page.controls.clear()
    page.add(ft.SafeArea(expand=True, content=ft.Column([content, nav], expand=True, spacing=0)))


def home_path() -> str:
    return "/home"                  # TODO: "/staff/inbox" for staff role


def _guard(path: str) -> str:
    if path in PUBLIC:
        return path
    if not session.is_logged_in():
        return "/login"
    return path


def _resolve(path: str):
    return importlib.import_module(ROUTES[path]).view


def _render(page: ft.Page, path: str, params: dict) -> None:
    _shell["content"].content = _resolve(path)(page, **params)
    nav = _shell["nav"]
    on_tab = path in TAB_PATHS
    nav.visible = on_tab
    if on_tab:
        nav.selected_index = TAB_PATHS.index(path)
    page.update()


def go(page: ft.Page, path: str, replace: bool = False, **params) -> None:
    path = _guard(path)
    if replace and _history:
        _history.pop()
    _history.append((path, params))
    _render(page, path, params)


def reset(page: ft.Page, path: str, **params) -> None:
    _history.clear()
    go(page, path, **params)


def back(page: ft.Page) -> None:
    if len(_history) > 1:
        _history.pop()
        path, params = _history[-1]
        _render(page, _guard(path), params)
