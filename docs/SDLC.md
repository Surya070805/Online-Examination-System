# SDLC plan

This lab project follows a lightweight, iterative SDLC. The current Quiz Master application is the starting baseline; each increment adds a usable, reviewable slice of the online examination system.

## Lifecycle

1. **Planning:** define the problem, users, scope, risks, and acceptance goals.
2. **Requirements analysis:** capture functional and quality requirements in [SRS.md](SRS.md); review the requirements with the instructor or project stakeholder.
3. **Design:** describe the Flask/SQLite architecture, data entities, access rules, and exam lifecycle before coding each increment.
4. **Implementation:** create a short-lived branch for one increment, implement the slice, and update its tests and documentation.
5. **Verification:** run automated functional tests, review security boundaries, and record outcomes. Fix failures on the increment branch before merging.
6. **Integration and release:** merge accepted increments into `main`; `main` should remain runnable and represent the latest integrated release.
7. **Maintenance:** record defects and change requests, prioritize them, and deliver them as later increments.

## Branch and review workflow

- `main` is the integrated, releasable product.
- Use `increment/NN-short-name` for work and `fix/short-name` for defects.
- Keep a branch focused on one increment. Update the requirement traceability and tests with each change.
- Before merging, run `python -m compileall -q app.py controllers.py models.py tests` and `pytest` after installing `requirements.txt`.
- Merge only when the increment's acceptance checks pass; use the merge commit to show integration in the history.
- Tag a demonstrated release as `v0.N.0` after the corresponding increment is accepted.

## Roles for a solo lab project

The student acts as analyst, designer, developer, and tester. The instructor or nominated reviewer acts as stakeholder and reviews requirements, increment acceptance, and final demonstration.
