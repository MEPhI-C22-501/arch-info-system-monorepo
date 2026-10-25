"""Run inside the real Superset image, without exporting cookies or tokens."""
import json
import time
from superset.app import create_app

app = create_app()
with app.app_context():
    if (not app.config.get('HTML_SANITIZATION') or
        not app.config.get('FEATURE_FLAGS', {}).get('ESCAPE_MARKDOWN_HTML') or
        app.config.get('ENABLE_CORS')):
        raise RuntimeError('HTML sanitization/escaping and disabled CORS are required')
    from superset.db_engine_specs import get_engine_spec
    from reports_cube.dialect import CubeDialect
    from types import SimpleNamespace
    if get_engine_spec('reports_cube', 'psycopg2').__name__ != 'CubeEngineSpec':
        raise RuntimeError('Cube EngineSpec entry point was not selected')
    dialect = CubeDialect()
    protocol = SimpleNamespace(connection=SimpleNamespace(dbapi_connection=SimpleNamespace(server_version=140002)))
    if dialect._get_server_version_info(protocol) != (14, 2):
        raise RuntimeError('Cube protocol version was not read from libpq')
    direct = SimpleNamespace(connection=SimpleNamespace(server_version=140002))
    if dialect._get_server_version_info(direct) != (14, 2):
        raise RuntimeError('First-connect DBAPI proxy was not supported')
    if get_engine_spec('reports_cube', 'psycopg2').get_default_schema(object(), None) != 'public':
        raise RuntimeError('Cube schema discovery must not open a SQL connection')
    if get_engine_spec('postgresql', 'psycopg2').__name__ == 'CubeEngineSpec':
        raise RuntimeError('Ordinary PostgreSQL must not use the Cube adapter')
    from superset import security_manager
    user = security_manager.find_user(username='pilot-bootstrap')
    if not user: raise RuntimeError('Local test user missing')
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
        session['reports_token_exp'] = int(time.time())+60
    csrf = client.get('/api/v1/security/csrf_token/').get_json()['result']
    for origin in ['http://foreign.invalid', 'null', 'http://localhost:8088.foreign.invalid']:
        response = client.post('/api/v1/dashboard/', json={'dashboard_title': []},
                               headers={'Origin': origin, 'X-CSRFToken': csrf})
        if response.status_code != 403 or response.get_json().get('message') != 'Origin is not allowed':
            raise RuntimeError('Foreign-origin write with a valid CSRF token was accepted')
        if 'Access-Control-Allow-Origin' in response.headers:
            raise RuntimeError('Foreign Origin must not receive CORS permission')
    response = client.post('/api/v1/dashboard/', json={'dashboard_title': []},
                           headers={'Origin': 'http://localhost:8088', 'X-CSRFToken': csrf})
    if response.status_code not in {400, 422} or response.get_json().get('message') == 'Origin is not allowed':
        raise RuntimeError('Same-origin request must reach normal payload validation')
    for expiry, expected in [(int(time.time())+60, 200), (int(time.time())-1, 401), (None, 401)]:
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
            session['reports_token_exp'] = expiry
        response = client.get('/api/v1/me/')
        if response.status_code != expected:
            raise RuntimeError('Unexpected OIDC session expiry status')
    print(json.dumps({'check': 'bi_absolute_token_expiry_and_cube_adapter', 'expiry_cases': 3,
                      'adapter_cases': 5, 'origin_cases': 4, 'passed': True}))
