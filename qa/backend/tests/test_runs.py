"""Прогоны: состав, идемпотентность, переходы, результаты (050, раздел 4; 130)."""

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
    new_run,
    new_suite,
    record,
    run_results,
)
from sqlalchemy import select

from app.auth import Role
from app.models import RunResult as RunResultRow
from app.models import StepResult
from app.runs import service

pytestmark = pytest.mark.usefixtures("classifiers")

KEY = "Idempotency-Key"


@pytest.fixture
def lead(auth):
    return auth(Role.LEAD)


@pytest.fixture
def dev(db_session):
    return environment(db_session)


@pytest.fixture
def cases(client, lead):
    return [new_case(client, lead), new_case(client, lead, module="TT")]


@pytest.fixture
def run(client, lead, dev, cases):
    return new_run(client, lead, cases)


def test_create_fixes_current_versions(client, lead, dev):
    case = new_case(client, lead)
    updated = client.put(
        f"/api/v1/test-cases/{case['id']}",
        json={"title": "Новое", "module": "RM"},
        headers=lead,
    ).json()
    run = new_run(client, lead, [case], start=False)
    client.put(
        f"/api/v1/test-cases/{case['id']}",
        json={"title": "Ещё новее", "module": "RM"},
        headers=lead,
    )

    result = run_results(client, lead, run)[case["key"]]

    assert run["status"] == "CREATED"
    assert run["summary"]["total"] == run["summary"]["notRun"] == 1
    assert (result["caseVersion"], result["title"]) == (updated["version"], "Новое")
    assert result["status"] == "NOT_RUN"
    assert run["trigger"] == "MANUAL"


def test_only_actual_and_needs_update_cases_get_into_run(client, lead, dev, db_session):
    actual = new_case(client, lead)
    needs_update = new_case(client, lead)
    archived = new_case(client, lead)
    suite = new_suite(client, lead, [actual, needs_update, archived])
    change_case_status(client, lead, needs_update, "NEEDS_UPDATE")
    change_case_status(client, lead, archived, "ARCHIVED")
    new_case(client, lead, status="DRAFT")
    by_filter = new_suite(client, lead, kind="FILTER", caseIds=[], filter={"module": "RM"})

    for source in (suite, by_filter):
        body = {"suiteId": source["id"], "environment": "dev"}
        run = client.post(RUNS, json=body, headers=lead).json()
        assert set(run_results(client, lead, run)) == {actual["key"], needs_update["key"]}


def test_run_from_archived_suite_is_rejected(client, lead, dev, cases):
    suite = new_suite(client, lead, cases)
    client.post(f"{SUITES}/{suite['id']}/archive", headers=lead)

    response = client.post(RUNS, json={"suiteId": suite["id"], "environment": "dev"}, headers=lead)

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "suiteId", "reason": "archived"}]


def test_empty_composition_is_run_empty(client, lead, dev):
    suite = new_suite(client, lead, kind="FILTER", caseIds=[], filter={"automated": True})

    response = client.post(
        RUNS, json={"suiteName": suite["name"], "environment": "dev"}, headers=lead
    )

    assert (response.status_code, response.json()["code"]) == (422, "RUN_EMPTY")
    assert client.get(RUNS, headers=lead).json()["items"] == []


@pytest.mark.parametrize(
    "body, field, reason",
    [
        ({"environment": "dev"}, "planId", "exactly_one_of:planId,suiteId,suiteName"),
        ({"suiteName": "Нет", "environment": "dev"}, "suiteName", "not_found"),
        ({"suiteName": "S", "environment": "nope"}, "environment", "not_found"),
        ({"suiteName": "S", "environment": "off"}, "environment", "inactive"),
    ],
)
def test_create_validation(client, lead, dev, db_session, cases, body, field, reason):
    environment(db_session, "off", is_active=False)
    new_suite(client, lead, cases, name="S")

    response = client.post(RUNS, json=body, headers=lead)

    assert response.status_code == 422
    assert {"field": field, "reason": reason} in response.json()["errors"]


