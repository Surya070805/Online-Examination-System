# Software Requirements Specification — Online Examination System

## 1. Purpose and scope
This document specifies the extension of Quiz Master into a browser-based online examination system. Students take timed examinations and review their results; assigned faculty author courses and exams; deans/administrators govern accounts, assignments, schedules, settings, and institutional reports. The current implementation uses Flask, Flask-SQLAlchemy, and SQLite.

## 2. Users and assumptions
- **Student:** registers as a student, takes a published timed examination, and reviews their own score, answers, and attempt history.
- **Teacher / Faculty:** receives administrator approval and subject assignments; manages chapters, question banks, draft exams, and analytics only for assigned subjects.
- **Admin / Dean:** manages subject creation, faculty roles and subject assignments, exam publication, institutional reports, system settings, and audit logs. Administrators cannot author or change exam questions.
- An examination consists of multiple-choice questions with one correct option and one point per correct answer.
- One attempt per student per examination is enforced. An exam timer is based on the server-recorded start time.

## 3. Functional requirements
- **FR-01 Authentication:** allow student registration and sign-in; store password hashes; use a server session and provide sign-out. Faculty roles are granted by an administrator; admin credentials are provisioned outside public registration.
- **FR-02 Authorization:** restrict student attempts and results to their owner; reject anonymous access and unauthorized roles.
- **FR-03 Exam listing:** show examination title, question count, and time limit.
- **FR-04 Attempt lifecycle:** create one attempt per student/exam, record server start time, prevent repeat attempts, and accept a submission once.
- **FR-05 Evaluation:** compare submitted option indexes to the stored answer key on the server; unanswered or invalid choices score zero.
- **FR-06 Results:** persist score, total questions, status, and submission time; show the result after submission.
- **FR-07 Time limit:** reject submissions after the server-side deadline; client countdown is a usability aid only.
- **FR-08 Content management:** administrators create subjects and govern curriculum; faculty manage chapters, exams, and questions for assigned subjects.
- **FR-09 Three-tier authorization:** enforce student, teacher, and admin permissions on every protected route; registration can create students only; role changes take effect after re-authentication.
- **FR-10 Subject assignment:** administrators assign existing subjects to faculty; teachers can author content only within assigned subjects.
- **FR-11 Exam approval:** teacher-created exams remain drafts until an administrator reviews and publishes them; students can start published exams only.
- **FR-12 Institutional analytics:** teachers see results and question response difficulty only for assigned subjects; administrators see institutional pass/fail counts using the configured pass threshold.
- **FR-13 Governance:** administrators configure default exam duration and passing threshold and can inspect audit records for role, assignment, content, publication, and setting changes.

## 4. Non-functional requirements
- Passwords must be stored using a one-way password hashing function.
- Authorization decisions and scoring must be performed server-side.
- Session cookies must be HTTP-only and use SameSite=Lax; production deployment must set a strong secret key and HTTPS/Secure cookies.
- Inputs must be validated and rendered using auto-escaping templates.
- The system should retain existing quiz records when its database is upgraded.

## 5. Data and interfaces
The existing user, admin, subject, chapter, quiz, question, and score entities are retained. `user.role` stores student/teacher roles; admins remain in the separate `admin_table`. `teacher_subject_assignment` scopes faculty permissions. `quiz.published` separates drafts from student-visible exams. `exam_attempt` stores ownership, timestamps, status, score, and total; `answer_record` stores one selected option and correctness value per question. `audit_log` and `system_setting` store governance history and configurable defaults. Startup migrations add the new fields/tables without dropping existing records.

## 6. Acceptance criteria
An unauthenticated or wrong-owner request cannot view or submit an attempt; a student's second start request resumes the same active attempt or shows its submitted result; forged scores are ignored; valid, invalid, and unanswered choices produce the correct aggregate; repeated submission cannot change the stored result; and server expiry prevents late scoring. Public registration cannot create faculty or administrator accounts. Faculty access is limited to assigned subjects and is revoked when demoted. Only administrators can publish a faculty draft. Legacy databases retain records and receive student defaults for old users and published defaults for old exams.

## 7. Limitations
The current app uses a single SQLite database and does not provide proctoring, essay grading, randomized question banks, or multiple attempts. The default passing threshold is 50 percent and can be changed by an administrator. Deployments beyond a trusted development environment require HTTPS, a managed secret, database backups, and operational monitoring.
