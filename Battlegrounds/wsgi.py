"""Production WSGI entry point.

Run behind a real WSGI server + TLS reverse proxy, for example:

    gunicorn -w 4 wsgi:app

Do not use `python app.py` (the Flask development server) in production.
See .env.example for the environment variables that must be set.
"""

from app import create_app

app = create_app()
