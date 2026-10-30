"""Дефекты: автодефект и дедупликация, переходы, ручное создание, история (050, раздел 6)."""

import pytest
from factories import (
    DEFECTS,
    fail,
    environment,
    finish_run,
    new_case,
    new_plan,
    new_run,
    run_results,
    to_status,
)
from sqlalchemy import func, select

from app.auth import Role
from app.config import get_settings
from app.defects import service
from app.models import DefectRunLink, OutboxMessage
from app.models import Defect as DefectRow

pytestmark = pytest.mark.usefixtures("classifiers")

TO_READY = ("OPEN", "IN_PROGRESS", "FIXED", "READY_FOR_TEST")


@pytest.fixture
def lead(auth):
    return auth(Role.LEAD)


@pytest.fixture
def dev(db_session):
    return environment(db_session)


@pytest.fixture
def manual_tracker(monkeypatch):
    """Опрос Task Tracker выключен: статусы разработки ставит QA-лид."""
    monkeypatch.setenv("TRACKER_SYNC_ENABLED", "false")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def case(client, lead):
    return new_case(client, lead, steps=3, requirementRef="FR-1", epicRef="EP-1")


@pytest.fixture
def spare(client, lead):
    """Второй кейс: иначе последний результат завершает прогон."""
    return new_case(client, lead, module="TT")


def failed_defect(client, headers, case, spare, actual="500", step=2) -> tuple[dict, dict]:
    run = new_run(client, headers, [case, spare])
    result = fail(
        client, headers, run, run_results(client, headers, run)[case["key"]], actual, step
    )
    return run, client.get(f"{DEFECTS}/{result['defect']['id']}", headers=headers).json()


def count(session, table) -> int:
    return session.scalar(select(func.count()).select_from(table))


def test_failure_creates_auto_defect(client, lead, dev, case, spare, db_session):
    run = new_run(client, lead, [case, spare])
    result = fail(client, lead, run, run_results(client, lead, run)[case["key"]], "503", step=2)

    assert result["defect"]["created"] is True
    defect = client.get(f"{DEFECTS}/{result['defect']['id']}", headers=lead).json()
    assert defect["key"] == result["defect"]["key"] == "DEF-01"
    assert (defect["origin"], defect["status"]) == ("AUTO", "NEW")
    assert defect["title"] == f"[{case['key']}] Шаг 2: {case['title']}"
    assert defect["reproSteps"] == (
        "Предусловия: Есть доступ\n"
        "1. Действие 1 — ожидается: Ожидание 1\n"
        "2. Действие 2 — ожидается: Ожидание 2"
    )
    assert (defect["expectedResult"], defect["actualResult"]) == ("Ожидание 2", "503")
    assert (defect["severity"], defect["priority"]) == ("MAJOR", "HIGH")
    assert (defect["environment"], defect["author"]) == ("dev", "demo-qa-lead")
    assert (defect["testCaseKey"], defect["caseVersion"]) == (case["key"], 1)
    assert defect["stepId"] == case["steps"][1]["id"]
    assert (defect["requirementRef"], defect["epicRef"]) == ("FR-1", "EP-1")
    assert defect["runIds"] == [run["id"]]
    assert defect["runs"][0]["runKey"] == run["key"]
    assert defect["trackerSyncState"] == "PENDING"


def test_auto_defect_uses_fixed_version(client, lead, dev, case, spare):
    run = new_run(client, lead, [case, spare])
    client.put(
        f"/api/v1/test-cases/{case['id']}",
        json={
            "title": "Переписан",
            "module": "RM",
            "severity": "BLOCKER",
            "steps": [{"action": "Новый", "expectedResult": "Новое"}],
        },
        headers=lead,
    )

    result = fail(client, lead, run, run_results(client, lead, run)[case["key"]], step=1)

    defect = client.get(f"{DEFECTS}/{result['defect']['id']}", headers=lead).json()
    assert defect["severity"] == "MAJOR"
    assert defect["title"] == f"[{case['key']}] Шаг 1: {case['title']}"
    assert defect["reproSteps"].endswith("1. Действие 1 — ожидается: Ожидание 1")
    assert defect["caseVersion"] == 1


