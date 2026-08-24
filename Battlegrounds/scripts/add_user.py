"""
Add a player account to the database.

Usage:
    python add_user.py <username> <password>

Both arguments are required — there are no default credentials.
"""

import sys
import os

if len(sys.argv) != 3:
    print("Usage: python add_user.py <username> <password>")
    sys.exit(2)

username = sys.argv[1]
password = sys.argv[2]

if len(password) < 8:
    print("Password must be at least 8 characters.")
    sys.exit(2)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from models import db, Player

app = create_app()
with app.app_context():
    if Player.query.filter_by(username=username).first():
        print(f"Account '{username}' already exists.")
        sys.exit(1)

    p = Player(username=username)
    p.set_password(password)
    db.session.add(p)
    db.session.commit()
    print(f"Created account: id={p.id}  username={p.username}")
