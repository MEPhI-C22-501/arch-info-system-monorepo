"""Классификаторы и окружения: ведёт администратор, используемое значение не отключается."""

import uuid

import pytest

from app.auth import Role
from app.models import (
    Defect,
    RunSchedule,
    TestCaseTemplate,
    TestRun,
    TestSuite,
)

pytestmark = pytest.mark.usefixtures("classifiers")

CLASSIFIERS = "/api/v1/admin/classifiers"
ENVIRONMENTS = "/api/v1/admin/environments"


def create_case(client, auth, **fields):
    body = {
        "title": "Кейс",
        "module": "RM",
        "priority": "LOW",
        "severity": "TRIVIAL",
        "type": "REGRESSION",
        "steps": [{"action": "Запрос", "expectedResult": "200"}],
        **fields,
    }
    return client.post("/api/v1/test-cases", json=body, headers=auth(Role.TESTER)).json()


def deactivate(client, auth, kind, code):
    return client.put(
        f"{CLASSIFIERS}/{kind}/{code}", json={"isActive": False}, headers=auth(Role.ADMIN)
    )


# --- Классификаторы ---------------------------------------------------------------------


def test_list_classifiers_in_order(client, auth):
    response = client.get(CLASSIFIERS, params={"kind": "SEVERITY"}, headers=auth(Role.VIEWER))

    codes = [item["code"] for item in response.json()["items"]]
    assert codes == ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "TRIVIAL"]


def test_add_and_rename_value(client, auth):
    created = client.post(
        CLASSIFIERS,
        json={
            "kind": "CASE_TYPE",
            "code": "EXPLORATORY",
            "name": "Исследовательский",
            "sortOrder": 6,
        },
        headers=auth(Role.ADMIN),
    )
    renamed = client.put(
        f"{CLASSIFIERS}/SEVERITY/MAJOR", json={"name": "Major"}, headers=auth(Role.ADMIN)
    )

    assert created.status_code == 201
    assert renamed.json() == {
        "kind": "SEVERITY",
        "code": "MAJOR",
        "name": "Major",
        "sortOrder": 3,
        "isActive": True,
    }


@pytest.mark.parametrize(
    "body, field, reason",
    [
        ({"kind": "SEVERITY", "code": "SHOWSTOPPER"}, "kind", "fixed:SEVERITY"),
        ({"kind": "PRIORITY", "code": "HIGH"}, "code", "duplicate"),
    ],
)
def test_classifier_validation(client, auth, body, field, reason):
    response = client.post(CLASSIFIERS, json={"name": "X", **body}, headers=auth(Role.ADMIN))

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": field, "reason": reason}]


def test_bad_code_format_is_422(client, auth):
    body = {"kind": "PRIORITY", "code": "low priority", "name": "X"}
    assert client.post(CLASSIFIERS, json=body, headers=auth(Role.ADMIN)).status_code == 422


def test_unused_value_can_be_disabled(client, auth):
    response = deactivate(client, auth, "PRIORITY", "MEDIUM")

    assert response.status_code == 200
    assert response.json()["isActive"] is False


def test_value_used_by_case_cannot_be_disabled(client, auth):
    case = create_case(client, auth)

    response = deactivate(client, auth, "PRIORITY", "LOW")

    assert response.status_code == 409
    assert response.json()["code"] == "VALUE_IN_USE"
    assert response.json()["errors"] == [
        {"field": "isActive", "reason": f"used-by:case:{case['key']}"}
    ]


def test_value_of_archived_case_or_old_version_is_free(client, auth):
    case = create_case(client, auth)
    client.put(
        f"/api/v1/test-cases/{case['id']}",
        json={"title": "Кейс", "module": "RM", "type": "FUNCTIONAL"},
        headers=auth(Role.TESTER),
    )

    assert deactivate(client, auth, "CASE_TYPE", "REGRESSION").status_code == 200


def test_value_used_by_active_template_or_open_defect(client, auth, db_session):
    db_session.add(TestCaseTemplate(name="Шаблон", body={"type": "SMOKE"}))
    db_session.add(
        Defect(
            key="DEF-01",
            origin="MANUAL",
            title="Падение",
            actual_result="500",
            severity="BLOCKER",
            proposed_priority="HIGH",
            status="OPEN",
            author="t",
        )
    )
    db_session.flush()

    smoke = deactivate(client, auth, "CASE_TYPE", "SMOKE").json()
    blocker = deactivate(client, auth, "SEVERITY", "BLOCKER").json()

    assert smoke["errors"] == [{"field": "isActive", "reason": "used-by:template:Шаблон"}]
    assert blocker["errors"] == [{"field": "isActive", "reason": "used-by:defect:DEF-01"}]


def test_unknown_classifier_is_404(client, auth):
    response = client.put(
        f"{CLASSIFIERS}/PRIORITY/NOPE", json={"name": "X"}, headers=auth(Role.ADMIN)
    )
    assert response.status_code == 404


