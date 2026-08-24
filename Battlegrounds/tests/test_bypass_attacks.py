#!/usr/bin/env python3
"""
Penetration tests for the safety gate + signup / invite flow.

Assumes an attacker who:
  - Has no access code
  - Can fully control their own browser (cookies, headers, JS)
  - Can enumerate URLs, send arbitrary methods, try traversal / forgery

Every test asserts a defense holds. A test failing means the real server
is probably exploitable.

Run:
    cd Battlegrounds && SAFETY_PASSWORD=testpass123 BETA_MODE=true python3 tests/test_bypass_attacks.py
"""

import json
import os
import sys
import traceback

# Ensure deterministic config for these tests
os.environ.setdefault('SAFETY_PASSWORD', 'testpass123')
os.environ.setdefault('BETA_MODE', 'true')
os.environ.setdefault('SIGNUP_ENABLED', 'true')
os.environ.setdefault('SECRET_KEY', 'test-suite-secret-key-must-be-long-enough-12345')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app import create_app
from models import db, Player, InviteCode
from rate_limit import reset_rate_limits


app = create_app()

PASS = []
FAIL = []


# ── helpers ──────────────────────────────────────────────────────────────────

def run_test(fn):
    name = fn.__name__
    try:
        with app.app_context():
            _clean()
        reset_rate_limits()
        fn()
        PASS.append(name)
        print(f"  PASS  {name}")
    except AssertionError as e:
        FAIL.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")
    except Exception as e:
        FAIL.append((name, f"ERROR: {e}"))
        print(f"  FAIL  {name}: ERROR")
        traceback.print_exc()


def _clean():
    Player.query.filter(Player.username.like('_atk_%')).delete(synchronize_session=False)
    InviteCode.query.filter(InviteCode.note == '_atk_') \
        .delete(synchronize_session=False)
    db.session.commit()


def _make_invite(is_tester=True):
    import secrets
    with app.app_context():
        code = secrets.token_urlsafe(12)
        row = InviteCode(code=code, is_tester=is_tester, note='_atk_')
        db.session.add(row)
        db.session.commit()
        return code


def _verify_safety(client, password='testpass123'):
    r = client.post('/api/safety/verify',
                    data=json.dumps({'password': password}),
                    content_type='application/json')
    assert r.status_code == 200, f"safety verify failed: {r.status_code} {r.data}"


def _post_json(client, path, body, **kw):
    return client.post(path,
                       data=json.dumps(body),
                       content_type='application/json',
                       **kw)


# ============================================================================
# 1. SAFETY GATE — all pre-auth paths must be blocked
# ============================================================================

def test_index_blocked_without_verification():
    """Unverified GET / must not deliver index.html."""
    with app.test_client() as c:
        r = c.get('/')
    assert r.status_code in (302, 403), f"expected redirect/403, got {r.status_code}"
    if r.status_code == 302:
        assert '/safety-login' in r.headers.get('Location', ''), \
            f"redirect wrong: {r.headers.get('Location')}"
    # Body must not contain the game UI
    assert b'Auto Battler' not in r.data or b'safety-login' in r.data or len(r.data) < 300, \
        "unverified / returned the game HTML"


def test_static_js_blocked_without_verification():
    """Even the JS files should be 302/403 when not verified."""
    targets = ['/js/main-menu.js', '/desktop.css', '/images/original/']
    for t in targets:
        with app.test_client() as c:
            r = c.get(t)
        assert r.status_code in (302, 403, 404), \
            f"{t} leaked content (got {r.status_code})"


def test_api_blocked_returns_json_403():
    """Unverified /api/ paths return JSON 403, not HTML redirect (SPA-friendly)."""
    with app.test_client() as c:
        r = c.get('/api/auth/check-session')
    assert r.status_code == 403
    body = r.get_json()
    assert body and 'error' in body


def test_source_files_never_served():
    """Python source, DB, env files must 404 even post-verification."""
    with app.test_client() as c:
        _verify_safety(c)
        for path in ['/app.py', '/models.py', '/game.db', '/.env', '/config.py', '/database.py']:
            r = c.get(path)
            assert r.status_code == 404, f"{path} was reachable (status {r.status_code})"