def test_failure_without_step(client, lead, dev, case, spare):
    run = new_run(client, lead, [case, spare])

    result = fail(client, lead, run, run_results(client, lead, run)[case["key"]])

    defect = client.get(f"{DEFECTS}/{result['defect']['id']}", headers=lead).json()
    assert defect["title"] == f"[{case['key']}] {case['title']}"
    assert defect["stepId"] is None
    assert defect["expectedResult"] is None
    assert "3. Действие 3" in defect["reproSteps"]


def test_outbox_and_history_of_auto_defect(client, lead, dev, case, spare, db_session):
    run, defect = failed_defect(client, lead, case, spare)

    message = db_session.scalars(select(OutboxMessage)).one()
    assert (message.kind, message.destination) == ("TRACKER_BUG", "task-tracker")
    assert (message.partition_key, message.sent_at) == (defect["key"], None)
    payload = message.payload
    assert (payload["externalSource"], payload["externalDefectId"]) == ("qa-system", "DEF-01")
    assert (payload["severity"], payload["environment"]) == ("high", "dev")
    assert payload["title"] == defect["title"]
    assert payload["testRunUrl"].endswith(f"/runs/{run['id']}")
    assert payload["testCaseUrl"].endswith(f"/test-cases/{case['id']}")
    assert "build" not in payload
    for text in ("Шаги воспроизведения", "Ожидание 2", "500", "MAJOR", "HIGH", case["key"]):
        assert text in payload["description"]
    assert "Шаг: 2" in payload["description"]

    history = client.get(f"{DEFECTS}/{defect['id']}/history", headers=lead).json()["items"]
    assert [(h["field"], h["newValue"], h["source"]) for h in history] == [
        ("status", "NEW", "SYSTEM")
    ]


@pytest.mark.parametrize(
    "severity, expected",
    [
        ("BLOCKER", "critical"),
        ("CRITICAL", "critical"),
        ("MAJOR", "high"),
        ("MINOR", "medium"),
        ("TRIVIAL", "low"),
    ],
)
def test_severity_scale_for_tracker(client, lead, dev, spare, db_session, severity, expected):
    case = new_case(client, lead, severity=severity)
    failed_defect(client, lead, case, spare)

    assert db_session.scalars(select(OutboxMessage)).one().payload["severity"] == expected


def test_repeated_failure_links_existing_defect(client, lead, dev, case, spare, db_session):
    first_run, defect = failed_defect(client, lead, case, spare)
    finish_run(client, lead, first_run)

    run = new_run(client, lead, [case, spare])
    result = fail(client, lead, run, run_results(client, lead, run)[case["key"]], "снова", step=1)

    assert result["defect"] == {"id": defect["id"], "key": defect["key"], "created": False}
    assert count(db_session, DefectRow) == 1
    assert count(db_session, OutboxMessage) == 1
    linked = client.get(f"{DEFECTS}/{defect['id']}", headers=lead).json()
    assert linked["runIds"] == [first_run["id"], run["id"]]
    history = client.get(f"{DEFECTS}/{defect['id']}/history", headers=lead).json()["items"]
    assert (history[0]["field"], history[0]["newValue"]) == ("run", run["key"])


def test_same_result_failed_twice_keeps_one_link(client, lead, dev, case, spare, db_session):
    run = new_run(client, lead, [case, spare])
    result = run_results(client, lead, run)[case["key"]]

    first = fail(client, lead, run, result)
    second = fail(client, lead, run, result, "ещё раз")

    assert second["defect"] == {**first["defect"], "created": False}
    assert count(db_session, DefectRunLink) == 1


