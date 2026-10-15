"""AUTH SERVICE - calls to the auth endpoints via core/api_client.py.

TODO (agree endpoint names with the backend owner)
  [ ] login(email, password)        POST /auth/login/          -> {access, refresh, user}
  [ ] signup(name, email, password, roll_no, building_id)  POST /auth/signup/   (sends OTP email)
  [ ] verify_otp(email, code)       POST /auth/verify-otp/     -> {access, refresh, user}
  [ ] resend_otp(email)             POST /auth/resend-otp/
  [ ] refresh(refresh_token)        POST /auth/token/refresh/
  [ ] logout(refresh_token)         POST /auth/logout/         (blacklists the refresh token)
  [ ] me()                          GET  /me/
"""
