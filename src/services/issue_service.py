"""ISSUE SERVICE - calls to the issue endpoints via core/api_client.py.

TODO (agree endpoint names with the backend owner)
  [ ] list_categories()             GET  /categories/
  [ ] list_buildings()              GET  /buildings/
  [ ] match_building(lat, lng)      GET  /buildings/match/?lat=&lng=
  [ ] create_issue(payload)         POST /issues/              (include an idempotency key)
  [ ] upload_photo(issue_id, bytes) POST /issues/{id}/attachments/
  [ ] list_my_issues(status=None)   GET  /issues/mine/
  [ ] get_issue(issue_id)           GET  /issues/{id}/         (includes timeline + allowed transitions)
  [ ] add_comment(issue_id, text)   POST /issues/{id}/comments/
  [ ] submit_feedback(issue_id, rating, text)   POST /issues/{id}/feedback/
  [ ] reopen(issue_id, reason)      POST /issues/{id}/reopen/
"""