def test_closed_defect_and_new_failure_create_new_defect(
    client, lead, dev, case, spare, db_session, manual_tracker
):
    first_run, defect = failed_defect(client, lead, case, spare)
    finish_run(client, lead, first_run)
    to_status(client, lead, defect, *TO_READY, "CLOSED")

    _, second = failed_defect(client, lead, case, spare)

    assert second["id"] != defect["id"]
    assert second["key"] == "DEF-02"
    assert count(db_session, OutboxMessage) == 2


def test_lost_race_links_winner_and_returns_key(client, lead, dev, case, spare, monkeypatch):
    """Гонка: проверка не увидела чужой дефект, индекс defect_open_auto_uq отклонил вставку."""
    first_run, defect = failed_defect(client, lead, case, spare)
    finish_run(client, lead, first_run)
    real = service._open_auto
    calls = iter([None])
    monkeypatch.setattr(service, "_open_auto", lambda s, c: next(calls, real(s, c)))

    run = new_run(client, lead, [case, spare])
    result = fail(client, lead, run, run_results(client, lead, run)[case["key"]])

    assert result["defect"] == {"id": defect["id"], "key": defect["key"], "created": False}
    assert result["status"] == "FAILED"
    monkeypatch.undo()
    # Номер, взятый в откатившемся savepoint, возвращается счётчику.
    other = new_case(client, lead, module="PS")
    _, next_defect = failed_defect(client, lead, other, spare)
    assert next_defect["key"] == "DEF-02"


def test_manual_defect_does_not_block_auto(client, lead, dev, case, spare):
    created = client.post(
        DEFECTS,
        json={
            "title": "Ручной",
            "actualResult": "Сбой",
            "severity": "MINOR",
            "testCaseId": case["id"],
            "environment": "dev",
        },
        headers=lead,
    )
    assert created.status_code == 201

    _, auto = failed_defect(client, lead, case, spare)

    assert auto["origin"] == "AUTO"
    assert auto["id"] != created.json()["id"]


def test_create_manual_from_result(client, auth, lead, dev, case, spare, db_session):
    plan = new_plan(client, lead, [case, spare], activate=True)
    run = client.post(
        "/api/v1/runs",
        json={"planId": plan["id"], "environment": "dev", "start": True},
        headers=lead,
    ).json()
    result = run_results(client, lead, run)[case["key"]]

    response = client.post(
        DEFECTS,
        json={
            "title": "Опечатка",
            "actualResult": "Текст",
            "severity": "TRIVIAL",
            "runResultId": result["id"],
            "stepId": result["steps"][2]["stepId"],
        },
        headers=auth(Role.TESTER, "ivanov"),
    )

    defect = response.json()
    assert response.status_code == 201
    assert (defect["origin"], defect["status"], defect["author"]) == ("MANUAL", "NEW", "ivanov")
    assert (defect["testCaseId"], defect["planId"]) == (case["id"], plan["id"])
    assert (defect["environment"], defect["priority"]) == ("dev", "HIGH")
    assert defect["runIds"] == [run["id"]]
    assert defect["stepId"] == result["steps"][2]["stepId"]
    payload = db_session.scalars(select(OutboxMessage)).one().payload
    assert payload["testRunUrl"].endswith(run["id"])


@pytest.mark.parametrize(
    "fields, field, reason",
    [
        ({"environment": "dev"}, "testCaseId", "required"),
        ({"testCaseId": "00000000-0000-0000-0000-000000000000"}, "testCaseId", "not_found"),
        ({"runResultId": "00000000-0000-0000-0000-000000000000"}, "runResultId", "not_found"),
        ({"testCaseId": "CASE"}, "environment", "required"),
        ({"testCaseId": "CASE", "environment": "nope"}, "environment", "not_found"),
        ({"testCaseId": "CASE", "environment": "dev", "priority": "NOPE"}, "priority", "unknown"),
        (
            {
                "testCaseId": "CASE",
                "environment": "dev",
                "stepId": "00000000-0000-0000-0000-000000000000",
            },
            "stepId",
            "not_found",
        ),
    ],
)
def test_manual_validation(client, lead, dev, case, fields, field, reason):
    body = {"title": "Т", "actualResult": "Ф", "severity": "MINOR", **fields}
    if body.get("testCaseId") == "CASE":
        body["testCaseId"] = case["id"]

    response = client.post(DEFECTS, json=body, headers=lead)

    assert response.status_code == 422
    assert {"field": field, "reason": reason} in response.json()["errors"]


