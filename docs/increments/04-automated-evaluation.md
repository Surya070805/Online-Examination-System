# Increment 4 — Automated evaluation and results

## Goal

Calculate and persist a candidate's score from the answer key, then make the result available to its owner (SRS FR-05 and FR-06).

## Delivered

- The server validates submitted option indexes and compares them with stored correct options.
- Unanswered and malformed choices receive zero points.
- The server ignores any client-supplied score.
- Score, total question count, completion time, and attempt status are persisted.
- A completed attempt cannot be resubmitted to alter the score.

## Acceptance cases

- `test_start_once_and_auto_evaluate`: correct and incorrect answers plus a forged score produce the server-calculated score.
- `test_unanswered_questions_score_zero`: an empty submission receives no points.
- `test_submitted_result_is_immutable`: a later post cannot change answers or the result.
- `test_expired_attempt_is_submitted_without_late_answers`: an expired attempt does not accept answers.
