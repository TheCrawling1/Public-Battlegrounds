import re
import os
from datetime import datetime
from flask import Blueprint, jsonify, request, session, current_app
from sqlalchemy import func, text
from models import db, Player, InviteCode
from rate_limit import rate_limit

auth_api = Blueprint('auth_api', __name__)

USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_]{3,32}$')
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


@auth_api.route('/login', methods=['POST'])
@rate_limit(max_requests=5, window_seconds=60)
def login():
    """Login endpoint"""
    data = request.get_json(silent=True)

    if not data or not isinstance(data, dict) or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password required'}), 400

    username = data.get('username')
    password = data.get('password')

    # Reject non-string / blank credentials early.
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        return jsonify({'error': 'Invalid username or password'}), 401

    # Find player
    player = Player.query.filter_by(username=username).first()

    if not player or not player.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # Update last login
    player.last_login = datetime.utcnow()
    db.session.commit()

    # Rotate the session identifier on privilege change to neutralize any pre-login
    # session value an attacker may have planted (session fixation defense).
    session.clear()
    session['safety_verified'] = True  # Already past the gate to reach login
    session['player_id'] = player.id
    session['username'] = player.username

    return jsonify({
        'message': 'Login successful',
        'player': player.to_dict()
    })


@auth_api.route('/signup', methods=['POST'])
@rate_limit(max_requests=5, window_seconds=60)
def signup():
    """Create a new account by consuming a single-use invite code.

    Body: {"invite_code": "...", "username": "...", "password": "..."}

    Rules:
      - Invite code must exist and be unused (consumed atomically).
      - Username: 3-32 chars, [A-Za-z0-9_] only, case-insensitively unique.
      - Password: 8-128 chars.
      - Resulting Player inherits is_tester from the invite code.
      - If BETA_MODE=true, the created account is always a tester regardless of code.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid request body'}), 400

    invite_code = data.get('invite_code')
    username = data.get('username')
    password = data.get('password')

    if not isinstance(invite_code, str) or not invite_code:
        return jsonify({'error': 'Invite code required'}), 400
    if not isinstance(username, str) or not USERNAME_PATTERN.match(username):
        return jsonify({'error': 'Username must be 3-32 chars, letters/numbers/underscore only'}), 400
    if not isinstance(password, str) or not (MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH):
        return jsonify({'error': f'Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} chars'}), 400

    # Reserved names
    if username.lower() in ('admin', 'administrator', 'root', 'system'):
        return jsonify({'error': 'Username unavailable'}), 400

    # Case-insensitive uniqueness check
    existing = Player.query.filter(func.lower(Player.username) == username.lower()).first()
    if existing:
        return jsonify({'error': 'Username unavailable'}), 400

    # Consume the invite code atomically. UPDATE...WHERE used_at IS NULL
    # guarantees only one concurrent signup can claim it.
    code_row = InviteCode.query.filter_by(code=invite_code).first()
    if not code_row or code_row.is_used():
        return jsonify({'error': 'Invalid or already-used invite code'}), 400

    # Determine tester flag — beta mode forces tester for all signups.
    beta_mode = current_app.config.get('BETA_MODE', False)
    is_tester = bool(beta_mode or code_row.is_tester)

    player = Player(username=username, is_tester=is_tester)
    player.set_password(password)
    db.session.add(player)

    try:
        db.session.flush()  # Get player.id before committing

        # Atomic claim of the invite code using a conditional UPDATE.
        result = db.session.execute(
            text(
                "UPDATE invite_codes "
                "SET used_at = :used_at, used_by_player_id = :pid "
                "WHERE code = :code AND used_at IS NULL"
            ),
            {'used_at': datetime.utcnow(), 'pid': player.id, 'code': invite_code},
        )
        if result.rowcount != 1:
            # Lost the race or code was consumed between our check and update.
            db.session.rollback()
            return jsonify({'error': 'Invalid or already-used invite code'}), 400

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Signup failed'}), 500

    # Log the new account in immediately (safer than a separate POST).
    session.clear()
    session['safety_verified'] = True
    session['player_id'] = player.id
    session['username'] = player.username

    return jsonify({
        'message': 'Account created',
        'player': player.to_dict()
    }), 201


@auth_api.route('/signup-enabled', methods=['GET'])
def signup_enabled():
    """Expose whether the signup form should be shown on the client."""
    return jsonify({
        'enabled': bool(current_app.config.get('SIGNUP_ENABLED', False)),
        'beta_mode': bool(current_app.config.get('BETA_MODE', False)),
    })


@auth_api.route('/logout', methods=['POST'])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@auth_api.route('/me', methods=['GET'])
def get_current_player():
    """Get current logged in player"""
    player_id = session.get('player_id')

    if not player_id:
        return jsonify({'error': 'Not logged in'}), 401

    player = Player.query.get(player_id)

    if not player:
        session.clear()
        return jsonify({'error': 'Player not found'}), 404

    return jsonify({'player': player.to_dict()})


@auth_api.route('/check-session', methods=['GET'])
def check_session():
    """Check if user is logged in"""
    player_id = session.get('player_id')

    if player_id:
        player = Player.query.get(player_id)
        if player:
            return jsonify({
                'logged_in': True,
                'player': player.to_dict()
            })

    return jsonify({'logged_in': False})