def test_update_writes_history(client, lead, dev, case, spare):
    _, defect = failed_defect(client, lead, case, spare)
    url = f"{DEFECTS}/{defect['id']}"

    updated = client.put(
        url,
        json={"title": "Точнее", "severity": "BLOCKER", "priority": "LOW", "description": "Д"},
        headers=lead,
    ).json()
    same = client.put(url, json={"title": "Точнее"}, headers=lead)

    assert (updated["title"], updated["severity"], updated["priority"]) == (
        "Точнее",
        "BLOCKER",
        "LOW",
    )
    assert same.status_code == 200
    history = client.get(f"{url}/history", headers=lead).json()["items"]
    changes = {h["field"]: (h["oldValue"], h["newValue"], h["source"]) for h in history[:-1]}
    assert changes == {
        "title": (defect["title"], "Точнее", "QA"),
        "severity": ("MAJOR", "BLOCKER", "QA"),
        "priority": ("HIGH", "LOW", "QA"),
        "description": (None, "Д", "QA"),
    }


def test_update_validation(client, lead, dev, case, spare, db_session):
    _, defect = failed_defect(client, lead, case, spare)
    url = f"{DEFECTS}/{defect['id']}"

    cleared = client.put(url, json={"title": None}, headers=lead)
    unknown = client.put(url, json={"environment": "nope"}, headers=lead)

    assert cleared.json()["errors"] == [{"field": "title", "reason": "required"}]
    assert unknown.json()["errors"] == [{"field": "environment", "reason": "not_found"}]
    row = db_session.get(DefectRow, defect["id"])
    row.tracker_sync_state = "SYNCED"
    db_session.flush()
    owned = client.put(url, json={"priority": "LOW"}, headers=lead)
    assert owned.json()["errors"] == [{"field": "priority", "reason": "owned_by_tracker"}]


def test_transition_path_with_history(client, lead, dev, case, spare, manual_tracker):
    _, defect = failed_defect(client, lead, case, spare)

    closed = to_status(client, lead, defect, *TO_READY, "CLOSED")
    assert closed["status"] == "CLOSED"
    assert closed["closedAt"]
    reopened = to_status(client, lead, closed, "REOPENED")
    assert (reopened["reopenCount"], reopened["closedAt"]) == (1, None)
    again = to_status(client, lead, reopened, "IN_PROGRESS", "FIXED", "READY_FOR_TEST", "REOPENED")
    assert again["reopenCount"] == 2

    history = client.get(f"{DEFECTS}/{defect['id']}/history", headers=lead).json()["items"]
    assert history[0]["oldValue"] == "READY_FOR_TEST"
    assert history[0]["newValue"] == "REOPENED"
    assert (history[0]["source"], history[0]["author"]) == ("QA", "demo-qa-lead")


ALLOWED = {
    "NEW": {"OPEN"},
    "OPEN": {"IN_PROGRESS"},
    "IN_PROGRESS": {"FIXED"},
    "FIXED": {"READY_FOR_TEST"},
    "READY_FOR_TEST": {"CLOSED", "REOPENED"},
    "CLOSED": {"REOPENED"},
    "REOPENED": {"IN_PROGRESS"},
}
STATUSES = list(ALLOWED)


