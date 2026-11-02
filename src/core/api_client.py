"""API CLIENT - the only place that does HTTP to the CampusCare backend (FastAPI, config.API_BASE_URL).

Usage (from services/*):
    data = await api_client.request("GET", "/issues/mine", params={"status": "open"})
    data = await api_client.request("POST", "/issues", data={...}, files=[("photos", (name, bytes, mime))])

- Adds "Authorization: Bearer <access>" from core/session.py when logged in.
- Returns the parsed JSON body ({} for empty responses).
- Server unreachable -> NetworkError.   HTTP error -> ApiError(message, status_code, body).

TODO
  [ ] On 401: call auth_service.refresh(), update the session, retry ONCE (backend has no refresh endpoint yet)
"""
from __future__ import annotations

import httpx

import config
from core import session


class NetworkError(ConnectionError):
    """Server unreachable (offline, wrong API_BASE_URL, timeout...)."""


class ApiError(Exception):
    """HTTP error with the status code and parsed response body."""

    def __init__(self, message: str, status_code: int | None = None, body: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body if isinstance(body, dict) else {}


def _parse_body(response: httpx.Response):
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"detail": response.text.strip()}


def _error_message(body, status: int) -> str:
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("message") or body.get("error")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list) and detail:          # FastAPI validation errors
            first = detail[0]
            if isinstance(first, dict) and first.get("msg"):
                return str(first["msg"])
    if status == 401:
        return "Your session has expired. Please log in again."
    return f"Request failed (HTTP {status})."


async def request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
    data: dict | None = None,
    files: list | None = None,
    auth: bool = True,
):
    """Perform one HTTP call against the backend and return the parsed JSON body."""
    headers = {}
    token = session.access_token() if auth else None
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if params:
        params = {k: v for k, v in params.items() if v is not None}
    if data:
        data = {k: v for k, v in data.items() if v is not None}

    url = f"{config.API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_S) as client:
            response = await client.request(
                method, url, headers=headers, params=params, json=json, data=data, files=files
            )
    except httpx.HTTPError as exc:
        raise NetworkError(f"Could not reach the server at {config.API_BASE_URL}: {exc}") from exc

    body = _parse_body(response)
    if response.status_code >= 400:
        raise ApiError(_error_message(body, response.status_code), response.status_code, body)
    return body
