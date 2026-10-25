"""HTTP adapter for /api/v1. Authentication is shared with the legacy pilot."""
import json
import os
import uuid
from urllib.parse import parse_qs, urlsplit
import jwt
from db import Database
from product_service import Service
from product_store import audit, remember
from report_engine import Problem


def handle(handler):
    path=urlsplit(handler.path)
    if not path.path.startswith('/api/v1/'): return False
    correlation=handler.headers.get('X-Correlation-Id','')
    try: correlation=str(uuid.UUID(correlation))
    except (ValueError,TypeError): correlation=str(uuid.uuid4())
    headers={'X-Correlation-Id':correlation,'Content-Type':'application/json'}
    status,body=503,{'code':'DEPENDENCY_UNAVAILABLE'};db=None;claims=None
    try:
        if path.path in {'/api/v1/health/livez','/api/v1/health/readyz'} and handler.command=='GET':
            status,body=200,{'status':'ok'}
            if path.path.endswith('/readyz'):
                db=Database(os.environ['REPORTS_DATABASE_URL'])
                db.execute('SELECT 1 FROM app.audit_log LIMIT 1')
        else:
            token=handler.headers.get('Authorization','')
            if not token.startswith('Bearer '): raise Problem(401,'UNAUTHENTICATED')
            key=handler.jwks.get_signing_key_from_jwt(token[7:]).key
            claims=jwt.decode(token[7:],key,algorithms=['RS256'],audience='reports',issuer=os.environ['REPORTS_OIDC_ISSUER'],
                options={'require':['exp','iat','sub','iss','aud']})
            parsed=parse_qs(path.query,keep_blank_values=True)
            if any(len(v)!=1 for v in parsed.values()): raise Problem(422,'INVALID_PARAMETER')
            params={k:v[0] for k,v in parsed.items()}
            payload=None
            if handler.command in {'POST','PATCH'}:
                if handler.headers.get('Content-Type','').split(';')[0]!='application/json': raise Problem(400,'MALFORMED_REQUEST')
                try:
                    size=int(handler.headers.get('Content-Length','0'))
                    if not 0<size<=262144: raise ValueError()
                    payload=json.loads(handler.rfile.read(size),parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
                except (ValueError,UnicodeDecodeError): raise Problem(400,'MALFORMED_REQUEST') from None
            db=Database(os.environ['REPORTS_DATABASE_URL'])
            with db.transaction():
                service=Service(db,claims,correlation)
                remember(db,claims)
                status,body,extra=service.route(handler.command,path.path[len('/api/v1/'):],payload,params,dict(handler.headers))
                if body is not None and not isinstance(body,bytes):
                    if len(json.dumps(body,ensure_ascii=False,allow_nan=False).encode())>16*1024*1024: raise Problem(422,'RESULT_TOO_LARGE')
                headers.update(extra)
                report_id=path.path.split('/')[4] if path.path.startswith('/api/v1/reports/R-') else None
                audit(db,claims['sub'],handler.command+' '+path.path[len('/api/v1/'):],report_id,
                      payload,resource=(body.get('exportId') or body.get('subscriptionId')) if isinstance(body,dict) else None,
                      correlation=correlation)
    except (jwt.InvalidTokenError,jwt.PyJWKClientError): status,body=401,{'code':'UNAUTHENTICATED'}
    except Problem as error: status,body=error.status,{'code':error.code}
    except PermissionError: status,body=403,{'code':'FORBIDDEN'}
    except Exception: status,body=503,{'code':'DEPENDENCY_UNAVAILABLE'}
    finally:
        if db is not None:
            if status>=400 and claims is not None:
                try:
                    with db.transaction(): audit(db,claims['sub'],'REQUEST_DENIED',result=str(status),correlation=correlation)
                except Exception: status,body=503,{'code':'AUDIT_UNAVAILABLE'}
            db.close()
    if status>=400:
        body=dict(body,type='https://reports.arch.local/errors/'+body['code'].lower().replace('_','-'),
                  title=body['code'],status=status,correlationId=correlation)
        headers['Content-Type']='application/problem+json'
    raw=body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False,allow_nan=False).encode() if body is not None else b''
    handler.send_response(status)
    for key,value in dict(headers,**{'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}).items():
        handler.send_header(key,value)
    handler.end_headers();handler.wfile.write(raw)
    return True
