"""Seed one small, clearly labeled assessment for local demonstration."""
from datetime import date

from app import app
from database import db
from models import chapter, questions, quiz, subject

DEMO_TITLE = "Demo exam - Computer Basics"


def main():
    with app.app_context():
        existing = quiz.query.filter_by(remarks=DEMO_TITLE).first()
        if existing:
            print(f"{DEMO_TITLE!r} already exists (quiz id {existing.id}); no changes made.")
            return

        demo_subject = subject(name="Demo Subject", Description="Sample content for local testing.")
        db.session.add(demo_subject)
        db.session.flush()

        demo_chapter = chapter(
            sub_id=demo_subject.id,
            name="Computer Basics",
            Description="Three sample multiple-choice questions.",
        )
        db.session.add(demo_chapter)
        db.session.flush()

        demo_quiz = quiz(
            chapter_id=demo_chapter.id,
            date_of_quiz=date.today().isoformat(),
            time_duration="10",
            remarks=DEMO_TITLE,
            quesion_id=1,
        )
        db.session.add(demo_quiz)
        db.session.flush()

        sample_questions = [
            ("Which component executes program instructions?", "CPU", "Monitor", "Keyboard", "Printer", "1"),
            ("Which of these is temporary working memory?", "SSD", "RAM", "USB drive", "DVD", "2"),
            ("Which protocol is commonly used for secure web browsing?", "FTP", "HTTP", "HTTPS", "SMTP", "3"),
        ]
        for statement, option1, option2, option3, option4, correct in sample_questions:
            db.session.add(questions(
                quiz_id=demo_quiz.id,
                chapter_id=demo_chapter.id,
                question_statement=statement,
                option1=option1,
                option2=option2,
                option3=option3,
                option4=option4,
                correct_opt=correct,
            ))

        db.session.commit()
        print(f"Created {DEMO_TITLE!r} with {len(sample_questions)} questions (quiz id {demo_quiz.id}).")


if __name__ == "__main__":
    main()
