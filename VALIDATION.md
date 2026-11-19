# Verification and release record

## Functional test cases

| ID | Scenario | Expected result | Automated case |
|---|---|---|---|
| TC-01 | Anonymous user opens exam list | Request redirects to sign-in | `test_authentication_required` |
| TC-02 | Candidate registers | Password is persisted as a one-way hash | `test_registration_stores_a_password_hash` |
| TC-03 | User submits an incorrect password | Sign-in fails and no session is created | `test_invalid_password_does_not_create_session` |
| TC-04 | Candidate opens admin dashboard | Request is forbidden | `test_student_cannot_open_admin_dashboard` |
| TC-05 | Candidate starts an exam twice | Only one attempt exists | `test_exam_attempt_is_created_only_once` |
| TC-06 | Candidate submits mixed correct/incorrect answers and a forged score | Server calculates the score from the answer key | `test_start_once_and_auto_evaluate` |
| TC-07 | Candidate submits no answers | Score is zero | `test_unanswered_questions_score_zero` |
| TC-08 | Candidate posts again after submission | Persisted result and answers remain unchanged | `test_submitted_result_is_immutable` |
| TC-09 | Candidate submits after expiry | Attempt closes with zero and late answers are ignored | `test_expired_attempt_is_submitted_without_late_answers` |
| TC-10 | Another candidate requests an attempt result | Request is denied | `test_attempt_owner_enforced` |

## Local verification record

| Check | Result |
|---|---|
| Python syntax compilation | Passed on 2026-11-19 with `python -m compileall -q app.py controllers.py models.py tests` |
| Functional test suite | 10 passed on 2026-11-19 with the project-local `.venv`; one app-factory issue was fixed during the run. |

### Test run log

| Date | Python / dependency environment | Passed | Failed | Notes |
|---|---|---:|---:|---|
| 2026-11-19 | Project `.venv`; Python 3.13, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, pytest 8.4.2 | 10 | 0 | `python -m compileall -q app.py controllers.py models.py tests` and `python -m pytest -q` both passed. |

## Setup workflow smoke check

On 2026-11-19, created an administrator using a generated password, seeded the demo exam, confirmed administrator login and dashboard returned HTTP 200, confirmed the student exam list returned HTTP 200 with the demo exam, and reran the seed without duplication.

## Release checklist

- [ ] All functional tests pass in the release environment.
- [ ] Requirements and traceability match the implemented behavior.
- [ ] `main` contains all accepted increments and has a clean working tree.
- [ ] `SECRET_KEY` is configured outside source control.
- [ ] HTTPS is configured for non-local deployment.
- [ ] SQLite database backup and administrator account provisioning are documented.