def test_idempotency_key_returns_same_run(client, auth, dev, cases, lead):
    suite = new_suite(client, lead, cases)
    body = {"suiteName": suite["name"], "environment": "dev", "start": True}
    ci = {**auth(Role.CI), KEY: "deploy-1"}

    first = client.post(RUNS, json=body, headers=ci)
    second = client.post(RUNS, json=body, headers=ci)
    other_key = client.post(RUNS, json=body, headers={**ci, KEY: "deploy-2"})
    other_client = client.post(RUNS, json=body, headers={**lead, KEY: "deploy-1"})

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["trigger"] == "CI"
    # Первый запуск ещё идёт: другой ключ и другой клиент упираются в FR-RUN-10, а не в дубль.
    assert other_key.json()["code"] == other_client.json()["code"] == "SUITE_ALREADY_RUNNING"


def test_idempotency_race_returns_winner(client, lead, dev, cases, monkeypatch):
    suite = new_suite(client, lead, cases)
    body = {"suiteId": suite["id"], "environment": "dev"}
    headers = {**lead, KEY: "race"}
    winner = client.post(RUNS, json=body, headers=headers).json()
    real = service._by_idempotency_key
    calls = iter([None])

    def lost_race(session, principal, key):
        return next(calls, real(session, principal, key))

    monkeypatch.setattr(service, "_by_idempotency_key", lost_race)

    repeated = client.post(RUNS, json=body, headers=headers)

    assert (repeated.status_code, repeated.json()["id"]) == (200, winner["id"])
    assert repeated.json()["key"] == winner["key"]


def test_suite_runs_once_per_environment(client, lead, dev, db_session, cases):
    environment(db_session, "staging")
    suite = new_suite(client, lead, cases)
    body = {"suiteId": suite["id"], "environment": "dev", "start": True}

    running = client.post(RUNS, json=body, headers=lead).json()
    conflict = client.post(RUNS, json=body, headers=lead)
    elsewhere = client.post(RUNS, json={**body, "environment": "staging"}, headers=lead)
    waiting = client.post(RUNS, json={**body, "start": False}, headers=lead).json()
    blocked_start = client.post(f"{RUNS}/{waiting['id']}/start", headers=lead)

    assert conflict.status_code == 409
    assert conflict.json()["code"] == "SUITE_ALREADY_RUNNING"
    assert conflict.json()["errors"] == [
        {"field": "suiteId", "reason": f"running:{running['key']}"}
    ]
    assert elsewhere.status_code == 201
    assert blocked_start.json()["code"] == "SUITE_ALREADY_RUNNING"
    finish_run(client, lead, running)
    assert client.post(RUNS, json=body, headers=lead).status_code == 201


def test_run_transitions(client, lead, dev, cases):
    run = new_run(client, lead, cases, start=False)
    url = f"{RUNS}/{run['id']}"

    assert client.post(f"{url}/complete", headers=lead).json()["code"] == "INVALID_TRANSITION"
    started = client.post(f"{url}/start", headers=lead).json()
    assert (started["status"], started["finishedAt"]) == ("IN_PROGRESS", None)
    assert started["startedAt"]
    assert client.post(f"{url}/start", headers=lead).status_code == 409
    completed = client.post(f"{url}/complete", headers=lead).json()
    assert completed["status"] == "COMPLETED"
    assert completed["durationMs"] >= 0
    for action in ("start", "complete", "abort"):
        response = client.post(f"{url}/{action}", headers=lead)
        assert (response.status_code, response.json()["code"]) == (409, "INVALID_TRANSITION")


@pytest.mark.parametrize("start", [False, True])
def test_abort_from_created_and_in_progress(client, lead, dev, cases, start):
    run = new_run(client, lead, cases, start=start)
    url = f"{RUNS}/{run['id']}"

    aborted = client.post(f"{url}/abort", headers=lead).json()

    assert aborted["status"] == "ABORTED"
    assert aborted["durationMs"] is None or start
    assert client.post(f"{url}/abort", headers=lead).json()["code"] == "INVALID_TRANSITION"


