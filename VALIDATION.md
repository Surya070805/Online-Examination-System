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
| Functional test suite | Collection blocked on 2026-11-19: `Flask-SQLAlchemy` is not installed in the active Python environment. Install `requirements.txt` and rerun `pytest`. |

### Test run log

| Date | Python / dependency environment | Passed | Failed | Notes |
|---|---|---:|---:|---|
| 2026-11-19 | Active environment; Flask-SQLAlchemy missing | — | — | Pytest stopped at collection before running cases. |
| _Add each lab test run here_ | | | | |

## Release checklist

- [ ] All functional tests pass in the release environment.
- [ ] Requirements and traceability match the implemented behavior.
- [ ] `main` contains all accepted increments and has a clean working tree.
- [ ] `SECRET_KEY` is configured outside source control.
- [ ] HTTPS is configured for non-local deployment.
- [ ] SQLite database backup and administrator account provisioning are documented.
