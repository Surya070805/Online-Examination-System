# Increment 3 — Timed examination delivery

## Goal

Allow an authenticated candidate to begin and complete a timed exam with one attempt (SRS FR-03, FR-04, and FR-07).

## Delivered

- Candidate exam list shows title, question count, and duration.
- Starting an exam creates a database attempt with a server timestamp.
- A unique `(quiz_id, user_id)` constraint prevents a second attempt.
- The exam page renders answer choices and a client countdown; the server independently enforces expiry.
- Attempt routes verify the current student owns the attempt.

## Acceptance cases

- `test_exam_attempt_is_created_only_once`: repeated start requests do not create a second attempt.
- `test_attempt_owner_enforced`: another user cannot read the result.
- `test_expired_attempt_is_submitted_without_late_answers`: a late post cannot receive points or change answers.

## Integration note

The timer shown in the browser is only a convenience. The stored start time and configured duration determine whether a submission is accepted.