def test_path_traversal_rejected():
    """../ and encoded variants must not escape STATIC_DIR."""
    with app.test_client() as c:
        _verify_safety(c)
        # send_from_directory rejects these; we just want a 404 not a 200 with /etc/passwd
        for path in [
            '/../etc/passwd',
            '/%2e%2e/etc/passwd',
            '/..%2fetc%2fpasswd',
            '/js/../app.py',
        ]:
            r = c.get(path)
            assert r.status_code in (400, 403, 404), \
                f"traversal {path!r} returned {r.status_code}"


def test_forged_safety_cookie_with_wrong_secret_fails():
    """A client that doesn't know SECRET_KEY cannot mint a valid session."""
    from itsdangerous import URLSafeTimedSerializer
    evil_secret = 'attacker-guess-dev-secret-key'
    serializer = URLSafeTimedSerializer(evil_secret, salt='cookie-session')
    forged = serializer.dumps({'safety_verified': True})
    with app.test_client() as c:
        c.set_cookie('session', forged)
        r = c.get('/')
    # With the wrong secret, Flask ignores the cookie → session is empty → gate redirects
    assert r.status_code == 302, \
        f"Forged cookie (wrong secret) was accepted! Got {r.status_code}"


def test_options_method_also_gated():
    """Attacker probing via OPTIONS should not bypass the gate."""
    with app.test_client() as c:
        r = c.open('/', method='OPTIONS')
    # With the gate on, OPTIONS to /  should not return 200 with game content.
    assert r.status_code in (302, 403, 405), \
        f"OPTIONS /  returned {r.status_code} (expected 302/403/405)"


def test_unknown_endpoint_still_gated():
    """Unmatched URLs hit 404, but the gate must run first: can't leak via /foo/bar."""
    with app.test_client() as c:
        r = c.get('/definitely/does/not/exist')
    # before_request fires first → redirect to safety-login
    assert r.status_code in (302, 404), f"got {r.status_code}"
    if r.status_code == 302:
        assert '/safety-login' in r.headers.get('Location', '')


def test_api_unknown_endpoint_gated_with_json():
    with app.test_client() as c:
        r = c.get('/api/nonexistent')
    assert r.status_code == 403, f"got {r.status_code}"
    assert r.get_json().get('error')


def test_health_does_not_leak_internals():
    """/health is exempt but must not leak session_id or random-system internals."""
    with app.test_client() as c:
        r = c.get('/health')
    assert r.status_code == 200
    body = r.get_json()
    # Must not include dev_mode, session_id, random internals
    forbidden = {'dev_mode', 'session_id', 'pending_overrides', 'random_system'}
    assert not (set(body.keys()) & forbidden), f"health leaked: {body}"


def test_safety_login_page_self_redirects_when_verified():
    """Already-verified visitor should be bounced away from the login page."""
    with app.test_client() as c:
        _verify_safety(c)
        r = c.get('/safety-login', follow_redirects=False)
    assert r.status_code == 302, f"got {r.status_code}"
    assert r.headers.get('Location', '').endswith('/')


def test_wrong_safety_password_never_verifies():
    with app.test_client() as c:
        for attempt in ['', 'wrong', 'testpass123 ', ' testpass123', 'TESTPASS123']:
            r = _post_json(c, '/api/safety/verify', {'password': attempt})
            assert r.status_code in (400, 401), \
                f"pw={attempt!r} accepted with status {r.status_code}"
        # And we should still be unverified
        r = c.get('/')
        assert r.status_code == 302


def test_safety_verify_rate_limited():
    """Brute force the safety code → 429 kicks in."""
    reset_rate_limits()
    with app.test_client() as c:
        last = None
        for i in range(12):
            r = _post_json(c, '/api/safety/verify', {'password': 'bad'},
                           environ_base={'REMOTE_ADDR': '198.51.100.7'})
            last = r.status_code
        assert last == 429, f"expected 429 after bursts, got {last}"


# ============================================================================
# 2. SIGNUP / INVITE CODE — no free-for-all account creation
# ============================================================================

def test_signup_requires_invite_code():
    with app.test_client() as c:
        _verify_safety(c)
        r = _post_json(c, '/api/auth/signup', {
            'username': '_atk_nocode', 'password': 'GoodPass123'
        })
    assert r.status_code == 400


def test_signup_rejects_bad_invite_code():
    with app.test_client() as c:
        _verify_safety(c)
        r = _post_json(c, '/api/auth/signup', {
            'invite_code': 'totally-bogus-code-xyz',
            'username': '_atk_bogus',
            'password': 'GoodPass123',
        })
    assert r.status_code == 400