def test_record_result_with_steps(client, lead, dev, cases, run):
    key = cases[0]["key"]
    result = run_results(client, lead, run)[key]
    first, second = result["steps"]

    response = record(
        client,
        lead,
        run,
        result,
        status="FAILED",
        comment="Падает",
        durationMs=1500,
        steps=[
            {"stepId": second["stepId"], "status": "FAILED", "actualResult": "500"},
            {"stepId": first["stepId"], "status": "PASSED"},
        ],
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["failedStepPosition"], body["actualResult"]) == (2, "500")
    assert (body["executedBy"], body["durationMs"]) == ("demo-qa-lead", 1500)
    assert [s["status"] for s in body["steps"]] == ["PASSED", "FAILED"]
    assert body["finishedAt"]
    assert client.get(f"{RUNS}/{run['id']}", headers=lead).json()["summary"] == {
        "total": 2,
        "passed": 0,
        "failed": 1,
        "blocked": 0,
        "notRun": 1,
        "skipped": 0,
        "unverified": 0,
    }


def test_rerecording_replaces_step_results(client, lead, dev, cases, run, db_session):
    result = run_results(client, lead, run)[cases[0]["key"]]
    step = result["steps"][0]["stepId"]
    fail(client, lead, run, result, step=1)

    again = record(
        client, lead, run, result, status="PASSED", steps=[{"stepId": step, "status": "PASSED"}]
    ).json()

    assert (again["status"], again["failedStepPosition"]) == ("PASSED", None)
    assert again["actualResult"] is None
    assert db_session.scalars(select(StepResult.status)).all() == ["PASSED"]


def test_reset_to_not_run_clears_finish_time(client, lead, dev, cases, run):
    result = run_results(client, lead, run)[cases[0]["key"]]
    record(client, lead, run, result, status="PASSED")

    reset = record(client, lead, run, result, status="NOT_RUN").json()

    assert (reset["finishedAt"], reset["executedBy"]) == (None, None)


def test_step_of_another_version_is_rejected(client, lead, dev, cases, run):
    """Шаги новой версии кейса не принимаются: прогон зафиксировал старую (ADR-003)."""
    case = cases[0]
    new_steps = [{"action": "Другое", "expectedResult": "Другое"}]
    current = client.put(
        f"/api/v1/test-cases/{case['id']}",
        json={"title": case["title"], "module": "RM", "steps": new_steps},
        headers=lead,
    ).json()
    result = run_results(client, lead, run)[case["key"]]

    response = record(
        client,
        lead,
        run,
        result,
        status="PASSED",
        steps=[{"stepId": current["steps"][0]["id"], "status": "PASSED"}],
    )

    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "steps.0.stepId", "reason": "not_in_case_version"}
    ]


def test_result_validation(client, lead, dev, cases, run):
    result = run_results(client, lead, run)[cases[0]["key"]]
    step = result["steps"][0]["stepId"]
    failed_step = {"stepId": step, "status": "FAILED", "actualResult": "500"}

    no_actual = record(client, lead, run, result, status="FAILED")
    contradiction = record(client, lead, run, result, status="PASSED", steps=[failed_step])
    duplicate = record(client, lead, run, result, status="FAILED", steps=[failed_step] * 2)

    assert no_actual.json()["errors"] == [{"field": "actualResult", "reason": "required"}]
    assert contradiction.json()["errors"] == [{"field": "status", "reason": "failed_step"}]
    assert duplicate.json()["errors"] == [{"field": "steps.1.stepId", "reason": "duplicate"}]


def test_finished_run_rejects_results(client, lead, dev, cases, run):
    result = run_results(client, lead, run)[cases[0]["key"]]
    finish_run(client, lead, run)

    response = record(client, lead, run, result, status="PASSED")

    assert (response.status_code, response.json()["code"]) == (409, "RUN_FINISHED")


