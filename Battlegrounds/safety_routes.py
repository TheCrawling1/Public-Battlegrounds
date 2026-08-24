import hmac
from flask import Blueprint, jsonify, request, session, current_app
from rate_limit import rate_limit

safety_api = Blueprint('safety_api', __name__)


@safety_api.route('/verify', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=60)
def verify_safety_password():
    """Verify the safety access code and grant site access."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or 'password' not in data:
        return jsonify({'error': 'Access code required'}), 400

    submitted = data.get('password')
    if not isinstance(submitted, str):
        return jsonify({'error': 'Access code required'}), 400

    safety_password = current_app.config.get('SAFETY_PASSWORD', '')

    if not safety_password:
        # Gate disabled — grant access automatically.
        session['safety_verified'] = True
        return jsonify({'success': True})

    # Constant-time comparison to neutralize timing side-channels.
    if hmac.compare_digest(submitted.encode('utf-8'), safety_password.encode('utf-8')):
        session['safety_verified'] = True
        return jsonify({'success': True})

    return jsonify({'error': 'Invalid access code'}), 401


@safety_api.route('/status', methods=['GET'])
def safety_status():
    """Check if safety gate is enabled and whether this session has passed it"""
    safety_password = current_app.config.get('SAFETY_PASSWORD', '')
    return jsonify({
        'gate_enabled': bool(safety_password),
        'verified': session.get('safety_verified', False)
    })