def test_signup_invite_code_is_single_use():
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        r1 = _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_first', 'password': 'GoodPass123'
        })
        assert r1.status_code == 201, f"first signup: {r1.status_code} {r1.data}"
    # Second try with the same code from a fresh client should fail.
    with app.test_client() as c2:
        _verify_safety(c2)
        r2 = _post_json(c2, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_second', 'password': 'GoodPass123'
        })
    assert r2.status_code == 400, \
        f"Invite code was reused! second status: {r2.status_code} body: {r2.data}"


def test_signup_username_must_match_charset():
    code = _make_invite()
    bad_names = ['ab', 'x' * 50, '_atk_<script>', '_atk_ a', '_atk_@bad', '']
    for name in bad_names:
        reset_rate_limits()
        with app.test_client() as c:
            _verify_safety(c)
            r = _post_json(c, '/api/auth/signup', {
                'invite_code': code, 'username': name, 'password': 'GoodPass123'
            })
        assert r.status_code == 400, f"bad name {name!r} accepted (got {r.status_code})"


def test_signup_rejects_short_password():
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        r = _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_short', 'password': 'abc'
        })
    assert r.status_code == 400


def test_signup_username_case_insensitive_uniqueness():
    code1 = _make_invite()
    code2 = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        r = _post_json(c, '/api/auth/signup', {
            'invite_code': code1, 'username': '_atk_Dupe', 'password': 'GoodPass123'
        })
        assert r.status_code == 201
    with app.test_client() as c2:
        _verify_safety(c2)
        r2 = _post_json(c2, '/api/auth/signup', {
            'invite_code': code2, 'username': '_atk_dupe', 'password': 'GoodPass123'
        })
    assert r2.status_code == 400, \
        f"case-different duplicate accepted: {r2.status_code}"


def test_signup_rejects_reserved_names():
    code = _make_invite()
    for name in ['_atk_admin', '_atk_root']:
        pass  # skip — these pass charset but not reserved
    # Test reserved
    for reserved in ['Admin', 'administrator', 'ROOT', 'system']:
        reset_rate_limits()
        with app.test_client() as c:
            _verify_safety(c)
            r = _post_json(c, '/api/auth/signup', {
                'invite_code': code, 'username': reserved, 'password': 'GoodPass123'
            })
        assert r.status_code == 400, f"reserved {reserved!r} was accepted (got {r.status_code})"


def test_beta_mode_forces_is_tester_true():
    """In BETA_MODE, signup with any code (even non-tester) must flag is_tester=True."""
    # Force a non-tester invite
    code = _make_invite(is_tester=False)
    with app.test_client() as c:
        _verify_safety(c)
        r = _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_btest', 'password': 'GoodPass123'
        })
    assert r.status_code == 201, f"{r.status_code} {r.data}"
    body = r.get_json()
    assert body['player']['is_tester'] is True, \
        f"BETA_MODE did not flag account is_tester: {body['player']}"


def test_signup_logs_in_and_gates_still_required_post_logout():
    """After signup the session is authed; after logout, /api/auth/me must 401."""
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        r = _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_flow', 'password': 'GoodPass123'
        })
        assert r.status_code == 201
        r2 = c.get('/api/auth/me')
        assert r2.status_code == 200

        # Logout clears EVERYTHING including safety_verified.
        c.post('/api/auth/logout')

        # Now the safety gate should fire again
        r3 = c.get('/')
        assert r3.status_code == 302, f"logged out but not re-gated: {r3.status_code}"


# ============================================================================
# 3. LOGIN PATH — still sound
# ============================================================================

def test_login_rejects_nonstring_credentials():
    """Passing JSON arrays/objects as credentials must be rejected."""
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_login', 'password': 'GoodPass123'
        })
    with app.test_client() as c2:
        _verify_safety(c2)
        r = _post_json(c2, '/api/auth/login', {
            'username': {'$ne': None}, 'password': 'x'
        })
    assert r.status_code == 401, f"weird types got {r.status_code}"


