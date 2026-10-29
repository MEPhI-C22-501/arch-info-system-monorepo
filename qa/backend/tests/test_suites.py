"""Наборы: MANUAL и FILTER, «Smoke» и «Приёмка стенда», статусы (050, раздел 3а), права."""

import pytest

from app.auth import Role
from app.models import Environment, RunSchedule, TestSuite

pytestmark = pytest.mark.usefixtures("classifiers")

URL = "/api/v1/suites"
CASES = "/api/v1/test-cases"


@pytest.fixture
def case(client, auth):
    """case(module=..., actual=True) — кейс через API, по умолчанию актуальный."""

    def create(module="RM", actual=True, role=Role.TESTER, **fields):
        body = {
            "title": f"Кейс {module}",
            "module": module,
            "priority": "HIGH",
            "severity": "MAJOR",
            "type": "FUNCTIONAL",
            "steps": [{"action": "Запрос", "expectedResult": "200"}],
            **fields,
        }
        created = client.post(CASES, json=body, headers=auth(role)).json()
        if actual:
            client.post(
                f"{CASES}/{created['id']}/status", json={"status": "ACTUAL"}, headers=auth(role)
            )
        return created

    return create


def manual(name="Регресс RM", case_ids=(), **fields):
    return {"name": name, "kind": "MANUAL", "caseIds": [str(i) for i in case_ids], **fields}


def test_create_manual_suite(client, auth, case):
    a, b = case(), case(module="TT")

    response = client.post(URL, json=manual(case_ids=[b["id"], a["id"]]), headers=auth(Role.TESTER))

    assert response.status_code == 201
    suite = response.json()
    assert (suite["status"], suite["purpose"], suite["owner"]) == (
        "ACTIVE",
        "GENERAL",
        "demo-qa-tester",
    )
    assert suite["caseIds"] == [a["id"], b["id"]]  # по ключу
    assert suite["caseCount"] == 2
    assert suite["filter"] is None


def test_manual_suite_accepts_only_actual_cases(client, auth, case):
    draft = case(actual=False)

    response = client.post(URL, json=manual(case_ids=[draft["id"]]), headers=auth(Role.TESTER))

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "caseIds.0", "reason": "status:DRAFT"}]


def test_existing_member_stays_after_status_change(client, auth, case):
    a, b = case(), case()
    suite = client.post(URL, json=manual(case_ids=[a["id"]]), headers=auth(Role.TESTER)).json()
    client.post(
        f"{CASES}/{a['id']}/status", json={"status": "NEEDS_UPDATE"}, headers=auth(Role.TESTER)
    )

    response = client.put(
        f"{URL}/{suite['id']}", json=manual(case_ids=[a["id"], b["id"]]), headers=auth(Role.TESTER)
    )

    assert response.status_code == 200
    assert response.json()["caseIds"] == [a["id"], b["id"]]
    shrunk = client.put(
        f"{URL}/{suite['id']}", json=manual(case_ids=[b["id"]]), headers=auth(Role.TESTER)
    )
    assert shrunk.json()["caseIds"] == [b["id"]]


def test_filter_suite_selects_cases_by_condition(client, auth, case):
    case(module="RM")
    tt = case(module="TT")
    case(module="TT", actual=False)  # черновик тоже отбирается условием без status
    body = {"name": "Все TT", "kind": "FILTER", "filter": {"module": "TT", "status": "ACTUAL"}}

    suite = client.post(URL, json=body, headers=auth(Role.TESTER)).json()

    assert suite["filter"] == {
        "module": "TT",
        "status": "ACTUAL",
        "type": None,
        "epicRef": None,
        "automated": None,
        "q": None,
        "suiteId": None,
    }
    assert suite["caseIds"] == []
    assert suite["caseCount"] == 1
    listed = client.get(CASES, params={"suiteId": suite["id"]}, headers=auth(Role.VIEWER)).json()
    assert [item["id"] for item in listed["items"]] == [tt["id"]]