# --- Окружения --------------------------------------------------------------------------


def environment(code="staging", **fields):
    return {
        "code": code,
        "name": "Общий стенд",
        "baseUrls": {"task-tracker": "http://task-tracker:8080"},
        **fields,
    }


def test_create_and_update_environment(client, auth):
    created = client.post(ENVIRONMENTS, json=environment(), headers=auth(Role.ADMIN)).json()

    updated = client.put(
        f"{ENVIRONMENTS}/{created['id']}",
        json={"name": "Staging", "baseUrls": {"reports": "https://reports.local"}},
        headers=auth(Role.ADMIN),
    ).json()

    assert created["baseUrls"] == {"task-tracker": "http://task-tracker:8080"}
    assert (updated["code"], updated["name"], updated["baseUrls"]) == (
        "staging",
        "Staging",
        {"reports": "https://reports.local"},
    )
    listed = client.get(ENVIRONMENTS, headers=auth(Role.TESTER)).json()["items"]
    assert [e["code"] for e in listed] == ["staging"]


@pytest.mark.parametrize(
    "body",
    [
        environment(code="Staging"),
        environment(baseUrls={"task-tracker": "ftp://x"}),
        environment(baseUrls={"Task Tracker": "http://x"}),
    ],
)
def test_environment_validation(client, auth, body):
    assert client.post(ENVIRONMENTS, json=body, headers=auth(Role.ADMIN)).status_code == 422


def test_environment_code_is_unique_and_immutable(client, auth):
    created = client.post(ENVIRONMENTS, json=environment(), headers=auth(Role.ADMIN)).json()

    duplicate = client.post(ENVIRONMENTS, json=environment(), headers=auth(Role.ADMIN))
    renamed = client.put(
        f"{ENVIRONMENTS}/{created['id']}", json={"code": "prod"}, headers=auth(Role.ADMIN)
    )

    assert duplicate.json()["errors"] == [{"field": "code", "reason": "duplicate"}]
    assert renamed.json()["errors"] == [{"field": "code", "reason": "immutable"}]


def test_environment_in_use_cannot_be_disabled(client, auth, db_session):
    created = client.post(ENVIRONMENTS, json=environment(), headers=auth(Role.ADMIN)).json()
    env_id = uuid.UUID(created["id"])
    suite = TestSuite(name="Набор", kind="MANUAL", status="ACTIVE", purpose="GENERAL", owner="t")
    db_session.add(suite)
    db_session.flush()
    run = TestRun(
        key="RUN-07",
        suite_id=suite.id,
        environment_id=env_id,
        status="IN_PROGRESS",
        trigger="CI",
        started_by="t",
    )
    schedule = RunSchedule(suite_id=suite.id, environment_id=env_id, cron="0 6 * * *")
    db_session.add_all([run, schedule])
    db_session.flush()
    url = f"{ENVIRONMENTS}/{created['id']}"

    busy = client.put(url, json={"isActive": False}, headers=auth(Role.ADMIN))
    run.status = "COMPLETED"
    schedule.is_active = False
    db_session.flush()
    free = client.put(url, json={"isActive": False}, headers=auth(Role.ADMIN))

    assert busy.status_code == 409
    assert busy.json()["code"] == "VALUE_IN_USE"
    assert [e["reason"] for e in busy.json()["errors"]] == [
        "used-by:run:RUN-07",
        f"used-by:schedule:{schedule.id}",
    ]
    assert free.json()["isActive"] is False


def test_unknown_environment_is_404(client, auth):
    response = client.put(
        f"{ENVIRONMENTS}/{uuid.uuid4()}", json={"name": "X"}, headers=auth(Role.ADMIN)
    )
    assert response.status_code == 404


# --- Права ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role, can_read, can_write",
    [
        (Role.VIEWER, True, False),
        (Role.TESTER, True, False),
        (Role.AUTOMATION, True, False),
        (Role.LEAD, True, False),
        (Role.ADMIN, True, True),
        (Role.CI, False, False),
        (Role.REPORTS_READER, False, False),
    ],
)
def test_role_matrix(client, auth, role, can_read, can_write):
    reads = {
        client.get(CLASSIFIERS, headers=auth(role)).status_code,
        client.get(ENVIRONMENTS, headers=auth(role)).status_code,
    }
    writes = {
        client.post(
            CLASSIFIERS, json={"kind": "PRIORITY", "code": "P0", "name": "P0"}, headers=auth(role)
        ).status_code,
        client.post(ENVIRONMENTS, json=environment(), headers=auth(role)).status_code,
        client.put(
            f"{CLASSIFIERS}/PRIORITY/HIGH", json={"name": "H"}, headers=auth(role)
        ).status_code,
    }

    assert reads == ({200} if can_read else {403})
    assert writes == ({201, 200} if can_write else {403})
