"""API CLIENT - the only place that does HTTP to the Django backend.

TODO
  [ ] async request(method, path, **kwargs) using httpx.AsyncClient(base_url=config.API_BASE_URL, timeout=config.REQUEST_TIMEOUT_S)
  [ ] Add "Authorization: Bearer <access>" from core/session.py
  [ ] On 401: call auth_service.refresh(), update the session, retry the request ONCE; if refresh fails -> clear session, go to /login
  [ ] Raise a clear ApiError(message, status) for HTTP errors; a separate NetworkError for unreachable server
  [ ] Multipart helper for photo uploads
"""
