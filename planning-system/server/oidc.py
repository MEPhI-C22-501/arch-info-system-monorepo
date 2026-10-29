"""OIDC configuration; plain HTTP is limited to the isolated local Keycloak."""
import os
from urllib.parse import urlparse


def endpoint(value):
    parsed = urlparse(value)
    local_http = (
        os.environ.get('APP_ENV') == 'development'
        and os.environ.get('OIDC_LOCAL_HTTP') == 'true'
        and parsed.scheme == 'http'
        and parsed.hostname in {'localhost', '127.0.0.1', 'keycloak'}
    )
    if parsed.username or parsed.password or not parsed.hostname:
        raise ValueError('Invalid OIDC endpoint')
    if parsed.scheme != 'https' and not local_http:
        raise ValueError('HTTPS OIDC endpoint required')
    return value