@pytest.mark.parametrize("source", STATUSES)
@pytest.mark.parametrize("target", STATUSES)
def test_every_transition(
    client, lead, dev, case, spare, db_session, manual_tracker, source, target
):
    _, defect = failed_defect(client, lead, case, spare)
    db_session.get(DefectRow, defect["id"]).status = source
    db_session.flush()

    response = client.post(
        f"{DEFECTS}/{defect['id']}/transitions", json={"to": target}, headers=lead
    )

    if target in ALLOWED[source]:
        assert response.status_code == 200
        assert response.json()["status"] == target
    else:
        assert (response.status_code, response.json()["code"]) == (409, "INVALID_TRANSITION")
        allowed = response.json()["errors"][0]["reason"].removeprefix("allowed:")
        assert set(allowed.split(",")) == ALLOWED[source]


def test_invalid_transition_lists_allowed(client, lead, dev, case, spare, manual_tracker):
    _, defect = failed_defect(client, lead, case, spare)

    response = client.post(
        f"{DEFECTS}/{defect['id']}/transitions", json={"to": "CLOSED"}, headers=lead
    )

    assert response.status_code == 409
    assert response.json()["errors"] == [{"field": "to", "reason": "allowed:OPEN"}]


@pytest.mark.parametrize("target", ["OPEN", "IN_PROGRESS", "FIXED"])
def test_development_status_is_owned_by_tracker(client, auth, lead, dev, case, spare, target):
    _, defect = failed_defect(client, lead, case, spare)
    url = f"{DEFECTS}/{defect['id']}/transitions"

    by_lead = client.post(url, json={"to": target}, headers=lead)
    by_tester = client.post(url, json={"to": target}, headers=auth(Role.TESTER))

    assert (by_lead.status_code, by_lead.json()["code"]) == (409, "STATUS_OWNED_BY_TRACKER")
    assert by_tester.status_code == 403


def test_only_lead_sets_development_status_with_sync_off(
    client, auth, lead, dev, case, spare, manual_tracker
):
    _, defect = failed_defect(client, lead, case, spare)
    url = f"{DEFECTS}/{defect['id']}/transitions"

    assert client.post(url, json={"to": "OPEN"}, headers=auth(Role.TESTER)).status_code == 403
    assert client.post(url, json={"to": "OPEN"}, headers=lead).status_code == 200


def test_tester_changes_testing_statuses(client, auth, lead, dev, case, spare, manual_tracker):
    _, defect = failed_defect(client, lead, case, spare)
    to_status(client, lead, defect, "OPEN", "IN_PROGRESS", "FIXED")
    tester = auth(Role.TESTER, "ivanov")

    ready = to_status(client, tester, defect, "READY_FOR_TEST", "CLOSED")

    assert ready["status"] == "CLOSED"
    automation = client.post(
        f"{DEFECTS}/{defect['id']}/transitions",
        json={"to": "REOPENED"},
        headers=auth(Role.AUTOMATION),
    )
    assert automation.status_code == 403


def test_reopening_closed_defect_conflicts_with_newer_one(
    client, lead, dev, case, spare, manual_tracker
):
    """Индекс defect_open_auto_uq не должен превращаться в 500."""
    first_run, closed = failed_defect(client, lead, case, spare)
    finish_run(client, lead, first_run)
    to_status(client, lead, closed, *TO_READY, "CLOSED")
    _, newer = failed_defect(client, lead, case, spare)

    response = client.post(
        f"{DEFECTS}/{closed['id']}/transitions", json={"to": "REOPENED"}, headers=lead
    )

    assert (response.status_code, response.json()["code"]) == (409, "INVALID_TRANSITION")
    assert response.json()["errors"] == [{"field": "to", "reason": f"open-auto:{newer['key']}"}]
    after = client.get(f"{DEFECTS}/{closed['id']}", headers=lead).json()
    assert (after["status"], after["reopenCount"]) == ("CLOSED", 0)