def test_not_started_run_rejects_results(client, lead, dev, cases):
    run = new_run(client, lead, cases, start=False)
    result = run_results(client, lead, run)[cases[0]["key"]]

    response = record(client, lead, run, result, status="PASSED")

    assert (response.status_code, response.json()["code"]) == (409, "INVALID_TRANSITION")


def test_last_result_completes_run(client, lead, dev, cases, run):
    results = run_results(client, lead, run)
    record(client, lead, run, results[cases[0]["key"]], status="PASSED")
    assert client.get(f"{RUNS}/{run['id']}", headers=lead).json()["status"] == "IN_PROGRESS"

    record(client, lead, run, results[cases[1]["key"]], status="SKIPPED")

    finished = client.get(f"{RUNS}/{run['id']}", headers=lead).json()
    assert (finished["status"], finished["smokeVerdict"]) == ("COMPLETED", "GREEN")
    assert finished["finishedAt"]


def test_failed_result_makes_smoke_verdict_red(client, lead, dev, cases, run):
    fail(client, lead, run, run_results(client, lead, run)[cases[0]["key"]])
    assert client.get(f"{RUNS}/{run['id']}", headers=lead).json()["smokeVerdict"] is None

    assert finish_run(client, lead, run)["smokeVerdict"] == "RED"


def test_unverified_counts_skipped_with_reason(client, lead, dev, cases, run):
    results = run_results(client, lead, run)

    record(
        client,
        lead,
        run,
        results[cases[0]["key"]],
        status="SKIPPED",
        failureReason=service.UNVERIFIED_REASON,
    )
    record(client, lead, run, results[cases[1]["key"]], status="SKIPPED")

    summary = client.get(f"{RUNS}/{run['id']}", headers=lead).json()["summary"]
    assert (summary["skipped"], summary["unverified"]) == (2, 1)


def test_last_result_on_case_card(client, lead, dev, cases):
    case = cases[0]
    first = new_run(client, lead, [case, cases[1]])
    fail(client, lead, first, run_results(client, lead, first)[case["key"]], "первый", step=2)
    finish_run(client, lead, first)
    url = f"/api/v1/test-cases/{case['id']}"
    card = client.get(url, headers=lead).json()["lastResult"]
    assert (card["runKey"], card["status"]) == (first["key"], "FAILED")
    assert (card["actualResult"], card["failedStepPosition"]) == ("первый", 2)
    assert (card["environment"], card["caseVersion"]) == ("dev", 1)

    second = new_run(client, lead, [case, cases[1]])
    record(client, lead, second, run_results(client, lead, second)[case["key"]], status="PASSED")

    latest = client.get(url, headers=lead).json()["lastResult"]
    assert (latest["runKey"], latest["status"]) == (second["key"], "PASSED")


def test_lists_and_pagination(client, lead, dev, cases):
    first = new_run(client, lead, cases)
    finish_run(client, lead, first)
    second = new_run(client, lead, cases)

    page = client.get(RUNS, params={"pageSize": 1}, headers=lead).json()
    assert (page["totalPages"], len(page["items"])) == (2, 1)
    assert page["items"][0]["key"] == second["key"]
    next_page = client.get(RUNS, params={"pageSize": 1, "page": 2}, headers=lead).json()
    assert next_page["items"][0]["key"] == first["key"]
    by_status = client.get(RUNS, params={"status": "COMPLETED"}, headers=lead).json()
    assert [run["key"] for run in by_status["items"]] == [first["key"]]
    by_suite = client.get(RUNS, params={"suiteId": second["suiteId"]}, headers=lead).json()
    assert [run["key"] for run in by_suite["items"]] == [second["key"]]

    results = client.get(
        f"{RUNS}/{second['id']}/results", params={"pageSize": 1}, headers=lead
    ).json()
    assert (results["totalPages"], results["items"][0]["testCaseKey"]) == (2, cases[0]["key"])


def test_results_filters(client, lead, dev, cases, db_session, run):
    results = run_results(client, lead, run)
    record(client, lead, run, results[cases[0]["key"]], status="BLOCKED")
    url = f"{RUNS}/{run['id']}/results"

    blocked = client.get(url, params={"status": "BLOCKED"}, headers=lead).json()
    assigned = client.get(url, params={"assignee": "ivanov"}, headers=lead).json()

    assert [item["testCaseKey"] for item in blocked["items"]] == [cases[0]["key"]]
    assert assigned["items"] == []


