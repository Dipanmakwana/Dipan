"""Bottom navigation bar (student tabs).

TABS drives both the bar and the router: (route, label, icon, selected icon).
To add a tab: add a row here and register the route in core/router.py.

TODO (later): staff tab set (Inbox, Map, Profile) chosen by session.role().
"""
import flet as ft

TABS = [
    ("/home", "Home", ft.Icons.HOME_OUTLINED, ft.Icons.HOME),
    ("/report", "Report", ft.Icons.ADD_CIRCLE_OUTLINE, ft.Icons.ADD_CIRCLE),
    ("/issues", "My issues", ft.Icons.LIST_ALT_OUTLINED, ft.Icons.LIST_ALT),
    ("/profile", "Profile", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON),
]

TAB_PATHS = [t[0] for t in TABS]


def build_bottom_nav(on_select) -> ft.NavigationBar:
    """`on_select(path)` is called when the user taps a tab."""
    return ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=icon, selected_icon=selected, label=label)
            for _, label, icon, selected in TABS
        ],
        selected_index=0,
        visible=False,   # the router shows it only on tab screens
        on_change=lambda e: on_select(TAB_PATHS[e.control.selected_index]),
    )
