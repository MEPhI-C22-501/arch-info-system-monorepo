"""Планы: привязка, состав, статусы, сводка (050, раздел 3; 130)."""

import pytest
from factories import (
    PLANS,
    RUNS,
    SUITES,
    change_case_status,
    environment,
    fail,
    finish_run,
    new_case,
    new_plan,
    record,
    run_results,
)
from sqlalchemy import select

from app.auth import Role
from app.models import TestPlan, TestRun

pytestmark = pytest.mark.usefixtures("classifiers")


@pytest.fixture
def lead(auth):
    return auth(Role.LEAD)


@pytest.fixture
def dev(db_session):
    return environment(db_session)


@pytest.fixture
def cases(client, lead):
    return [new_case(client, lead), new_case(client, lead, module="TT")]


def plan_run(client, headers, plan):
    body = {"planId": plan["id"], "environment": "dev", "start": True}
    created = client.post(RUNS, json=body, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


def test_create_plan_in_draft(client, lead):
    plan = new_plan(
        client,
        lead,
        name="Релиз 1.0",
        scopeKind="RELEASE",
        planningProjectId="p-1",
        planningReleaseId="r-1",
        planningPlanVersionId="v-1",
        planningMilestoneId="m-1",
        trackerIterationId="it-1",
    )

    assert plan["key"] == "TP-01"
    assert (plan["status"], plan["refsVerified"], plan["caseCount"]) == ("DRAFT", False, 0)
    assert client.get(f"{PLANS}/{plan['id']}", headers=lead).json() == plan


@pytest.mark.parametrize(
    "fields, field",
    [
        ({"scopeKind": "RELEASE", "planningProjectId": "p"}, "planningReleaseId"),
        ({"scopeKind": "RELEASE", "planningReleaseId": "r"}, "planningProjectId"),
        (
            {"scopeKind": "RELEASE", "planningProjectId": " ", "planningReleaseId": "r"},
            "planningProjectId",
        ),
        ({"scopeKind": "PROJECT"}, "planningProjectId"),
        ({"startDate": "2026-12-01", "endDate": "2026-11-01"}, "endDate"),
    ],
)
def test_plan_validation(client, lead, fields, field):
    body = {
        "name": "П",
        "scopeKind": "MODULE",
        "owner": "ivanov",
        "startDate": "2026-11-01",
        "endDate": "2026-11-30",
        **fields,
    }

    response = client.post(PLANS, json=body, headers=lead)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"
    assert field in {error["field"] for error in response.json()["errors"]}


def test_update_plan_resets_verified_refs(client, lead, db_session):
    plan = new_plan(client, lead)
    db_session.get(TestPlan, plan["id"]).refs_verified = True
    db_session.flush()
    body = {
        "name": "Новое имя",
        "scopeKind": "PROJECT",
        "owner": "petrov",
        "startDate": "2026-11-02",
        "endDate": "2026-11-03",
        "planningProjectId": "p-2",
    }

    updated = client.put(f"{PLANS}/{plan['id']}", json=body, headers=lead).json()

    assert (updated["name"], updated["owner"], updated["scopeRef"]) == (
        "Новое имя",
        "petrov",
        None,
    )
    assert (updated["key"], updated["refsVerified"]) == (plan["key"], False)
    assert updated["updatedAt"] >= plan["updatedAt"]


@pytest.mark.parametrize("action", ["complete", "cancel"])
def test_closed_plan_is_immutable(client, lead, cases, action):
    plan = new_plan(client, lead, cases, activate=True)
    url = f"{PLANS}/{plan['id']}"
    client.post(f"{url}/{action}", headers=lead)
    body = {
        "name": "Н",
        "scopeKind": "MODULE",
        "owner": "o",
        "startDate": "2026-11-01",
        "endDate": "2026-11-02",
    }
    extra = new_case(client, lead)

    for response in (
        client.put(url, json=body, headers=lead),
        client.post(f"{url}/cases", json={"ids": [extra["id"]]}, headers=lead),
        client.delete(f"{url}/cases/{cases[0]['id']}", headers=lead),
    ):
        assert (response.status_code, response.json()["code"]) == (409, "PLAN_CLOSED")


def test_add_cases_by_ids(client, lead, cases):
    plan = new_plan(client, lead)

    added = client.post(
        f"{PLANS}/{plan['id']}/cases", json={"ids": [c["id"] for c in cases]}, headers=lead
    ).json()
    repeated = client.post(
        f"{PLANS}/{plan['id']}/cases", json={"ids": [cases[0]["id"]]}, headers=lead
    ).json()

    assert added["caseCount"] == repeated["caseCount"] == 2
    assert added["caseIds"] == [c["id"] for c in sorted(cases, key=lambda c: c["key"])]


@pytest.mark.parametrize("status", ["DRAFT", "NEEDS_UPDATE", "ARCHIVED"])
def test_not_actual_case_is_rejected_with_list(client, lead, cases, status):
    bad = new_case(client, lead, status=status)
    plan = new_plan(client, lead)
    url = f"{PLANS}/{plan['id']}/cases"

    response = client.post(url, json={"ids": [cases[0]["id"], bad["id"]]}, headers=lead)

    assert (response.status_code, response.json()["code"]) == (409, "CASE_NOT_ACTUAL")
    assert response.json()["errors"] == [{"field": "ids.1", "reason": f"{bad['key']}:{status}"}]
    assert client.get(f"{PLANS}/{plan['id']}", headers=lead).json()["caseCount"] == 0


def test_filter_selecting_draft_is_rejected(client, lead, cases):
    draft = new_case(client, lead, status="DRAFT")
    plan = new_plan(client, lead)
    url = f"{PLANS}/{plan['id']}/cases"

    rejected = client.post(url, json={"filter": {"module": "RM"}}, headers=lead)
    accepted = client.post(url, json={"filter": {"module": "RM", "status": "ACTUAL"}}, headers=lead)

    assert rejected.json()["code"] == "CASE_NOT_ACTUAL"
    assert rejected.json()["errors"] == [{"field": "filter", "reason": f"{draft['key']}:DRAFT"}]
    assert accepted.json()["caseIds"] == [cases[0]["id"]]


def test_case_already_in_plan_stays_after_status_change(client, lead, cases):
    plan = new_plan(client, lead, cases)
    change_case_status(client, lead, cases[0], "NEEDS_UPDATE")

    response = client.post(
        f"{PLANS}/{plan['id']}/cases", json={"ids": [cases[0]["id"]]}, headers=lead
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "body, field",
    [
        ({}, "ids"),
        ({"ids": [], "filter": {"module": "RM"}}, "ids"),
        ({"filter": {}}, "filter"),
        ({"ids": ["00000000-0000-0000-0000-000000000000"]}, "ids.0"),
        ({"ids": [], "saveAsSuite": "Н"}, "saveAsSuite"),
    ],
)
def test_add_cases_validation(client, lead, body, field):
    plan = new_plan(client, lead)

    response = client.post(f"{PLANS}/{plan['id']}/cases", json=body, headers=lead)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field


def test_save_filter_as_suite(client, lead, cases):
    plan = new_plan(client, lead)
    body = {"filter": {"module": "RM", "status": "ACTUAL"}, "saveAsSuite": "Кейсы RM"}

    added = client.post(f"{PLANS}/{plan['id']}/cases", json=body, headers=lead)

    assert added.json()["caseIds"] == [cases[0]["id"]]
    suites = client.get(SUITES, headers=lead).json()["items"]
    assert [(s["name"], s["kind"], s["caseCount"]) for s in suites] == [("Кейсы RM", "FILTER", 1)]


def test_duplicate_suite_name_keeps_plan_unchanged(client, lead, cases):
    plan = new_plan(client, lead)
    body = {"filter": {"module": "RM", "status": "ACTUAL"}, "saveAsSuite": "Дубль"}
    client.post(SUITES, json={"name": "Дубль", "kind": "MANUAL", "caseIds": []}, headers=lead)

    response = client.post(f"{PLANS}/{plan['id']}/cases", json=body, headers=lead)

    assert response.status_code == 422
    assert client.get(f"{PLANS}/{plan['id']}", headers=lead).json()["caseCount"] == 0


def test_remove_case(client, lead, cases):
    plan = new_plan(client, lead, cases, activate=True)
    url = f"{PLANS}/{plan['id']}/cases/{cases[0]['id']}"

    assert client.delete(url, headers=lead).status_code == 204
    assert client.delete(url, headers=lead).status_code == 404
    assert client.get(f"{PLANS}/{plan['id']}", headers=lead).json()["caseIds"] == [cases[1]["id"]]


def test_activate(client, lead, cases):
    plan = new_plan(client, lead)
    url = f"{PLANS}/{plan['id']}"

    empty = client.post(f"{url}/activate", headers=lead)
    assert (empty.status_code, empty.json()["code"]) == (409, "PLAN_EMPTY")
    client.post(f"{url}/cases", json={"ids": [cases[0]["id"]]}, headers=lead)
    assert client.post(f"{url}/activate", headers=lead).json()["status"] == "ACTIVE"


TRANSITIONS = {
    "DRAFT": {"activate", "cancel"},
    "ACTIVE": {"complete", "cancel"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
TARGET = {"activate": "ACTIVE", "complete": "COMPLETED", "cancel": "CANCELLED"}


def plan_in(client, lead, cases, status):
    plan = new_plan(client, lead, cases, activate=status != "DRAFT")
    if status in ("COMPLETED", "CANCELLED"):
        action = "complete" if status == "COMPLETED" else "cancel"
        assert client.post(f"{PLANS}/{plan['id']}/{action}", headers=lead).status_code == 200
    return plan


@pytest.mark.parametrize("source", TRANSITIONS)
@pytest.mark.parametrize("action", TARGET)
def test_every_transition(client, lead, cases, source, action):
    plan = plan_in(client, lead, cases, source)

    response = client.post(f"{PLANS}/{plan['id']}/{action}", headers=lead)

    if action in TRANSITIONS[source]:
        assert (response.status_code, response.json()["status"]) == (200, TARGET[action])
    else:
        assert (response.status_code, response.json()["code"]) == (409, "INVALID_TRANSITION")


def test_complete_requires_finished_runs(client, lead, dev, cases):
    plan = new_plan(client, lead, cases, activate=True)
    run = plan_run(client, lead, plan)
    url = f"{PLANS}/{plan['id']}/complete"

    blocked = client.post(url, headers=lead)
    assert (blocked.status_code, blocked.json()["code"]) == (409, "RUNS_NOT_FINISHED")
    assert blocked.json()["errors"] == [{"field": "runs", "reason": f"unfinished:{run['key']}"}]

    finish_run(client, lead, run)
    assert client.post(url, headers=lead).json()["status"] == "COMPLETED"


def test_cancel_aborts_unfinished_runs(client, lead, dev, cases, db_session):
    plan = new_plan(client, lead, cases, activate=True)
    finished = plan_run(client, lead, plan)
    finish_run(client, lead, finished)
    running = plan_run(client, lead, plan)
    waiting = client.post(
        RUNS, json={"planId": plan["id"], "environment": "dev"}, headers=lead
    ).json()

    assert client.post(f"{PLANS}/{plan['id']}/cancel", headers=lead).status_code == 200

    statuses = dict(db_session.execute(select(TestRun.key, TestRun.status)).tuples().all())
    assert statuses == {
        finished["key"]: "COMPLETED",
        running["key"]: "ABORTED",
        waiting["key"]: "ABORTED",
    }
    aborted = client.get(f"{RUNS}/{running['id']}", headers=lead).json()
    assert aborted["finishedAt"]


def test_summary(client, lead, dev, cases):
    third = new_case(client, lead, module="PS")
    plan = new_plan(client, lead, [*cases, third], activate=True)
    run = plan_run(client, lead, plan)
    results = run_results(client, lead, run)
    failed = fail(client, lead, run, results[cases[0]["key"]], "500")
    record(client, lead, run, results[cases[1]["key"]], status="PASSED")

    summary = client.get(f"{PLANS}/{plan['id']}/summary", headers=lead).json()

    assert summary["planId"] == plan["id"]
    assert summary["counters"] == {
        "total": 3,
        "passed": 1,
        "failed": 1,
        "blocked": 0,
        "skipped": 0,
        "notRun": 1,
    }
    by_key = {item["testCaseKey"]: item for item in summary["cases"]}
    assert by_key[cases[0]["key"]]["lastResult"]["runKey"] == run["key"]
    assert by_key[third["key"]]["lastResult"] is None
    assert [d["key"] for d in summary["openDefects"]] == [failed["defect"]["key"]]
    assert summary["openDefects"][0]["testCaseId"] == cases[0]["id"]


def test_lists_and_pagination(client, lead):
    first = new_plan(client, lead, trackerIterationId="it-1")
    second = new_plan(
        client,
        lead,
        scopeKind="RELEASE",
        planningProjectId="p-1",
        planningReleaseId="r-1",
    )

    def keys(**params):
        page = client.get(PLANS, params=params, headers=lead).json()
        return [item["key"] for item in page["items"]]

    assert keys(trackerIterationId="it-1") == [first["key"]]
    assert keys(planningProjectId="p-1") == keys(planningReleaseId="r-1") == [second["key"]]
    assert keys(status="ACTIVE") == []
    page = client.get(PLANS, params={"pageSize": 1, "page": 2}, headers=lead).json()
    assert (page["totalPages"], len(page["items"])) == (2, 1)


@pytest.mark.parametrize(
    "role, read, write",
    [
        (Role.VIEWER, True, False),
        (Role.TESTER, True, False),
        (Role.AUTOMATION, True, False),
        (Role.LEAD, True, True),
        (Role.ADMIN, True, False),
        (Role.CI, False, False),
        (Role.REPORTS_READER, False, False),
    ],
)
def test_role_matrix(client, auth, lead, cases, role, read, write):
    plan = new_plan(client, lead, cases)
    headers = auth(role)
    url = f"{PLANS}/{plan['id']}"
    body = {
        "name": "П",
        "scopeKind": "MODULE",
        "owner": "o",
        "startDate": "2026-11-01",
        "endDate": "2026-11-02",
    }

    assert (client.get(PLANS, headers=headers).status_code == 200) is read
    assert (client.get(url, headers=headers).status_code == 200) is read
    assert (client.get(f"{url}/summary", headers=headers).status_code == 200) is read
    assert (client.post(PLANS, json=body, headers=headers).status_code == 201) is write
    assert (client.put(url, json=body, headers=headers).status_code == 200) is write
    assert (client.post(f"{url}/activate", headers=headers).status_code == 200) is write
    assert (client.post(f"{url}/cancel", headers=headers).status_code == 200) is write


def test_unknown_plan_is_404(client, lead):
    missing = f"{PLANS}/00000000-0000-0000-0000-000000000000"

    assert client.get(missing, headers=lead).status_code == 404
    assert client.get(f"{missing}/summary", headers=lead).status_code == 404
    assert client.post(f"{missing}/activate", headers=lead).status_code == 404
