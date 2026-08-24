#!/usr/bin/env python3
"""
Security tests for the login / authentication system.

Covers:
  1. Password hashing  – plain text never stored
  2. Login endpoint    – correct creds, wrong creds, missing fields
  3. Session handling  – set on login, cleared on logout, /me enforcement
  4. Rate limiting     – brute-force lock-out after 5 requests / 60 s
  5. Username case     – accounts are case-sensitive (no collision bypass)
  6. Empty / blank credentials rejected

Run:
    cd Battlegrounds && python tests/test_auth_security.py
"""

import sys
import os
import json
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app import create_app
from models import db, Player
from rate_limit import reset_rate_limits

app = create_app()

PASS = []
FAIL = []


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def run_test(fn):
    name = fn.__name__
    try:
        with app.app_context():
            _clean_test_players()
        fn()
        PASS.append(name)
        print(f"  PASS  {name}")
    except Exception as exc:
        FAIL.append(name)
        print(f"  FAIL  {name}")
        traceback.print_exc()


def _clean_test_players():
    Player.query.filter(Player.username.like('_test_%')).delete(synchronize_session=False)
    db.session.commit()


def _make_player(username='_test_user', password='GoodPass1!'):
    with app.app_context():
        p = Player(username=username)
        p.set_password(password)
        db.session.add(p)
        db.session.commit()


def _bypass_safety(client):
    """Inject safety_verified into the test client's session."""
    with client.session_transaction() as sess:
        sess['safety_verified'] = True


def auth_post(client, path, payload, environ_base=None):
    kwargs = dict(
        data=json.dumps(payload),
        content_type='application/json',
    )
    if environ_base:
        kwargs['environ_base'] = environ_base
    resp = client.post(f'/api/auth{path}', **kwargs)
    return resp.status_code, resp.get_json()


def auth_get(client, path):
    resp = client.get(f'/api/auth{path}', content_type='application/json')
    return resp.status_code, resp.get_json()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Password hashing
# ──────────────────────────────────────────────────────────────────────────────

def test_password_not_stored_plain():
    """set_password hashes; raw password never appears in password_hash."""
    with app.app_context():
        p = Player(username='_test_hash_check')
        p.set_password('SuperSecret99')
        assert p.password_hash != 'SuperSecret99'
        assert 'SuperSecret99' not in p.password_hash


def test_correct_password_verifies():
    with app.app_context():
        p = Player(username='_test_verify')
        p.set_password('MyPass123')
        assert p.check_password('MyPass123') is True


def test_wrong_password_rejected():
    with app.app_context():
        p = Player(username='_test_wrong')
        p.set_password('MyPass123')
        assert p.check_password('WrongPass') is False


def test_empty_password_rejected():
    with app.app_context():
        p = Player(username='_test_empty_pw')
        p.set_password('HasAPassword')
        assert p.check_password('') is False


# ──────────────────────────────────────────────────────────────────────────────
# 2. Login endpoint
# ──────────────────────────────────────────────────────────────────────────────

def test_login_success():
    _make_player('_test_login_ok', 'GoodPass1!')
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        status, body = auth_post(client, '/login', {'username': '_test_login_ok', 'password': 'GoodPass1!'})
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert 'player' in body


def test_login_wrong_password():
    _make_player('_test_login_bad', 'CorrectHorse')
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        status, body = auth_post(client, '/login', {'username': '_test_login_bad', 'password': 'wronghorse'})
    assert status == 401, f"Expected 401, got {status}: {body}"


def test_login_nonexistent_user():
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        status, body = auth_post(client, '/login', {'username': '_test_no_such_user', 'password': 'anything'})
    assert status == 401, f"Expected 401, got {status}: {body}"


def test_login_missing_username_field():
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        status, body = auth_post(client, '/login', {'password': 'only_pw'})
    assert status == 400, f"Expected 400, got {status}: {body}"


def test_login_missing_password_field():
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        status, body = auth_post(client, '/login', {'username': 'someone'})
    assert status == 400, f"Expected 400, got {status}: {body}"


def test_login_empty_body():
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        status, body = auth_post(client, '/login', {})
    assert status == 400, f"Expected 400, got {status}: {body}"


