import pytest
from server.oidc import endpoint


@pytest.mark.parametrize('environment,enabled,url,accepted', [
    ('development','true','http://localhost:8081/realms/planning',True),
    ('development','true','http://keycloak:8080/realms/planning',True),
    ('development','false','http://localhost:8081/realms/planning',False),
    ('staging','true','http://localhost:8081/realms/planning',False),
    ('production','true','http://keycloak:8080/realms/planning',False),
    ('development','true','http://external.example/realm',False),
    ('production','false','https://identity.example/realm',True),
    ('development','true','http://user:password@localhost:8081/realm',False),
])
def test_oidc_http_is_explicit_local_development_only(monkeypatch,environment,enabled,url,accepted):
    monkeypatch.setenv('APP_ENV',environment)
    monkeypatch.setenv('OIDC_LOCAL_HTTP',enabled)
    if accepted:
        assert endpoint(url)==url
    else:
        with pytest.raises(ValueError):endpoint(url)
