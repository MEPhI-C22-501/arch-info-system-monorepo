"""Общие правила API из 130: формат ошибок, X-Request-Id, роли, страницы, ключи."""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import Principal, Role, require_roles
from app.errors import conflict
from app.keys import next_key
from app.main import create_app
from app.models import Environment
from app.schemas import ApiModel, PageParams, paginate


@pytest.fixture
def probe() -> TestClient:
    app = create_app()

    @app.get("/probe/lead")
    def lead_only(principal: Principal = Depends(require_roles(Role.LEAD))):
        return {"subject": principal.subject}

    @app.get("/probe/crash")
    def crash():
        raise RuntimeError("boom")

    @app.get("/probe/conflict")
    def invalid_transition():
        raise conflict("INVALID_TRANSITION", "Недопустимый переход")

    @app.get("/probe/page")
    def page(params: PageParams = Depends()):
        return {"page": params.page, "pageSize": params.page_size}

    return TestClient(app, raise_server_exceptions=False)


def test_unknown_path_uses_error_format(probe):
    response = probe.get("/api/v1/nothing")
    body = response.json()
    assert response.status_code == 404
    assert body["code"] == "NOT_FOUND"
    assert body["correlationId"] == response.headers["X-Request-Id"]
    assert body["errors"] == []


def test_incoming_request_id_is_echoed(probe):
    response = probe.get("/livez", headers={"X-Request-Id": "pipeline-42"})
    assert response.headers["X-Request-Id"] == "pipeline-42"


def test_unhandled_error_is_internal(probe):
    response = probe.get("/probe/crash")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
    assert response.headers["X-Request-Id"]


def test_api_error_keeps_code(probe):
    response = probe.get("/probe/conflict")
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"


def test_validation_error_lists_fields(probe):
    response = probe.get("/probe/page", params={"pageSize": 201})
    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_FAILED"
    assert body["errors"][0]["field"] == "pageSize"


def test_page_defaults(probe):
    assert probe.get("/probe/page").json() == {"page": 1, "pageSize": 50}


@pytest.mark.parametrize("header", [None, "Bearer garbage", "Bearer demo-qa-boss"])
def test_missing_or_invalid_token_is_401(probe, header):
    headers = {"Authorization": header} if header else {}
    response = probe.get("/probe/lead", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_wrong_role_is_403(probe, auth):
    response = probe.get("/probe/lead", headers=auth(Role.TESTER))
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_demo_token_carries_user(probe, auth):
    assert probe.get("/probe/lead", headers=auth(Role.LEAD, "ivanov")).json() == {
        "subject": "ivanov"
    }
    assert probe.get("/probe/lead", headers=auth(Role.LEAD)).json() == {"subject": "demo-qa-lead"}


class EnvironmentOut(ApiModel):
    code: str
    is_active: bool


def test_paginate(db_session):
    db_session.add_all(
        Environment(code=f"env-{i}", name=f"Env {i}", base_urls={}) for i in range(5)
    )
    db_session.flush()
    stmt = select(Environment).order_by(Environment.code)

    page = paginate(db_session, stmt, PageParams(page=2, page_size=2), EnvironmentOut)

    assert [item.code for item in page.items] == ["env-2", "env-3"]
    assert page.total_pages == 3
    assert page.model_dump(by_alias=True)["items"][0] == {"code": "env-2", "isActive": True}
    assert set(page.model_dump(by_alias=True)) == {"items", "page", "pageSize", "totalPages"}


def test_next_key_counts_per_prefix(db_session):
    assert next_key(db_session, "TC-RM") == "TC-RM-01"
    assert next_key(db_session, "TC-RM") == "TC-RM-02"
    assert next_key(db_session, "RUN") == "RUN-01"