@pytest.mark.parametrize(
    "body, field, reason",
    [
        ({"kind": "FILTER"}, "filter", "required"),
        ({"kind": "FILTER", "filter": {}}, "filter", "required"),
        (
            {
                "kind": "FILTER",
                "filter": {"module": "RM"},
                "caseIds": ["00000000-0000-0000-0000-000000000001"],
            },
            "caseIds",
            "not_allowed:FILTER",
        ),
        ({"kind": "MANUAL", "filter": {"module": "RM"}}, "filter", "not_allowed:MANUAL"),
        (
            {"kind": "MANUAL", "caseIds": ["00000000-0000-0000-0000-000000000001"]},
            "caseIds.0",
            "not_found",
        ),
    ],
)
def test_suite_validation(client, auth, body, field, reason):
    response = client.post(URL, json={"name": "Набор", **body}, headers=auth(Role.TESTER))

    assert response.status_code == 422
    assert {"field": field, "reason": reason} in response.json()["errors"]


def test_unknown_filter_key_is_rejected(client, auth):
    body = {"name": "Набор", "kind": "FILTER", "filter": {"priority": "HIGH"}}
    assert client.post(URL, json=body, headers=auth(Role.TESTER)).status_code == 422


def test_suite_name_is_unique(client, auth):
    client.post(URL, json=manual(), headers=auth(Role.TESTER))

    response = client.post(URL, json=manual(), headers=auth(Role.TESTER))

    assert response.status_code == 422
    assert {"field": "name", "reason": "duplicate"} in response.json()["errors"]


def test_filter_may_reference_only_manual_suite(client, auth, case):
    a = case(role=Role.AUTOMATION, automated=True, autotestKey="rm/test_health.py::test_livez")
    case()
    acceptance = client.post(
        URL, json=manual("Приёмка стенда", [a["id"]], purpose="ACCEPTANCE"), headers=auth(Role.LEAD)
    ).json()
    smoke_body = {
        "name": "Smoke",
        "kind": "FILTER",
        "purpose": "SMOKE",
        "filter": {"suiteId": acceptance["id"], "automated": True},
    }

    smoke = client.post(URL, json=smoke_body, headers=auth(Role.LEAD)).json()
    nested = {"name": "Вложенный", "kind": "FILTER", "filter": {"suiteId": smoke["id"]}}

    assert smoke["caseCount"] == 1
    response = client.post(URL, json=nested, headers=auth(Role.TESTER))
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "filter.suiteId", "reason": "not_manual"}]


# --- «Smoke» и «Приёмка стенда» ---------------------------------------------------------


@pytest.mark.parametrize("purpose", ["SMOKE", "ACCEPTANCE"])
def test_special_suite_is_single_and_lead_only(client, auth, purpose):
    body = manual(f"Особый {purpose}", purpose=purpose)

    assert client.post(URL, json=body, headers=auth(Role.TESTER)).status_code == 403
    assert client.post(URL, json=body, headers=auth(Role.LEAD)).status_code == 201
    second = client.post(URL, json=manual("Второй", purpose=purpose), headers=auth(Role.LEAD))
    assert second.status_code == 422
    assert second.json()["errors"] == [{"field": "purpose", "reason": f"exists:Особый {purpose}"}]


def test_special_suite_name_and_purpose_are_fixed(client, auth):
    smoke = client.post(URL, json=manual("Smoke", purpose="SMOKE"), headers=auth(Role.LEAD)).json()

    tester = client.put(f"{URL}/{smoke['id']}", json=manual("Smoke"), headers=auth(Role.TESTER))
    renamed = client.put(f"{URL}/{smoke['id']}", json=manual("Дым"), headers=auth(Role.LEAD))
    repurposed = client.put(
        f"{URL}/{smoke['id']}", json=manual("Smoke", purpose="GENERAL"), headers=auth(Role.LEAD)
    )

    assert tester.status_code == 403
    assert {"field": "name", "reason": "fixed:SMOKE"} in renamed.json()["errors"]
    assert {"field": "purpose", "reason": "immutable"} in repurposed.json()["errors"]


# --- Архив ------------------------------------------------------------------------------


