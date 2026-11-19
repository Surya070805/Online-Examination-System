# Increment plan and traceability

Each increment adds value to the previous one. The existing quiz application is the baseline; the increments below evolve it into an online examination system.

| Increment | Branch | Delivered capability | Acceptance evidence |
|---|---|---|---|
| 0 — Baseline | `main` | Existing Quiz Master project plus the online exam implementation brought into this repository | Application source and initial functional tests are present |
| 1 — Requirements and design | `increment/01-requirements-planning` | SRS, lifecycle, scope, system boundaries, and acceptance goals | Stakeholder can trace system scope and acceptance criteria in `SRS.md` |
| 2 — Secure identity | `increment/02-secure-authentication` | Hashed passwords, server sessions, role and ownership guards, logout | Anonymous access is denied; credentials are not stored in clear text |
| 3 — Exam delivery | `increment/03-exam-delivery` | One attempt per student, server-started timer, exam interface | A student can start once; a second start is rejected; time limit is server checked |
| 4 — Evaluation and results | `increment/04-automated-evaluation` | Server-side answer checking and persisted result display | Correct, incorrect, unanswered, and forged score inputs yield expected totals |
| 5 — Verification and release | `increment/05-validation-release` | Functional test suite, traceability, run instructions, release checklist | Tests pass; clean `main` can be started from the documented setup |

## Requirement-to-test map

| Requirement | Test/evidence |
|---|---|
| FR-01 Authentication | `test_authentication_required`; login and registration cases |
| FR-02 Authorization | `test_attempt_owner_enforced` |
| FR-03 Exam listing | exam-list route and template review |
| FR-04 Single attempt | `test_start_once_and_auto_evaluate` |
| FR-05 Evaluation | `test_start_once_and_auto_evaluate` |
| FR-06 Results | result route and persisted attempt assertions |
| FR-07 Time limit | expired-attempt functional test |
| FR-08 Content management | existing administrator subject, chapter, quiz, and question workflows |

## Definition of done for an increment

1. The increment's scope is stated and linked to SRS requirement IDs.
2. Code and documentation are committed on its branch.
3. Functional cases cover the changed behavior and relevant rejection paths.
4. Syntax and functional checks pass, or a known blocker is recorded.
5. The increment is merged to `main` and `main` remains the integrated project state.
