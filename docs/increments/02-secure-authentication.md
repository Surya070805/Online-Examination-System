# Increment 2 — Secure authentication

## Goal

Protect candidate and administrator workflows with server-side identity and role checks (SRS FR-01 and FR-02).

## Delivered

- Registration stores a Werkzeug password hash; legacy plaintext accounts are upgraded after a successful login.
- Login establishes a server session with user ID and role; logout clears the session.
- Student and administrator routes use role checks, and attempt/result access checks ownership.
- Session cookies are HTTP-only and use SameSite=Lax.

## Acceptance cases

- `test_authentication_required`: anonymous candidate access redirects to sign-in.
- `test_registration_stores_a_password_hash`: registration does not persist the submitted secret in clear text.
- `test_invalid_password_does_not_create_session`: rejected credentials do not create an authenticated session.
- `test_student_cannot_open_admin_dashboard`: a candidate cannot use an administrator route.

## Review note

The app uses a development fallback secret to support local startup. Set a unique `SECRET_KEY` and use HTTPS for deployment; `SDLC.md` records this release condition.