def test_login_error_message_is_generic():
    """Wrong username and wrong password should return the same message (no user enumeration)."""
    _make_player('_test_enum', 'SomePass!')
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        _, body_bad_pw  = auth_post(client, '/login', {'username': '_test_enum', 'password': 'wrong'})
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        _, body_no_user = auth_post(client, '/login', {'username': '_test_no_exist_x', 'password': 'wrong'})
    assert body_bad_pw.get('error') == body_no_user.get('error'), \
        "Login errors leak whether the username exists"


# ──────────────────────────────────────────────────────────────────────────────
# 3. Session management
# ──────────────────────────────────────────────────────────────────────────────

def test_session_set_after_login():
    _make_player('_test_sess', 'Passw0rd!')
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        auth_post(client, '/login', {'username': '_test_sess', 'password': 'Passw0rd!'})
        status, body = auth_get(client, '/me')
    assert status == 200, f"/me should be 200 after login, got {status}"
    assert body['player']['username'] == '_test_sess'


def test_session_cleared_after_logout():
    _make_player('_test_logout', 'Passw0rd!')
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        auth_post(client, '/login', {'username': '_test_logout', 'password': 'Passw0rd!'})
        auth_post(client, '/logout', {})
        # logout clears the whole session (including safety_verified), so re-inject it
        _bypass_safety(client)
        status, body = auth_get(client, '/me')
    assert status == 401, f"/me should be 401 after logout, got {status}"


def test_me_requires_login():
    with app.test_client() as client:
        _bypass_safety(client)
        status, _ = auth_get(client, '/me')
    assert status == 401, f"/me should require auth, got {status}"


def test_check_session_false_when_not_logged_in():
    with app.test_client() as client:
        _bypass_safety(client)
        status, body = auth_get(client, '/check-session')
    assert status == 200
    assert body['logged_in'] is False


def test_check_session_true_after_login():
    _make_player('_test_chk', 'Pass1234!')
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        auth_post(client, '/login', {'username': '_test_chk', 'password': 'Pass1234!'})
        status, body = auth_get(client, '/check-session')
    assert status == 200
    assert body['logged_in'] is True


# ──────────────────────────────────────────────────────────────────────────────
# 4. Rate limiting on /login
# ──────────────────────────────────────────────────────────────────────────────

def test_login_rate_limit_blocks_after_5_failures():
    """6th request from same IP within 60 s should get 429."""
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        last_status = None
        for i in range(6):
            last_status, _ = auth_post(
                client,
                '/login',
                {'username': '_test_brute', 'password': 'wrong'},
                environ_base={'REMOTE_ADDR': '10.0.0.1'},
            )
        assert last_status == 429, f"Expected 429 on 6th attempt, got {last_status}"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Username case-sensitivity
# ──────────────────────────────────────────────────────────────────────────────

def test_username_case_sensitive():
    """'Tester' and 'tester' are different accounts."""
    _make_player('_test_Case', 'Pass1!')
    reset_rate_limits()
    with app.test_client() as client:
        _bypass_safety(client)
        status, _ = auth_post(client, '/login', {'username': '_test_case', 'password': 'Pass1!'})
    assert status == 401, "Login should fail when case doesn't match"


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

TESTS = [
    test_password_not_stored_plain,
    test_correct_password_verifies,
    test_wrong_password_rejected,
    test_empty_password_rejected,
    test_login_success,
    test_login_wrong_password,
    test_login_nonexistent_user,
    test_login_missing_username_field,
    test_login_missing_password_field,
    test_login_empty_body,
    test_login_error_message_is_generic,
    test_session_set_after_login,
    test_session_cleared_after_logout,
    test_me_requires_login,
    test_check_session_false_when_not_logged_in,
    test_check_session_true_after_login,
    test_login_rate_limit_blocks_after_5_failures,
    test_username_case_sensitive,
]

if __name__ == '__main__':
    print(f"\nRunning {len(TESTS)} auth security tests...\n")
    for t in TESTS:
        run_test(t)

    print(f"\n{'='*50}")
    print(f"  Passed: {len(PASS)} / {len(TESTS)}")
    if FAIL:
        print(f"  Failed: {FAIL}")
    print('='*50)
    sys.exit(0 if not FAIL else 1)
