import os
from dataclasses import dataclass
import jwt
from fastapi import Request, HTTPException

ROLES = {'PORTFOLIO_OWNER':'R-01','PLANNER':'R-02','PROJECT_MANAGER':'R-03',
         'RESOURCE_MANAGER':'R-04','TEAM_MEMBER':'R-05','MODULE_ADMIN':'R-06'}
DEMO_PORTFOLIO = '10000000-0000-4000-8000-000000000001'
DEMO_PROJECT = '10000000-0000-4000-8000-000000000002'

@dataclass
class Actor:
    subject: str
    roles: set
    scopes: set
    portfolios: set
    projects: set
    employees: set

def actor(request: Request):
    credentials = request.headers.get('Authorization', '').split()
    if len(credentials)!=2 or credentials[0].lower()!='bearer':
        raise HTTPException(401,'Нужен Bearer-токен')
    token = credentials[1]
    mode = os.environ.get('AUTH_MODE', 'oidc')
    if mode == 'demo':
        if os.environ.get('APP_ENV') != 'development':
            raise RuntimeError('Demo auth разрешён только в development')
        role = token.removeprefix('demo-')
        if token != 'demo-' + role or role not in {*ROLES.values(),'S-03','S-06','S-07'}:
            raise HTTPException(401, 'Нужен демонстрационный токен')
        scopes = {'cost.read'} if role in {'R-01','R-02','R-03'} else set()
        scopes |= {'publication.read','publication.ack','facts.write'} if role == 'S-03' else set()
        scopes |= {'reports.read','reports.export'} if role == 'S-06' else set()
        scopes |= {'qa.read'} if role == 'S-07' else set()
        return Actor('demo-'+role, {role}, scopes, {DEMO_PORTFOLIO}, {DEMO_PROJECT}, {'employees/demo-1','employees/demo-2'} if role=='R-04' else {'employees/demo-1'})
    try:
        issuer = os.environ['OIDC_ISSUER'].rstrip('/'); audience = os.environ['OIDC_AUDIENCE']
        if not issuer.startswith('https://'): raise ValueError('HTTPS issuer required')
        client = request.app.state.jwks
        key = client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=audience,
                            issuer=issuer, options={'require':['exp','iat','sub','iss','aud']})
        roles = set(claims.get('realm_access',{}).get('roles',[]))
        roles |= set(claims.get('resource_access',{}).get(audience,{}).get('roles',[]))
        return Actor(claims['sub'], {ROLES.get(r,r) for r in roles}, set(claims.get('scope','').split()),
                     set(claims.get('portfolio_ids',[])), set(claims.get('project_ids',[])), set(claims.get('employee_ids',[])))
    except Exception:
        raise HTTPException(401, 'Недействительный токен') from None
