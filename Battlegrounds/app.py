import logging
import os
import secrets
import string
from datetime import timedelta
from flask import Flask, jsonify, session, request, redirect, send_from_directory, abort
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from logging_config import configure_logging
from models import db

logger = logging.getLogger(__name__)
from routes import api
from auth_routes import auth_api
from safety_routes import safety_api
from database import init_database
from config import DATABASE_URL
from dev_combat_routes import dev_api
from dev_events_routes import dev_events_api
from dev_ghosts_routes import dev_ghosts_api
from collection_routes import collection_api
from game_random import game_random

# Directory where HTML/CSS/JS files live (same folder as this file)
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Endpoints that bypass the safety gate. Keep this list minimal — every exempt
# endpoint is an attack surface pre-authentication.
_SAFETY_EXEMPT_ENDPOINTS = {
    'safety_api.verify_safety_password',
    'safety_api.safety_status',
    'serve_safety_login',
    'health',
}

# Files inside STATIC_DIR that must be reachable to render the safety-login page
# itself. safety-login.html is intentionally self-contained (inline CSS + JS),
# so this set is empty — any other asset is gated.
_SAFETY_EXEMPT_STATIC_FILES = set()


def _generate_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _env_flag(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ('1', 'true', 'yes', 'on')


def create_app():
    """Create and configure the Flask application."""
    configure_logging()
    app = Flask(__name__, static_folder=None)  # We handle static serving ourselves

    # ── Configuration ──────────────────────────────────────────────────────────
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # SECRET_KEY: require a strong value. If unset, generate a random one at boot.
    # A random-per-boot key invalidates sessions on restart, which is acceptable
    # for a beta deployment and prevents anyone forging safety_verified cookies.
    secret_key = os.environ.get('SECRET_KEY', '').strip()
    if not secret_key or secret_key == 'dev-secret-key':
        secret_key = secrets.token_urlsafe(48)
        logger.warning("No SECRET_KEY env var — generated a random one. Sessions will not "
                       "survive restarts. Set SECRET_KEY to a long random string for stable sessions.")
    app.config['SECRET_KEY'] = secret_key

    # Session cookie hardening. These defend against XSS-based cookie theft,
    # CSRF, and cookie injection over plaintext HTTP.
    #   - HttpOnly: JS cannot read the cookie (mitigates XSS session theft)
    #   - SameSite=Lax: browsers won't send the cookie on most cross-site requests
    #   - Secure: only sent over HTTPS (enable via SESSION_COOKIE_SECURE=true
    #     once you have TLS; leave off on plain HTTP or the cookie won't work)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # Off by default so the app works out-of-the-box over plain HTTP (local dev).
    # PRODUCTION MUST set SESSION_COOKIE_SECURE=true once served behind HTTPS, or
    # the session cookie can be sent over plaintext. See .env.example / README.
    app.config['SESSION_COOKIE_SECURE'] = _env_flag('SESSION_COOKIE_SECURE', default=False)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    # Safety gate password — set SAFETY_PASSWORD env var to pin a fixed code.
    safety_password = os.environ.get('SAFETY_PASSWORD', '')
    app.config['SAFETY_PASSWORD'] = safety_password
    if not safety_password:
        generated = _generate_password()
        app.config['SAFETY_PASSWORD'] = generated
        logger.info("SAFETY ACCESS CODE: %s", generated)
        logger.info("(Set SAFETY_PASSWORD env var to use a fixed code)")
    else:
        logger.info("Safety gate enabled with configured password.")

    # Beta/signup configuration.
    app.config['BETA_MODE'] = _env_flag('BETA_MODE', default=False)
    # Signup is available whenever there's at least one way to classify accounts:
    # either we're in beta mode (all signups = testers), or an operator has minted
    # invite codes manually. The client will still gate on invite code existence.
    app.config['SIGNUP_ENABLED'] = _env_flag('SIGNUP_ENABLED', default=app.config['BETA_MODE'])

    if app.config['BETA_MODE']:
        logger.info("BETA_MODE enabled — all signups will be flagged is_tester=True.")
    if app.config['SIGNUP_ENABLED']:
        logger.info("Signup endpoint enabled (invite code required).")

    # Developer tooling (combat simulator, event/ghost editors, sound/demo pages)
    # is disabled by default. It is internal-only tooling that must never be
    # reachable in a public deployment, so it is gated behind an explicit env flag.
    app.config['ENABLE_DEV_ROUTES'] = _env_flag('ENABLE_DEV_ROUTES', default=False)
    if app.config['ENABLE_DEV_ROUTES']:
        logger.warning("ENABLE_DEV_ROUTES enabled — developer tooling pages/APIs are exposed.")

    # ── Extensions ─────────────────────────────────────────────────────────────
    # Trust one reverse-proxy hop for X-Forwarded-For/-Proto so request.remote_addr
    # and scheme reflect the real client behind nginx/Caddy. Without this, IP-based
    # controls (rate limiting, localhost-only dev routes) would see the proxy's IP.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    # CORS is locked to an explicit allow-list. The game frontend is served from
    # the same origin as the API, so no cross-origin access is needed by default.
    # Set CORS_ORIGINS (comma-separated) only if you host the frontend elsewhere.
    cors_origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', '').split(',') if o.strip()]
    if cors_origins:
        CORS(app, origins=cors_origins, supports_credentials=True)

    # ── Blueprints ─────────────────────────────────────────────────────────────
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(auth_api, url_prefix='/api/auth')
    app.register_blueprint(safety_api, url_prefix='/api/safety')
    app.register_blueprint(collection_api, url_prefix='/api/collection')

    # Developer tooling APIs — registered only when explicitly enabled.
    if app.config['ENABLE_DEV_ROUTES']:
        app.register_blueprint(dev_api, url_prefix='/api/dev')
        app.register_blueprint(dev_events_api, url_prefix='/api/dev-events')
        app.register_blueprint(dev_ghosts_api, url_prefix='/api/dev-ghosts')

    # ── Database ───────────────────────────────────────────────────────────────
    init_database(app)

    # ── Safety gate middleware ─────────────────────────────────────────────────
    @app.before_request
    def safety_gate():
        """Reject every request until the session has proved it knows the access code.

        Rules (defense-in-depth):
          * Run before any route handler — so no view, static or otherwise, is reached.
          * Applies to every HTTP method including OPTIONS: we don't want an attacker
            probing for endpoints via preflight.
          * The only exempt endpoints are: the safety verify/status API, the safety
            login HTML itself, and /health. Nothing else.
          * If safety_password is empty string we treat the gate as DISABLED; but the
            app always generates a random code when none is provided, so in practice
            the gate is always on.
        """
        # Unknown/unmatched URL — let Flask raise 404 through the error handler
        # (which stays JSON for /api/ or plain 404 otherwise). `before_request`
        # runs *before* routing, but `request.endpoint` is populated by now.
        safety_pw = app.config.get('SAFETY_PASSWORD', '')
        if not safety_pw:
            return  # Gate disabled entirely

        if request.endpoint in _SAFETY_EXEMPT_ENDPOINTS:
            return

        if session.get('safety_verified'):
            return

        # Not verified — API paths get JSON 403; everything else redirects to login.
        # Caller can hot-modify the client, so we never include any HTML here.
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Access denied. Safety login required.'}), 403
        # For all static file/HTML requests, force a redirect to the login page.
        # Return a terminal response — the 302 Location header contains no app data.
        return redirect('/safety-login', code=302)

    # ── HTML page routes ───────────────────────────────────────────────────────
    @app.route('/safety-login')
    def serve_safety_login():
        # If already verified, don't reveal the login UI — bounce to the game.
        if session.get('safety_verified'):
            return redirect('/', code=302)
        return send_from_directory(STATIC_DIR, 'safety-login.html')

    @app.route('/')
    def serve_index():
        return send_from_directory(STATIC_DIR, 'index.html')

    # Developer tooling pages — registered only when ENABLE_DEV_ROUTES is set.
    # These are internal tools (combat simulator, event/ghost editors, sound and
    # demo pages) and are never exposed in a public deployment.
    _DEV_PAGES = {
        '/dev-combat': 'dev-combat.html',
        '/dev-events': 'dev-events.html',
        '/dev-ghosts': 'dev-ghosts.html',
        '/dev-sounds': 'dev-sounds.html',
        '/demo-trophy-display': 'demo-trophy-display.html',
        '/event-icons-display': 'event-icons-display.html',
        '/examples': 'examples.html',
    }
    # HTML filenames that must never be served through the catch-all static route
    # when dev tooling is disabled.
    _DEV_PAGE_FILES = set(_DEV_PAGES.values())

    if app.config['ENABLE_DEV_ROUTES']:
        def _make_dev_page(page_file):
            return lambda: send_from_directory(STATIC_DIR, page_file)
        for route, page_file in _DEV_PAGES.items():
            app.add_url_rule(
                route,
                endpoint=f'dev_page_{page_file}',
                view_func=_make_dev_page(page_file),
            )

    # Serve all static assets (CSS, JS, images, etc.). `send_from_directory`
    # normalises paths and rejects `..` traversal automatically.
    @app.route('/<path:filename>')
    def serve_static(filename):
        # Block access to sensitive source / config files even if the gate is off.
        # Flask's path converter already disallows the file from escaping STATIC_DIR,
        # but we also don't want the game serving its own Python source.
        forbidden_exts = ('.py', '.db', '.sqlite', '.sqlite3', '.env', '.ini', '.log', '.yml', '.yaml')
        lower = filename.lower()
        if lower.endswith(forbidden_exts):
            abort(404)
        if lower.startswith('tests/') or lower.startswith('.git'):
            abort(404)
        # Don't let the catch-all leak dev tooling pages when dev routes are off.
        if not app.config['ENABLE_DEV_ROUTES'] and os.path.basename(lower) in _DEV_PAGE_FILES:
            abort(404)
        return send_from_directory(STATIC_DIR, filename)

    # ── JSON error handlers for API routes ────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return e

    @app.errorhandler(500)
    def internal_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return e

    # ── Health check ───────────────────────────────────────────────────────────
    # Minimal — nothing here should leak internal state. Previously this exposed
    # session_id and dev_mode which is noise at best / fingerprinting at worst.
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    return app


if __name__ == '__main__':
    app = create_app()

    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = _env_flag('DEBUG', default=False)

    print()
    print("Starting Auto Battler Game Server...")
    print(f"  Listening on: http://{host}:{port}")
    print(f"  Debug mode:   {debug}")
    print()
    print("Players connect to:  http://<your-ip>:5000/")
    print("Safety login page:   http://<your-ip>:5000/safety-login")
    print()

    app.run(debug=debug, host=host, port=port)
