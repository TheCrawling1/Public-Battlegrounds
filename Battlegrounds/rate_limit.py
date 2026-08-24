"""
Rate Limiting & Access Control — security utilities for Flask endpoints.

Usage:
    from rate_limit import rate_limit, localhost_only

    @app.route('/api/move')
    @rate_limit(max_requests=20, window_seconds=10)
    def move():
        ...

    # Restrict a whole blueprint to local requests:
    my_blueprint.before_request(localhost_only)
"""

import time
from collections import defaultdict
from functools import wraps
from flask import request, jsonify

# IPs that count as "local" — loopback for IPv4 and IPv6
_LOCAL_IPS = {'127.0.0.1', '::1'}


def localhost_only():
    """Block non-localhost requests.  Use as a before_request hook or call directly.

    Returns None (allow) for local IPs, or a 403 JSON response for remote ones.
    """
    ip = request.remote_addr or ''
    if ip not in _LOCAL_IPS:
        return jsonify({'success': False, 'error': 'Dev endpoints are localhost-only'}), 403

# ip -> list of request timestamps
_request_log = defaultdict(list)


def rate_limit(max_requests=30, window_seconds=10):
    """Reject requests from an IP that exceed max_requests within the sliding window."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or '0.0.0.0'
            now = time.time()
            cutoff = now - window_seconds

            # Trim timestamps older than the window
            timestamps = _request_log[ip]
            _request_log[ip] = [t for t in timestamps if t > cutoff]

            if len(_request_log[ip]) >= max_requests:
                return jsonify({'success': False, 'error': 'Too many requests'}), 429

            _request_log[ip].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def reset_rate_limits():
    """Clear all rate limit state. Useful for testing."""
    _request_log.clear()
