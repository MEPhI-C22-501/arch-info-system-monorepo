"""An OIDC browser session cannot outlive the verified access token."""
import time


def expired(expires_at, now=None):
    return type(expires_at) is not int or expires_at <= (time.time() if now is None else now)


def install(app):
    from flask import jsonify, redirect, request, session
    from flask_login import current_user, logout_user

    @app.before_request
    def enforce_oidc_expiry():
        # Reject browser writes from a foreign Origin even if a session cookie
        # and a valid CSRF token have been supplied. Missing Origin still uses
        # Superset's CSRF protection; this does not exempt any write endpoint.
        origin = request.headers.get('Origin')
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and origin is not None:
            if origin not in app.config.get('REPORTS_ALLOWED_ORIGINS', ()):
                return jsonify({'message': 'Origin is not allowed'}), 403
        if current_user.is_authenticated and expired(session.get('reports_token_exp')):
            logout_user()
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'message': 'OIDC login required'}), 401
            return redirect('/login/')
