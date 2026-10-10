import flet as ft


def main(page: ft.Page):
    page.title = "Hello World"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.add(ft.Text("Hello, World!", size=32))


ft.run(main)