def test_comment_on_transition_and_directly(client, auth, lead, dev, case, spare, manual_tracker):
    _, defect = failed_defect(client, lead, case, spare)
    url = f"{DEFECTS}/{defect['id']}"

    client.post(f"{url}/transitions", json={"to": "OPEN", "comment": "Взяли"}, headers=lead)
    added = client.post(f"{url}/comments", json={"body": "Вижу"}, headers=auth(Role.VIEWER, "dev1"))

    assert added.status_code == 201
    assert (added.json()["author"], added.json()["source"]) == ("dev1", "QA")
    detail = client.get(url, headers=lead).json()
    assert [c["body"] for c in detail["comments"]] == ["Взяли", "Вижу"]
    history = client.get(f"{url}/history", headers=lead).json()["items"]
    assert (history[0]["field"], history[0]["newValue"]) == ("comment", "Вижу")
    assert client.post(f"{url}/comments", json={"body": " "}, headers=lead).status_code == 422


def test_filters_and_pagination(client, auth, lead, dev, spare):
    major = new_case(client, lead)
    blocker = new_case(client, lead, severity="BLOCKER")
    plan = new_plan(client, lead, [major, spare], activate=True, trackerIterationId="it-1")
    plan_run = client.post(
        "/api/v1/runs",
        json={"planId": plan["id"], "environment": "dev", "start": True},
        headers=lead,
    ).json()
    fail(client, lead, plan_run, run_results(client, lead, plan_run)[major["key"]])
    _, second = failed_defect(client, auth(Role.TESTER, "ivanov"), blocker, spare)

    def keys(**params):
        page = client.get(DEFECTS, params=params, headers=lead).json()
        return [item["key"] for item in page["items"]]

    assert keys() == ["DEF-02", "DEF-01"]
    assert keys(severity="BLOCKER") == ["DEF-02"]
    assert keys(author="ivanov") == ["DEF-02"]
    assert keys(status="CLOSED") == []
    assert keys(trackerIterationId="it-1") == ["DEF-01"]
    assert keys(trackerMismatch="false") == ["DEF-02", "DEF-01"]
    page = client.get(DEFECTS, params={"pageSize": 1, "page": 2}, headers=lead).json()
    assert (page["totalPages"], page["items"][0]["key"]) == (2, "DEF-01")
    assert page["items"][0]["testCaseKey"] == major["key"]


@pytest.mark.parametrize(
    "role, read, write, comment",
    [
        (Role.VIEWER, True, False, True),
        (Role.TESTER, True, True, True),
        (Role.AUTOMATION, True, True, True),
        (Role.LEAD, True, True, True),
        (Role.ADMIN, True, False, False),
        (Role.CI, False, False, False),
        (Role.REPORTS_READER, False, False, False),
    ],
)
def test_role_matrix(client, auth, lead, dev, case, spare, role, read, write, comment):
    _, defect = failed_defect(client, lead, case, spare)
    url = f"{DEFECTS}/{defect['id']}"
    headers = auth(role)
    body = {
        "title": "Т",
        "actualResult": "Ф",
        "severity": "MINOR",
        "testCaseId": case["id"],
        "environment": "dev",
    }

    assert (client.get(url, headers=headers).status_code == 200) is read
    assert (client.get(DEFECTS, headers=headers).status_code == 200) is read
    assert (client.get(f"{url}/history", headers=headers).status_code == 200) is read
    assert (client.post(DEFECTS, json=body, headers=headers).status_code == 201) is write
    assert (client.put(url, json={"title": "Н"}, headers=headers).status_code == 200) is write
    posted = client.post(f"{url}/comments", json={"body": "К"}, headers=headers)
    assert (posted.status_code == 201) is comment


def test_unknown_defect_is_404(client, lead):
    missing = f"{DEFECTS}/00000000-0000-0000-0000-000000000000"

    assert client.get(missing, headers=lead).status_code == 404
    assert client.get(f"{missing}/history", headers=lead).status_code == 404
    assert client.put(missing, json={}, headers=lead).status_code == 404
