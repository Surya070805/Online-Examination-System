"""Create an administrator account without a built-in default password."""
import argparse
import getpass
import secrets
import sys

from werkzeug.security import generate_password_hash

from app import app
from database import db
from models import admin_table, user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="admin", help="Administrator username (default: admin)")
    parser.add_argument("--generate", action="store_true", help="Generate and print a one-time strong password")
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        parser.error("username cannot be empty")

    with app.app_context():
        if admin_table.query.filter_by(username=username).first():
            print(f"Administrator {username!r} already exists.", file=sys.stderr)
            return 1
        if user.query.filter_by(userName=username).first():
            print("That username is already used by a student account.", file=sys.stderr)
            return 1

        if args.generate:
            password = secrets.token_urlsafe(24)
        else:
            password = getpass.getpass("New administrator password (12+ characters): ")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                print("Passwords do not match.", file=sys.stderr)
                return 1
            if len(password) < 12:
                print("Choose a password with at least 12 characters.", file=sys.stderr)
                return 1

        db.session.add(admin_table(username=username, Password=generate_password_hash(password)))
        db.session.commit()

    print(f"Administrator created. Username: {username}")
    if args.generate:
        print(f"One-time password (save it now): {password}")
    else:
        print("Password stored as a one-way hash.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
