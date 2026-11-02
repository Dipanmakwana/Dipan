"""Login session (tokens + current user).

Access token: memory only. Refresh token: persisted so the user stays logged in.

TODO (auth owner):
  - restore(): read the stored refresh token -> POST /auth/token/refresh -> GET /me.
      * token rejected by server -> clear() and show login
      * no network -> do NOT log out; show "can't connect" + retry
  - set_session(): also persist the refresh token + basic user info.
      Recent Flet:  await page.shared_preferences.set("campuscare.refresh", token)
      Older Flet:   page.client_storage.set(...)   (check the docs for your pinned version)
      Use a "campuscare." key prefix; storage is shared by all Flet apps and not encrypted.
  - clear(): remove stored values and blacklist the refresh token on the server.
"""

import config

_state = {"access": None, "refresh": None, "user": None}


async def restore(page) -> None:
    """Called once at startup. Currently a no-op (nothing persisted yet)."""
    return None


def set_session(access: str, refresh: str, user: dict) -> None:
    _state.update(access=access, refresh=refresh, user=user)


def update_user(fields: dict) -> None:
    """Merge fresh profile fields (e.g. from GET /auth/me) into the logged-in user."""
    if _state["user"] is not None:
        _state["user"] = {**_state["user"], **{k: v for k, v in fields.items() if v is not None}}


def is_dev_session() -> bool:
    """True for the DEV_MODE "Skip as ..." login (fake token, the API will reject it)."""
    return _state["access"] == "dev"


def clear() -> None:
    _state.update(access=None, refresh=None, user=None)


def is_logged_in() -> bool:
    return _state["user"] is not None


def access_token():
    return _state["access"]


def refresh_token():
    return _state["refresh"]


def user() -> dict:
    return _state["user"] or {}


def role():
    return user().get("role")


def is_staff() -> bool:
    """True for PHO/admin users (see config.STAFF_ROLES)."""
    return str(role() or "").strip().lower() in config.STAFF_ROLES