def test_run_from_plan(client, lead, dev, cases):
    plan = new_plan(client, lead, cases, activate=True)
    change_case_status(client, lead, cases[1], "ARCHIVED")

    created = client.post(
        RUNS, json={"planId": plan["id"], "environment": "dev"}, headers=lead
    ).json()

    assert created["planId"] == plan["id"]
    assert set(run_results(client, lead, created)) == {cases[0]["key"]}
    filtered = client.get(RUNS, params={"planId": plan["id"]}, headers=lead).json()
    assert [run["id"] for run in filtered["items"]] == [created["id"]]


def test_run_from_inactive_plan_is_rejected(client, lead, dev, cases):
    plan = new_plan(client, lead, cases)
    body = {"planId": plan["id"], "environment": "dev"}

    assert client.post(RUNS, json=body, headers=lead).json()["code"] == "PLAN_NOT_ACTIVE"
    client.post(f"{PLANS}/{plan['id']}/cancel", headers=lead)
    assert client.post(RUNS, json=body, headers=lead).status_code == 409


def test_ci_starts_suites_only_and_sees_own_runs(client, auth, lead, dev, cases, run):
    ci = auth(Role.CI)
    plan = new_plan(client, lead, cases, activate=True)
    suite = new_suite(client, lead, cases)

    from_plan = client.post(RUNS, json={"planId": plan["id"], "environment": "dev"}, headers=ci)
    own = client.post(RUNS, json={"suiteId": suite["id"], "environment": "dev"}, headers=ci).json()

    assert from_plan.status_code == 403
    assert [item["id"] for item in client.get(RUNS, headers=ci).json()["items"]] == [own["id"]]
    assert client.get(f"{RUNS}/{own['id']}", headers=ci).status_code == 200
    assert client.get(f"{RUNS}/{run['id']}", headers=ci).status_code == 404
    assert client.post(f"{RUNS}/{own['id']}/start", headers=ci).status_code == 200
    assert client.get(f"{RUNS}/{own['id']}/results", headers=ci).status_code == 403


def test_tester_records_own_or_unassigned_only(client, auth, lead, dev, cases, run, db_session):
    results = run_results(client, lead, run)
    tester = auth(Role.TESTER, "ivanov")
    db_session.get(RunResultRow, results[cases[0]["key"]]["id"]).assignee = "petrov"
    db_session.flush()

    foreign = record(client, tester, run, results[cases[0]["key"]], status="PASSED")
    unassigned = record(client, tester, run, results[cases[1]["key"]], status="BLOCKED")
    by_lead = record(client, lead, run, results[cases[0]["key"]], status="PASSED")

    assert foreign.status_code == 403
    assert unassigned.status_code == 200
    assert by_lead.status_code == 200


@pytest.mark.parametrize(
    "role, read, create, record_result, manage",
    [
        (Role.VIEWER, True, False, False, False),
        (Role.TESTER, True, True, True, False),
        (Role.AUTOMATION, True, True, False, False),
        (Role.LEAD, True, True, True, True),
        (Role.ADMIN, True, False, False, False),
        (Role.REPORTS_READER, False, False, False, False),
    ],
)
def test_role_matrix(client, auth, lead, dev, cases, role, read, create, record_result, manage):
    run = new_run(client, lead, cases)
    result = run_results(client, lead, run)[cases[0]["key"]]
    headers = auth(role)
    suite = new_suite(client, lead, cases)
    body = {"suiteId": suite["id"], "environment": "dev"}

    assert (client.get(RUNS, headers=headers).status_code == 200) is read
    assert (client.get(f"{RUNS}/{run['id']}/results", headers=headers).status_code == 200) is read
    assert (client.post(RUNS, json=body, headers=headers).status_code == 201) is create
    written = record(client, headers, run, result, status="PASSED")
    assert (written.status_code == 200) is record_result
    assert (client.post(f"{RUNS}/{run['id']}/abort", headers=headers).status_code == 200) is manage


