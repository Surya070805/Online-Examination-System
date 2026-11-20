# Verification and release record

## Functional test cases

| ID | Scenario | Expected result | Automated case |
|---|---|---|---|
| TC-01 | Anonymous user opens exam list | Redirected to sign-in | `test_authentication_required` |
| TC-02 | Student registers | Password stored as a one-way hash | `test_registration_stores_a_password_hash` |
| TC-03 | Public registration submits teacher role | Account is still created as student | `test_public_registration_cannot_self_assign_faculty_role` |
| TC-04 | Student opens dean dashboard | Request is forbidden | `test_student_cannot_open_admin_dashboard` |
| TC-05 | Wrong password submitted | No authenticated session is created | `test_invalid_password_does_not_create_session` |
| TC-06 | Candidate forges a score in the exam form | Server calculates score from the answer key | `test_start_once_and_auto_evaluate` |
| TC-07 | Candidate starts the same exam twice | One attempt is retained | `test_exam_attempt_is_created_only_once` |
| TC-08 | Student refreshes an active attempt and later submits | Same attempt resumes; answer review is available to its owner | `test_student_can_resume_attempt_and_review_own_answers` |
| TC-09 | Candidate submits after expiry | Attempt closes with zero; late answers are ignored | `test_expired_attempt_is_submitted_without_late_answers` |
| TC-10 | Candidate submits no answers | Score is zero | `test_unanswered_questions_score_zero` |
| TC-11 | Candidate posts again after submission | Saved result and answers remain unchanged | `test_submitted_result_is_immutable` |
| TC-12 | Another candidate requests an attempt result | Request is denied | `test_attempt_owner_enforced` |
| TC-13 | Dean creates a subject, assigns faculty, and reviews an exam | Faculty builds a draft; only dean publication exposes it to students | `test_admin_assigns_subject_teacher_builds_draft_and_admin_publishes` |
| TC-14 | Faculty deletes an unused chapter | Its unused draft exams and questions are removed | `test_teacher_delete_chapter_removes_unused_exam_content` |
| TC-15 | Faculty deletes a draft question and exam | Both operations succeed while attempt history is protected | `test_teacher_can_delete_question_and_draft_exam` |
| TC-16 | Dean opens institutional Results | Results view loads with an empty state when appropriate | `test_admin_results_action_opens_results_page` |
| TC-17 | Faculty changes a question after exam attempts exist | Change is rejected | `test_teacher_cannot_change_question_bank_after_an_attempt` |
| TC-18 | Dean demotes an authenticated faculty account | Existing faculty session is revoked | `test_admin_role_demotion_revokes_existing_teacher_session` |
| TC-19 | Faculty requests unassigned subject content or results | Data and write operations are denied | `test_teacher_only_sees_and_manages_assigned_subjects` |
| TC-20 | Dean saves invalid and valid system settings | Invalid values are rejected; changes are audited | `test_admin_settings_are_validated_and_audited` |
| TC-21 | Institutional pass/fail report is viewed | Configured threshold determines pass and fail counts | `test_admin_pass_fail_metrics_follow_system_threshold` |
| TC-22 | Existing SQLite database starts after upgrade | Legacy data remains; role, publication, and governance schema is available | `test_existing_database_schema_migrates_roles_assignments_and_exam_publish_state` |

## Local verification record

| Check | Result |
|---|---|
| Python syntax parse | Passed on 2026-11-20 for app, config, controllers, database, models, and tests. |
| Functional suite | **22 passed, 0 failed** on 2026-11-20 using the project-local `.venv`. |
| Legacy schema migration | Passed within the functional suite against a pre-role SQLite database. |
| Test database safety | App startup used an in-memory database; each functional fixture used a separate temporary SQLite database. |

Reproduce the test run in PowerShell from the project folder:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## Release checklist

- [x] Three roles are enforced by the server and faculty data is scoped to assigned subjects.
- [x] Existing SQLite schemas migrate additively without dropping records.
- [x] Functional tests pass for authentication, examination delivery/evaluation, role boundaries, governance, and migration.
- [ ] Review the feature branch and merge the accepted increment to `main`.
- [ ] Set a deployment-specific `SECRET_KEY` and enable HTTPS before non-local deployment.
- [ ] Back up the SQLite database and provision the first administrator account.
