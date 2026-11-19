# Software Requirements Specification — Online Examination System

## 1. Purpose and scope
This document specifies the extension of Quiz Master into a browser-based online examination system. Administrators maintain quizzes and questions; registered students take timed examinations and receive automatically computed results. The current implementation uses Flask, Flask-SQLAlchemy, and SQLite.

## 2. Users and assumptions
- **Administrator:** authenticates to manage examination content and review results.
- **Student:** registers, authenticates, takes an available examination, and views their result.
- An examination consists of multiple-choice questions with one correct option and one point per correct answer.
- One attempt per student per examination is enforced. An exam timer is based on the server-recorded start time.

## 3. Functional requirements
- **FR-01 Authentication:** allow registration and sign-in; store password hashes; use a server session and provide sign-out.
- **FR-02 Authorization:** restrict student attempts and results to their owner; reject anonymous access and unauthorized roles.
- **FR-03 Exam listing:** show examination title, question count, and time limit.
- **FR-04 Attempt lifecycle:** create one attempt per student/exam, record server start time, prevent repeat attempts, and accept a submission once.
- **FR-05 Evaluation:** compare submitted option indexes to the stored answer key on the server; unanswered or invalid choices score zero.
- **FR-06 Results:** persist score, total questions, status, and submission time; show the result after submission.
- **FR-07 Time limit:** reject submissions after the server-side deadline; client countdown is a usability aid only.
- **FR-08 Content management:** administrators create and maintain subjects, chapters, exams, and questions.

## 4. Non-functional requirements
- Passwords must be stored using a one-way password hashing function.
- Authorization decisions and scoring must be performed server-side.
- Session cookies must be HTTP-only and use SameSite=Lax; production deployment must set a strong secret key and HTTPS/Secure cookies.
- Inputs must be validated and rendered using auto-escaping templates.
- The system should retain existing quiz records when its database is upgraded.

## 5. Data and interfaces
The existing user, admin, subject, chapter, quiz, question, and score entities are retained. `exam_attempt` stores ownership, timestamps, status, score, and total; `answer_record` stores one selected option and correctness value per question. Student interfaces are `/exams`, `POST /exam/<quiz_id>/start`, `/exam/attempt/<attempt_id>`, and `/exam/result/<attempt_id>`.

## 6. Acceptance criteria
An unauthenticated or wrong-owner request cannot view or submit an attempt; a student's second start request is refused; forged scores are ignored; valid, invalid, and unanswered choices produce the correct aggregate; repeated submission cannot change the stored result; and server expiry prevents late scoring.

## 7. Limitations
The current app uses a single SQLite database and does not provide proctoring, essay grading, randomized question banks, or multiple attempts. Deployments beyond a trusted development environment require HTTPS, a managed secret, database backups, and operational monitoring.
