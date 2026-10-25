import os
import uuid
import jwt
from flask_appbuilder.security.manager import AUTH_OAUTH
from superset.security import SupersetSecurityManager
from flask import session
from session_policy import install

ISSUER = 'http://localhost:8180/realms/reports-pilot'
INTERNAL = 'http://keycloak:8080/realms/reports-pilot/protocol/openid-connect/'
SECRET_KEY = os.environ['SUPERSET_SECRET_KEY']
SQLALCHEMY_DATABASE_URI = os.environ['REPORTS_BI_METADATA_URL']
AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = 'ReportsNoAccess'
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {'reports-member': ['Gamma'], 'reports-admin': ['Admin']}
WTF_CSRF_ENABLED = True
REPORTS_ALLOWED_ORIGINS = ('http://localhost:8088',)
ENABLE_CORS = False
ENABLE_PROXY_FIX = False
FEATURE_FLAGS = {'ENABLE_TEMPLATE_PROCESSING': True, 'ESCAPE_MARKDOWN_HTML': True}
HTML_SANITIZATION = True
DATA_CACHE_CONFIG = {
    'CACHE_TYPE': 'SupersetMetastoreCache',
    'CACHE_KEY_PREFIX': 'reports_chart_data',
    'CACHE_DEFAULT_TIMEOUT': 60,
}
FLASK_APP_MUTATOR = install
OAUTH_PROVIDERS = [{
    'name': 'keycloak', 'icon': 'fa-key', 'token_key': 'access_token',
    'remote_app': {
        'client_id': 'reports-superset', 'client_secret': os.environ['REPORTS_SUPERSET_CLIENT_SECRET'],
        'client_kwargs': {'scope': 'openid profile email'},
        'authorize_url': ISSUER+'/protocol/openid-connect/auth',
        'access_token_url': INTERNAL+'token', 'jwks_uri': INTERNAL+'certs', 'issuer': ISSUER,
    },
}]


class ReportsSecurityManager(SupersetSecurityManager):
    def oauth_user_info(self, provider, response=None):
        if provider != 'keycloak' or not response:
            raise PermissionError('OIDC response required')
        token = response['access_token']
        key = jwt.PyJWKClient(INTERNAL+'certs').get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience='reports', issuer=ISSUER,
                            options={'require': ['exp', 'sub', 'iss', 'aud']})
        subject = str(uuid.UUID(claims['sub']))  # Safe UUID in RLS current_username().
        access = claims.get('resource_access', {})
        resource = access.get('reports', {}) if isinstance(access, dict) else {}
        roles = resource.get('roles') if isinstance(resource, dict) else None
        if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
            raise PermissionError('Invalid Reports roles')
        if {'reports-admin','reports-analyst'} <= set(roles):
            roles = ['reports-admin']
        elif 'reports-member' in roles:
            roles = ['reports-member']
        else:
            raise PermissionError('Use Reports UI for this role')
        session['reports_token_exp'] = claims['exp']
        return {'username': subject, 'first_name': claims.get('given_name', ''),
                'last_name': claims.get('family_name', ''), 'email': claims.get('email', ''), 'role_keys': roles}


CUSTOM_SECURITY_MANAGER = ReportsSecurityManager