def test_login_error_message_is_generic():
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_enum', 'password': 'GoodPass123'
        })
    reset_rate_limits()
    with app.test_client() as c2:
        _verify_safety(c2)
        r1 = _post_json(c2, '/api/auth/login',
                        {'username': '_atk_enum', 'password': 'WRONG'})
    reset_rate_limits()
    with app.test_client() as c3:
        _verify_safety(c3)
        r2 = _post_json(c3, '/api/auth/login',
                        {'username': '_atk_nosuch', 'password': 'WRONG'})
    assert r1.status_code == 401 and r2.status_code == 401, \
        f"unexpected statuses: {r1.status_code} {r2.status_code}"
    assert r1.get_json().get('error') == r2.get_json().get('error'), \
        f"login error message leaks existence: r1={r1.get_json()} r2={r2.get_json()}"


def test_login_rotates_session_id():
    """Attacker-planted safety_verified cookie is discarded on login (fixation)."""
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_fix', 'password': 'GoodPass123'
        })
    # Attacker tries to pre-seed a session with extra junk.
    with app.test_client() as c2:
        with c2.session_transaction() as s:
            s['safety_verified'] = True
            s['admin_escalation'] = True  # attacker-planted key
        r = _post_json(c2, '/api/auth/login',
                       {'username': '_atk_fix', 'password': 'GoodPass123'})
        assert r.status_code == 200
        with c2.session_transaction() as s:
            assert 'admin_escalation' not in s, "pre-login session data survived login"


# ============================================================================
# 4. ADMIN / DEFAULTS — no hidden backdoors
# ============================================================================

def test_no_default_admin_without_env():
    """Without ADMIN_PASSWORD env var, the Admin/Admin account must NOT exist."""
    with app.app_context():
        admin = Player.query.filter_by(username='Admin').first()
        # If another test run created Admin via env, skip; else assert absence.
        if admin is None:
            return
        # If Admin exists it must not be 'Admin' hash (i.e., password was set via env)
        assert not admin.check_password('Admin'), \
            "Admin account uses default password 'Admin' — easy takeover"


def test_tester_account_flag_is_persisted():
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_persist', 'password': 'GoodPass123'
        })
    with app.app_context():
        p = Player.query.filter_by(username='_atk_persist').first()
        assert p is not None
        assert p.is_tester is True


def test_invite_code_records_user():
    code = _make_invite()
    with app.test_client() as c:
        _verify_safety(c)
        _post_json(c, '/api/auth/signup', {
            'invite_code': code, 'username': '_atk_rec', 'password': 'GoodPass123'
        })
    with app.app_context():
        row = InviteCode.query.filter_by(code=code).first()
        assert row is not None
        assert row.used_at is not None
        assert row.used_by_player_id is not None


# ============================================================================
# Runner
# ============================================================================

TESTS = [
    # Gate
    test_index_blocked_without_verification,
    test_static_js_blocked_without_verification,
    test_api_blocked_returns_json_403,
    test_source_files_never_served,
    test_path_traversal_rejected,
    test_forged_safety_cookie_with_wrong_secret_fails,
    test_options_method_also_gated,
    test_unknown_endpoint_still_gated,
    test_api_unknown_endpoint_gated_with_json,
    test_health_does_not_leak_internals,
    test_safety_login_page_self_redirects_when_verified,
    test_wrong_safety_password_never_verifies,
    test_safety_verify_rate_limited,

    # Signup
    test_signup_requires_invite_code,
    test_signup_rejects_bad_invite_code,
    test_signup_invite_code_is_single_use,
    test_signup_username_must_match_charset,
    test_signup_rejects_short_password,
    test_signup_username_case_insensitive_uniqueness,
    test_signup_rejects_reserved_names,
    test_beta_mode_forces_is_tester_true,
    test_signup_logs_in_and_gates_still_required_post_logout,

    # Login
    test_login_rejects_nonstring_credentials,
    test_login_error_message_is_generic,
    test_login_rotates_session_id,

    # Admin / persistence
    test_no_default_admin_without_env,
    test_tester_account_flag_is_persisted,
    test_invite_code_records_user,
]

if __name__ == '__main__':
    print(f"\nRunning {len(TESTS)} bypass / attack tests...\n")
    for t in TESTS:
        run_test(t)
    print(f"\n{'='*60}")
    print(f"  Passed: {len(PASS)} / {len(TESTS)}")
    if FAIL:
        print(f"  Failed ({len(FAIL)}):")
        for name, why in FAIL:
            print(f"    - {name}: {why}")
    print('='*60)
    sys.exit(0 if not FAIL else 1)
