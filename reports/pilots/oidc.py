"""Access token boundary shared by the two Reports HTTP APIs."""
import os

import jwt


def claims_for(token, jwks):
    try:
        key = jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token, key, algorithms=['RS256'], audience='reports',
            issuer=os.environ['REPORTS_OIDC_ISSUER'],
            options={'require':['exp','sub','iss','aud']},
        )
        if not claims['sub'].strip() or claims.get('typ') != 'Bearer':
            raise jwt.InvalidTokenError('Expected a Keycloak access token')
    except (TypeError, ValueError) as error:
        raise jwt.InvalidTokenError('Invalid token claims') from error
    access = claims.get('resource_access')
    entry = access.get('reports') if isinstance(access,dict) else None
    names = entry.get('roles') if isinstance(entry,dict) else None
    scope = claims.get('scope')
    scopes = scope.split() if isinstance(scope,str) else []
    if not isinstance(names,list) or 'cost.read' not in names:
        scopes = [name for name in scopes if name != 'cost.read']
    claims['scope'] = ' '.join(scopes)
    return claims