@pytest.mark.parametrize(
    "start, action", [(False, None), (True, None), (True, "abort"), (True, "complete")]
)
def test_delete_empty_run(client, lead, dev, cases, db_session, start, action):
    run = new_run(client, lead, cases, start=start)
    if action:
        assert client.post(f"{RUNS}/{run['id']}/{action}", headers=lead).status_code == 200

    assert client.delete(f"{RUNS}/{run['id']}", headers=lead).status_code == 204

    assert client.get(f"{RUNS}/{run['id']}", headers=lead).status_code == 404
    assert not db_session.scalar(select(RunResultRow).where(RunResultRow.run_id == run["id"]))


def test_deleted_run_frees_suite_on_environment(client, lead, dev, cases):
    run = new_run(client, lead, cases)
    client.delete(f"{RUNS}/{run['id']}", headers=lead)

    body = {"suiteId": run["suiteId"], "environment": "dev", "start": True}
    assert client.post(RUNS, json=body, headers=lead).status_code == 201


def test_delete_run_with_results_is_rejected(client, lead, dev, cases, run):
    result = run_results(client, lead, run)[cases[0]["key"]]
    assert record(client, lead, run, result, status="PASSED").status_code == 200

    response = client.delete(f"{RUNS}/{run['id']}", headers=lead)

    assert response.status_code == 409
    assert response.json()["code"] == "RUN_HAS_RESULTS"
    assert client.get(f"{RUNS}/{run['id']}", headers=lead).status_code == 200


def test_delete_run_keeps_records_of_reset_result(client, lead, dev, cases, run):
    result = run_results(client, lead, run)[cases[0]["key"]]
    step = {"stepId": result["steps"][0]["stepId"], "status": "PASSED"}
    assert record(client, lead, run, result, status="NOT_RUN", steps=[step]).status_code == 200
    response = client.delete(f"{RUNS}/{run['id']}", headers=lead)
    assert (response.status_code, response.json()["code"]) == (409, "RUN_HAS_RESULTS")

    assert record(client, lead, run, result, status="NOT_RUN").status_code == 200
    fail(client, lead, run, result)
    assert record(client, lead, run, result, status="NOT_RUN").status_code == 200
    response = client.delete(f"{RUNS}/{run['id']}", headers=lead)
    assert (response.status_code, response.json()["code"]) == (409, "RUN_HAS_RESULTS")


def test_delete_completed_run_with_results_is_rejected(client, lead, dev, cases, run):
    result = run_results(client, lead, run)[cases[0]["key"]]
    assert record(client, lead, run, result, status="PASSED").status_code == 200
    finish_run(client, lead, run)

    response = client.delete(f"{RUNS}/{run['id']}", headers=lead)

    assert (response.status_code, response.json()["code"]) == (409, "RUN_HAS_RESULTS")


@pytest.mark.parametrize(
    "role", [Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.ADMIN, Role.CI, Role.REPORTS_READER]
)
def test_delete_run_is_for_lead_only(client, auth, lead, dev, cases, run, role):
    assert client.delete(f"{RUNS}/{run['id']}", headers=auth(role)).status_code == 403
    assert client.get(f"{RUNS}/{run['id']}", headers=lead).status_code == 200


def test_unknown_objects(client, lead, dev, cases, run):
    missing = "00000000-0000-0000-0000-000000000000"
    other = new_run(client, lead, cases[:1])
    foreign = run_results(client, lead, other)[cases[0]["key"]]

    assert client.get(f"{RUNS}/{missing}", headers=lead).status_code == 404
    assert client.delete(f"{RUNS}/{missing}", headers=lead).status_code == 404
    assert client.get(f"{RUNS}/{missing}/results", headers=lead).status_code == 404
    assert record(client, lead, run, foreign, status="PASSED").status_code == 404
    assert client.get(RUNS).status_code == 401