def test_archive_and_restore(client, auth, db_session):
    suite = client.post(URL, json=manual(), headers=auth(Role.TESTER, "ivanov")).json()
    environment = Environment(code="staging", name="Стенд", base_urls={})
    db_session.add(environment)
    db_session.flush()
    schedule = RunSchedule(suite_id=suite["id"], environment_id=environment.id, cron="0 6 * * *")
    db_session.add(schedule)
    db_session.flush()

    archived = client.post(f"{URL}/{suite['id']}/archive", headers=auth(Role.TESTER, "ivanov"))
    again = client.post(f"{URL}/{suite['id']}/archive", headers=auth(Role.TESTER, "ivanov"))
    restored = client.post(f"{URL}/{suite['id']}/restore", headers=auth(Role.TESTER, "ivanov"))
    restored_again = client.post(f"{URL}/{suite['id']}/restore", headers=auth(Role.LEAD))

    assert archived.json()["status"] == "ARCHIVED"
    db_session.refresh(schedule)
    assert schedule.is_active is False  # расписания архивного набора отключаются
    assert again.status_code == 409 and again.json()["code"] == "INVALID_TRANSITION"
    assert restored.json()["status"] == "ACTIVE"
    assert restored_again.json()["code"] == "INVALID_TRANSITION"


def test_only_owner_or_lead_archives(client, auth):
    suite = client.post(URL, json=manual(), headers=auth(Role.TESTER, "ivanov")).json()

    assert (
        client.post(f"{URL}/{suite['id']}/archive", headers=auth(Role.TESTER, "petrov")).status_code
        == 403
    )
    assert client.post(f"{URL}/{suite['id']}/archive", headers=auth(Role.LEAD)).status_code == 200


def test_special_suite_archived_only_by_lead(client, auth, db_session):
    suite = TestSuite(name="Smoke", kind="MANUAL", status="ACTIVE", purpose="SMOKE", owner="ivanov")
    db_session.add(suite)
    db_session.flush()

    assert (
        client.post(f"{URL}/{suite.id}/archive", headers=auth(Role.TESTER, "ivanov")).status_code
        == 403
    )
    assert client.post(f"{URL}/{suite.id}/archive", headers=auth(Role.LEAD)).status_code == 200


# --- Список и права -----------------------------------------------------------------------


def test_list_filters_and_pagination(client, auth):
    for name in ("А", "Б", "В"):
        client.post(URL, json=manual(name), headers=auth(Role.TESTER))
    client.post(URL, json=manual("Smoke", purpose="SMOKE"), headers=auth(Role.LEAD))
    archived = client.post(URL, json=manual("Г"), headers=auth(Role.TESTER)).json()
    client.post(f"{URL}/{archived['id']}/archive", headers=auth(Role.TESTER))

    def names(**params):
        return [
            s["name"]
            for s in client.get(URL, params=params, headers=auth(Role.VIEWER)).json()["items"]
        ]

    assert names(status="ARCHIVED") == ["Г"]
    assert names(purpose="SMOKE") == ["Smoke"]
    page = client.get(URL, params={"pageSize": 2, "page": 3}, headers=auth(Role.VIEWER)).json()
    assert ([s["name"] for s in page["items"]], page["totalPages"]) == (["Г"], 3)


@pytest.mark.parametrize(
    "role, can_read, can_write",
    [
        (Role.VIEWER, True, False),
        (Role.TESTER, True, True),
        (Role.AUTOMATION, True, True),
        (Role.LEAD, True, True),
        (Role.ADMIN, True, False),
        (Role.CI, False, False),
        (Role.REPORTS_READER, False, False),
    ],
)
def test_role_matrix(client, auth, role, can_read, can_write):
    suite = client.post(URL, json=manual("Общий"), headers=auth(Role.LEAD)).json()

    read = {
        client.get(URL, headers=auth(role)).status_code,
        client.get(f"{URL}/{suite['id']}", headers=auth(role)).status_code,
    }
    create = client.post(URL, json=manual("Новый"), headers=auth(role)).status_code
    edit = client.put(f"{URL}/{suite['id']}", json=manual("Общий"), headers=auth(role)).status_code

    assert read == ({200} if can_read else {403})
    assert create == (201 if can_write else 403)
    assert edit == (200 if can_write else 403)


def test_unknown_suite_is_404(client, auth):
    response = client.get(f"{URL}/00000000-0000-0000-0000-000000000001", headers=auth(Role.VIEWER))
    assert response.status_code == 404
