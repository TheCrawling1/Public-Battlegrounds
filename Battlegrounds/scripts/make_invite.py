"""Mint invite codes for self-signup.

Usage:
    python make_invite.py                      # 1 tester invite
    python make_invite.py --count 5            # 5 tester invites
    python make_invite.py --count 3 --player   # 3 real-player invites
    python make_invite.py --note "beta wave 1" # attach a note
    python make_invite.py --list               # list unused codes

Codes are single-use and cryptographically random (secrets.token_urlsafe).
They propagate `is_tester` to the account created with them.
"""
import argparse
import os
import secrets
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from models import db, InviteCode


def _fresh_code():
    # 22 chars of URL-safe randomness; ~132 bits of entropy — not guessable.
    return secrets.token_urlsafe(16)


def main():
    ap = argparse.ArgumentParser(description="Mint signup invite codes.")
    ap.add_argument('--count', type=int, default=1, help='How many codes to generate (default 1)')
    ap.add_argument('--player', action='store_true',
                    help='Create real-player invites instead of tester invites')
    ap.add_argument('--note', type=str, default=None, help='Optional note on each code')
    ap.add_argument('--list', action='store_true', help='List all unused codes and exit')
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        if args.list:
            rows = InviteCode.query.filter(InviteCode.used_at.is_(None)).order_by(InviteCode.id).all()
            if not rows:
                print("No unused invite codes.")
                return
            print(f"{len(rows)} unused invite code(s):")
            for r in rows:
                kind = 'tester' if r.is_tester else 'player'
                note = f" — {r.note}" if r.note else ''
                print(f"  [{kind:6}] {r.code}{note}")
            return

        if args.count < 1 or args.count > 100:
            print("--count must be between 1 and 100")
            sys.exit(1)

        is_tester = not args.player
        kind = 'tester' if is_tester else 'player'

        created = []
        for _ in range(args.count):
            code = _fresh_code()
            row = InviteCode(code=code, is_tester=is_tester, note=args.note)
            db.session.add(row)
            created.append(code)
        db.session.commit()

        print(f"Created {len(created)} {kind} invite code(s):")
        for c in created:
            print(f"  {c}")


if __name__ == '__main__':
    main()
