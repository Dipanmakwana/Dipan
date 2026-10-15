"""Entry point: build the shell (content + bottom navbar), restore the saved login, open the first screen.

Screens live in screens/ and are registered in core/router.py.
"""
import flet as ft

from core import router, session


async def main(page: ft.Page):
    page.title = "CampusCare"
    page.padding = 0

    router.init(page)
    await session.restore(page)     # TODO in session.py: read stored refresh token

    router.reset(page, router.home_path() if session.is_logged_in() else "/login")


ft.run(main)
