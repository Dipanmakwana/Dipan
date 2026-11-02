"""Bottom navigation bar (student tabs / staff tabs).

Tab sets: (route, label, icon, selected icon). The router calls apply_tabs() on every render with the
current role, so the bar switches automatically after login / logout.
To add a tab: add a row to the right list here and register the route in core/router.py.
"""
import flet as ft

STUDENT_TABS = [
    ("/home", "Home", ft.Icons.HOME_OUTLINED, ft.Icons.HOME),
    ("/report", "Report", ft.Icons.ADD_CIRCLE_OUTLINE, ft.Icons.ADD_CIRCLE),
    ("/issues", "My issues", ft.Icons.LIST_ALT_OUTLINED, ft.Icons.LIST_ALT),
    ("/profile", "Profile", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON),
]

STAFF_TABS = [
    ("/admin", "Dashboard", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD),
    ("/admin/complaints", "Complaints", ft.Icons.INBOX_OUTLINED, ft.Icons.INBOX),
    ("/admin/workers", "Workers", ft.Icons.ENGINEERING_OUTLINED, ft.Icons.ENGINEERING),
    ("/profile", "Profile", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON),
]


def tabs_for(is_staff: bool) -> list:
    return STAFF_TABS if is_staff else STUDENT_TABS


def build_bottom_nav(on_select) -> ft.NavigationBar:
    """`on_select(path)` is called when the user taps a tab.

    Starts with the student tabs (Flet needs >= 2 destinations); apply_tabs() swaps the set per role.
    """
    nav = ft.NavigationBar(
        destinations=[],
        selected_index=0,
        visible=False,   # the router shows it only on tab screens
        data=None,       # current tab paths, set by apply_tabs()
        on_change=lambda e: on_select(e.control.data[e.control.selected_index]),
    )
    apply_tabs(nav, is_staff=False)
    return nav


def apply_tabs(nav: ft.NavigationBar, is_staff: bool) -> list[str]:
    """Show the tab set for this role (rebuilds only when it changes). Returns the tab paths."""
    tabs = tabs_for(is_staff)
    paths = [t[0] for t in tabs]
    if nav.data != paths:
        nav.destinations = [
            ft.NavigationBarDestination(icon=icon, selected_icon=selected, label=label)
            for _, label, icon, selected in tabs
        ]
        nav.data = paths
    return paths
