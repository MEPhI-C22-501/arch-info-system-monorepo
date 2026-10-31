"""Тест-кейсы: версии (ADR-003), статусы (050, раздел 2), ошибки и права (130, 070)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.auth import Role
from app.models import (
    ClassifierValue,
    Defect,
    Environment,
    RunResult,
    TestCase,
    TestCaseTemplate,
    TestCaseVersion,
    TestRun,
    TestSuite,
)

pytestmark = pytest.mark.usefixtures("classifiers")

URL = "/api/v1/test-cases"


def payload(**overrides):
    body = {
        "title": "Создание записи с занятым кодом отклоняется",
        "module": "RM",
        "priority": "HIGH",
        "severity": "MAJOR",
        "type": "NEGATIVE",
        "steps": [
            {"action": "Создать запись currencies/PLN", "expectedResult": "201, state ACTIVE"},
            {"action": "Создать запись повторно", "expectedResult": "409 ALREADY_EXISTS"},
        ],
    }
    body.update(overrides)
    return body


@pytest.fixture
def create(client, auth):
    def create_case(role=Role.TESTER, user=None, **overrides):
        response = client.post(URL, json=payload(**overrides), headers=auth(role, user))
        assert response.status_code == 201, response.json()
        return response.json()

    return create_case


def set_status(client, auth, case_id, status, role=Role.TESTER):
    return client.post(f"{URL}/{case_id}/status", json={"status": status}, headers=auth(role))


def make_actual(client, auth, case_id):
    assert set_status(client, auth, case_id, "ACTUAL").status_code == 200


def add_result(session, case_id, *, status="FAILED", finished_at=None, env_code="dev"):
    """Результат прогона напрямую в БД: модуль прогонов — следующий этап."""
    environment = session.scalar(select(Environment).where(Environment.code == env_code))
    if environment is None:
        environment = Environment(code=env_code, name=env_code, base_urls={})
        session.add(environment)
    suite = session.scalar(select(TestSuite).where(TestSuite.name == "Результаты"))
    if suite is None:
        suite = TestSuite(
            name="Результаты", kind="MANUAL", status="ACTIVE", purpose="GENERAL", owner="t"
        )
        session.add(suite)
    session.flush()
    run = TestRun(
        key=f"RUN-{uuid.uuid4().hex[:6]}",
        suite_id=suite.id,
        environment_id=environment.id,
        status="IN_PROGRESS",
        trigger="MANUAL",
        started_by="t",
    )
    session.add(run)
    session.flush()
    case = session.get(TestCase, case_id)
    version = session.scalar(
        select(TestCaseVersion).where(
            TestCaseVersion.test_case_id == case.id,
            TestCaseVersion.version == case.current_version,
        )
    )
    result = RunResult(
        run_id=run.id,
        test_case_id=case.id,
        case_version_id=version.id,
        status=status,
        actual_result="201 Created вместо 409",
        failed_step_position=2 if status == "FAILED" else None,
        finished_at=finished_at,
    )
    session.add(result)
    session.flush()
    return run


# --- Создание и чтение -------------------------------------------------------------------


def test_create_case_is_draft_version_1_with_key_and_positions(create):
    case = create()

    assert case["key"] == "TC-RM-01"
    assert case["status"] == "DRAFT"
    assert case["version"] == case["currentVersion"] == 1
    assert [s["position"] for s in case["steps"]] == [1, 2]
    assert case["steps"][1]["expectedResult"] == "409 ALREADY_EXISTS"
    assert case["createdBy"] == "demo-qa-tester"
    assert case["lastResult"] is None
    assert "actualResult" not in case  # ADR-014: у кейса нет фактического результата


def test_keys_are_numbered_per_module(create):
    assert create()["key"] == "TC-RM-01"
    assert create()["key"] == "TC-RM-02"
    assert create(module="TT")["key"] == "TC-TT-01"


@pytest.mark.parametrize(
    "overrides, field, reason",
    [
        ({"title": "  "}, "title", None),
        ({"module": "rm"}, "module", None),
        ({"module": "RNM"}, "module", "unknown"),
        ({"priority": "URGENT"}, "priority", "unknown"),
        ({"severity": "HUGE"}, "severity", None),
        ({"type": None}, "type", "required"),
        ({"steps": [{"action": "a", "expectedResult": ""}]}, "steps.0.expectedResult", None),
    ],
)
def test_create_validation(client, auth, overrides, field, reason):
    response = client.post(URL, json=payload(**overrides), headers=auth(Role.TESTER))
    body = response.json()

    assert response.status_code == 422
    assert body["code"] == "VALIDATION_FAILED"
    assert field in [e["field"] for e in body["errors"]]
    if reason:
        assert {"field": field, "reason": reason} in body["errors"]


def test_inactive_classifier_is_rejected_for_new_values(client, auth):
    admin = auth(Role.ADMIN)
    client.put("/api/v1/admin/classifiers/PRIORITY/LOW", json={"isActive": False}, headers=admin)

    response = client.post(URL, json=payload(priority="LOW"), headers=auth(Role.TESTER))

    assert response.status_code == 422
    assert {"field": "priority", "reason": "inactive"} in response.json()["errors"]


def test_create_from_template_fills_missing_fields(client, auth, db_session):
    template = TestCaseTemplate(
        name="API",
        body={
            "priority": "LOW",
            "severity": "MINOR",
            "type": "FUNCTIONAL",
            "preconditions": "Токен qa-executor",
            "steps": [{"action": "Запрос", "expectedResult": "200"}],
        },
    )
    db_session.add(template)
    db_session.flush()
    body = {"title": "Из шаблона", "module": "RM", "templateId": str(template.id)}

    case = client.post(URL, json=body, headers=auth(Role.TESTER)).json()

    assert case["templateId"] == str(template.id)
    assert (case["priority"], case["severity"], case["type"]) == ("LOW", "MINOR", "FUNCTIONAL")
    assert case["preconditions"] == "Токен qa-executor"
    assert [s["action"] for s in case["steps"]] == ["Запрос"]


def test_inactive_template_is_rejected(client, auth, db_session):
    template = TestCaseTemplate(name="Старый", body={}, is_active=False)
    db_session.add(template)
    db_session.flush()

    response = client.post(
        URL, json=payload(templateId=str(template.id)), headers=auth(Role.TESTER)
    )

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "templateId", "reason": "inactive"}]


def test_get_unknown_case_is_404(client, auth):
    response = client.get(f"{URL}/{uuid.uuid4()}", headers=auth(Role.VIEWER))
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# --- Версии ------------------------------------------------------------------------------


def test_content_change_creates_new_immutable_version(client, auth, create):
    case = create()
    changed = payload(title="Новое название", steps=[{"action": "Один", "expectedResult": "Да"}])

    saved = client.put(f"{URL}/{case['id']}", json=changed, headers=auth(Role.TESTER, "petrov"))

    assert saved.status_code == 200
    assert saved.json()["version"] == 2
    assert saved.json()["title"] == "Новое название"
    old = client.get(f"{URL}/{case['id']}", params={"version": 1}, headers=auth(Role.VIEWER))
    assert old.json()["title"] == case["title"]
    assert old.json()["version"] == 1
    assert old.json()["currentVersion"] == 2
    assert [s["id"] for s in old.json()["steps"]] == [s["id"] for s in case["steps"]]
    versions = client.get(f"{URL}/{case['id']}/versions", headers=auth(Role.VIEWER)).json()
    assert [(v["version"], v["author"], v["changedFields"]) for v in versions["items"]] == [
        (2, "petrov", ["title", "steps"]),
        (1, "demo-qa-tester", []),
    ]


def test_save_without_changes_keeps_version(client, auth, create):
    case = create()

    saved = client.put(f"{URL}/{case['id']}", json=payload(), headers=auth(Role.TESTER))

    assert saved.json()["version"] == 1


def test_omitted_fields_are_kept_from_current_version(client, auth, create):
    case = create(description="Описание")

    saved = client.put(
        f"{URL}/{case['id']}",
        json={"title": "Только название", "module": "RM"},
        headers=auth(Role.TESTER),
    ).json()

    assert saved["version"] == 2
    assert saved["description"] == "Описание"
    assert len(saved["steps"]) == 2
    assert saved["priority"] == "HIGH"


def test_reference_change_does_not_create_version(client, auth, create):
    case = create()

    saved = client.put(
        f"{URL}/{case['id']}", json=payload(epicRef="EPIC-7"), headers=auth(Role.TESTER)
    ).json()

    assert saved["version"] == 1
    assert saved["epicRef"] == "EPIC-7"


def test_unchanged_inactive_classifier_does_not_block_save(client, auth, create, db_session):
    case = create(priority="LOW")
    db_session.get(ClassifierValue, ("PRIORITY", "LOW")).is_active = False
    db_session.flush()

    saved = client.put(
        f"{URL}/{case['id']}",
        json=payload(priority="LOW", title="Правка"),
        headers=auth(Role.TESTER),
    )

    assert saved.status_code == 200
    assert saved.json()["version"] == 2


def test_stale_version_is_conflict(client, auth, create):
    case = create()
    client.put(f"{URL}/{case['id']}", json=payload(title="Первый"), headers=auth(Role.TESTER))

    response = client.put(
        f"{URL}/{case['id']}", json=payload(title="Второй", version=1), headers=auth(Role.TESTER)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "VERSION_CONFLICT"
    assert response.json()["errors"] == [{"field": "version", "reason": "current:2"}]


def test_parallel_save_loses_on_unique_version(client, auth, create, db_session):
    """Другой запрос уже вставил версию 2, но ещё не поднял current_version."""
    case = create()
    rival = TestCaseVersion(
        test_case_id=uuid.UUID(case["id"]),
        version=2,
        title="Чужая правка",
        priority="HIGH",
        severity="MAJOR",
        type="NEGATIVE",
        changed_fields=["title"],
        author="rival",
    )
    db_session.add(rival)
    db_session.flush()

    response = client.put(
        f"{URL}/{case['id']}", json=payload(title="Моя"), headers=auth(Role.TESTER)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "VERSION_CONFLICT"


def test_archived_case_cannot_be_saved(client, auth, create):
    case = create()
    make_actual(client, auth, case["id"])
    set_status(client, auth, case["id"], "ARCHIVED")

    response = client.put(f"{URL}/{case['id']}", json=payload(title="X"), headers=auth(Role.TESTER))

    assert response.status_code == 409
    assert response.json()["code"] == "CASE_ARCHIVED"


def test_module_is_immutable(client, auth, create):
    case = create()

    response = client.put(
        f"{URL}/{case['id']}", json=payload(module="TT"), headers=auth(Role.TESTER)
    )

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "module", "reason": "immutable"}]


def test_case_of_module_outside_list_stays_editable(client, auth, create, db_session):
    case = create()
    db_session.get(TestCase, uuid.UUID(case["id"])).module = "QA"
    db_session.commit()

    response = client.put(
        f"{URL}/{case['id']}",
        json=payload(module="QA", title="Новое название"),
        headers=auth(Role.TESTER),
    )

    assert response.status_code == 200
    assert response.json()["version"] == 2


def test_actual_case_keeps_at_least_one_step(client, auth, create):
    case = create()
    make_actual(client, auth, case["id"])

    response = client.put(f"{URL}/{case['id']}", json=payload(steps=[]), headers=auth(Role.TESTER))

    assert response.status_code == 422
    assert {"field": "steps", "reason": "required"} in response.json()["errors"]


# --- Автоматизация -----------------------------------------------------------------------


def test_automation_fields_need_automation_or_lead(client, auth, create):
    automated = payload(automated=True, autotestKey="rm/test_health.py::test_readyz")

    assert client.post(URL, json=automated, headers=auth(Role.TESTER)).status_code == 403
    case = create(role=Role.AUTOMATION, **automated)
    assert case["automated"] is True
    tester_edit = client.put(f"{URL}/{case['id']}", json=payload(), headers=auth(Role.TESTER))
    assert tester_edit.status_code == 200  # поля автоматизации не присланы — не меняются
    unlink = payload(automated=False, autotestKey=None)
    assert (
        client.put(f"{URL}/{case['id']}", json=unlink, headers=auth(Role.TESTER)).status_code == 403
    )
    assert (
        client.put(f"{URL}/{case['id']}", json=unlink, headers=auth(Role.LEAD)).status_code == 200
    )


def test_automated_case_requires_key(client, auth):
    response = client.post(URL, json=payload(automated=True), headers=auth(Role.AUTOMATION))

    assert response.status_code == 422
    assert {"field": "autotestKey", "reason": "required"} in response.json()["errors"]


# --- Статусы -----------------------------------------------------------------------------


ALL_STATUSES = ["DRAFT", "ACTUAL", "NEEDS_UPDATE", "ARCHIVED"]
ALLOWED = {
    ("DRAFT", "ACTUAL"),
    ("ACTUAL", "NEEDS_UPDATE"),
    ("ACTUAL", "ARCHIVED"),
    ("NEEDS_UPDATE", "ACTUAL"),
    ("NEEDS_UPDATE", "ARCHIVED"),
    ("ARCHIVED", "ACTUAL"),
}
PATH_TO = {
    "DRAFT": [],
    "ACTUAL": ["ACTUAL"],
    "NEEDS_UPDATE": ["ACTUAL", "NEEDS_UPDATE"],
    "ARCHIVED": ["ACTUAL", "ARCHIVED"],
}


@pytest.mark.parametrize("source", ALL_STATUSES)
@pytest.mark.parametrize("target", ALL_STATUSES)
def test_every_status_transition(client, auth, create, source, target):
    case = create()
    for step in PATH_TO[source]:
        assert set_status(client, auth, case["id"], step).status_code == 200

    response = set_status(client, auth, case["id"], target)

    if (source, target) in ALLOWED:
        assert response.status_code == 200
        assert response.json()["status"] == target
    else:
        assert response.status_code == 409
        assert response.json()["code"] == "INVALID_TRANSITION"
        assert response.json()["errors"][0]["reason"].startswith("allowed:")


def test_draft_without_steps_is_not_ready(client, auth, create):
    case = create(steps=[])

    response = set_status(client, auth, case["id"], "ACTUAL")

    assert response.status_code == 409
    assert response.json()["code"] == "CASE_NOT_READY"


def test_viewer_cannot_change_status(client, auth, create):
    case = create()
    assert set_status(client, auth, case["id"], "ACTUAL", role=Role.VIEWER).status_code == 403


# --- Удаление ----------------------------------------------------------------------------


def test_delete_own_draft_with_versions_and_steps(client, auth, create, db_session):
    case = create(user="ivanov")
    client.put(f"{URL}/{case['id']}", json=payload(title="v2"), headers=auth(Role.TESTER))

    response = client.delete(f"{URL}/{case['id']}", headers=auth(Role.TESTER, "ivanov"))

    assert response.status_code == 204
    assert client.get(f"{URL}/{case['id']}", headers=auth(Role.VIEWER)).status_code == 404
    versions = select(TestCaseVersion).where(TestCaseVersion.test_case_id == uuid.UUID(case["id"]))
    assert db_session.scalars(versions).all() == []


def test_delete_someone_elses_draft_needs_lead(client, auth, create):
    case = create(user="ivanov")

    assert (
        client.delete(f"{URL}/{case['id']}", headers=auth(Role.TESTER, "petrov")).status_code == 403
    )
    assert client.delete(f"{URL}/{case['id']}", headers=auth(Role.LEAD)).status_code == 204


def test_delete_non_draft_is_invalid_transition(client, auth, create):
    case = create()
    make_actual(client, auth, case["id"])

    response = client.delete(f"{URL}/{case['id']}", headers=auth(Role.TESTER))

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"


def test_delete_draft_with_runs_is_case_has_runs(client, auth, create, db_session):
    case = create()
    add_result(db_session, uuid.UUID(case["id"]), status="NOT_RUN")

    response = client.delete(f"{URL}/{case['id']}", headers=auth(Role.TESTER))

    assert response.status_code == 409
    assert response.json()["code"] == "CASE_HAS_RUNS"


def test_delete_draft_with_defect_is_case_has_runs(client, auth, create, db_session):
    case = create()
    db_session.add(
        Defect(
            key="DEF-01",
            origin="MANUAL",
            title="Падение",
            actual_result="500",
            severity="MAJOR",
            proposed_priority="HIGH",
            status="NEW",
            author="t",
            test_case_id=uuid.UUID(case["id"]),
        )
    )
    db_session.flush()

    response = client.delete(f"{URL}/{case['id']}", headers=auth(Role.TESTER))

    assert response.json()["code"] == "CASE_HAS_RUNS"


def test_delete_source_of_copy_keeps_copy(client, auth, create):
    source = create()
    copy = client.post(f"{URL}/copy", json={"ids": [source["id"]]}, headers=auth(Role.TESTER))

    assert client.delete(f"{URL}/{source['id']}", headers=auth(Role.TESTER)).status_code == 204
    copy_id = copy.json()["items"][0]["id"]
    assert client.get(f"{URL}/{copy_id}", headers=auth(Role.VIEWER)).json()["copiedFromId"] is None


# --- Копирование -------------------------------------------------------------------------


def test_copy_is_atomic_draft_with_link_to_source(client, auth, create):
    first = create()
    make_actual(client, auth, first["id"])
    second = create(
        role=Role.AUTOMATION, module="TT", automated=True, autotestKey="tt/test_tasks.py::test_x"
    )

    response = client.post(
        f"{URL}/copy", json={"ids": [first["id"], second["id"]]}, headers=auth(Role.TESTER)
    )

    assert response.status_code == 201
    copies = response.json()["items"]
    assert [c["key"] for c in copies] == ["TC-RM-02", "TC-TT-02"]
    assert [c["copiedFromId"] for c in copies] == [first["id"], second["id"]]
    assert all(c["status"] == "DRAFT" and c["version"] == 1 for c in copies)
    assert copies[0]["title"] == first["title"]
    assert [s["action"] for s in copies[0]["steps"]] == [s["action"] for s in first["steps"]]
    assert copies[0]["steps"][0]["id"] != first["steps"][0]["id"]
    assert copies[1]["automated"] is False and copies[1]["autotestKey"] is None


def test_copy_with_unknown_id_creates_nothing(client, auth, create, db_session):
    case = create()

    response = client.post(
        f"{URL}/copy", json={"ids": [case["id"], str(uuid.uuid4())]}, headers=auth(Role.TESTER)
    )

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "ids.1", "reason": "not_found"}]
    assert len(db_session.scalars(select(TestCase)).all()) == 1


# --- Список ------------------------------------------------------------------------------


def test_list_filters(client, auth, create):
    a = create(title="Health")
    b = create(module="TT", type="FUNCTIONAL", epicRef="EPIC-1")
    c = create(role=Role.AUTOMATION, automated=True, autotestKey="k")
    make_actual(client, auth, c["id"])
    archived = create(title="Старый")
    make_actual(client, auth, archived["id"])
    set_status(client, auth, archived["id"], "ARCHIVED")

    def keys(**params):
        response = client.get(URL, params=params, headers=auth(Role.VIEWER))
        assert response.status_code == 200
        return [item["key"] for item in response.json()["items"]]

    assert keys() == [a["key"], c["key"], b["key"]]  # архивные скрыты
    everything = [a["key"], c["key"], archived["key"], b["key"]]
    assert keys(includeArchived=True) == everything
    assert keys(includeArchived=True, status="ACTUAL") == [c["key"]]
    assert keys(module="TT") == [b["key"]]
    assert keys(type="FUNCTIONAL") == [b["key"]]
    assert keys(epicRef="EPIC-1") == [b["key"]]
    assert keys(automated=True) == [c["key"]]
    assert keys(status="ACTUAL") == [c["key"]]
    assert keys(status="ARCHIVED") == [archived["key"]]
    assert keys(q="heal") == [a["key"]]
    assert keys(q="tc-tt") == [b["key"]]
    assert keys(q="100%") == []


def test_list_pagination(client, auth, create):
    for _ in range(5):
        create()

    response = client.get(URL, params={"page": 2, "pageSize": 2}, headers=auth(Role.VIEWER))
    body = response.json()

    assert [item["key"] for item in body["items"]] == ["TC-RM-03", "TC-RM-04"]
    assert (body["page"], body["pageSize"], body["totalPages"]) == (2, 2, 3)
    assert client.get(URL, params={"pageSize": 201}, headers=auth(Role.VIEWER)).status_code == 422


def test_list_shows_current_version(client, auth, create):
    case = create()
    client.put(f"{URL}/{case['id']}", json=payload(title="Вторая"), headers=auth(Role.TESTER))

    item = client.get(URL, headers=auth(Role.VIEWER)).json()["items"][0]

    assert (item["version"], item["title"]) == (2, "Вторая")


# --- Последний результат (ADR-014) ---------------------------------------------------------


def test_last_result_is_latest_finished_non_not_run(client, auth, create, db_session):
    case = create()
    case_id = uuid.UUID(case["id"])
    now = datetime.now(UTC)
    add_result(db_session, case_id, status="PASSED", finished_at=now - timedelta(days=1))
    latest = add_result(db_session, case_id, status="FAILED", finished_at=now, env_code="staging")
    add_result(db_session, case_id, status="NOT_RUN")

    card = client.get(f"{URL}/{case['id']}", headers=auth(Role.VIEWER)).json()
    listed = client.get(URL, headers=auth(Role.VIEWER)).json()["items"][0]

    expected = {
        "runId": str(latest.id),
        "runKey": latest.key,
        "caseVersion": 1,
        "status": "FAILED",
        "actualResult": "201 Created вместо 409",
        "failedStepPosition": 2,
        "environment": "staging",
    }
    assert {k: card["lastResult"][k] for k in expected} == expected
    assert listed["lastResult"]["runId"] == str(latest.id)


# --- Права -------------------------------------------------------------------------------


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
def test_role_matrix(client, auth, create, role, can_read, can_write):
    case = create()
    headers = auth(role)

    read = client.get(URL, headers=headers).status_code
    card = client.get(f"{URL}/{case['id']}", headers=headers).status_code
    versions = client.get(f"{URL}/{case['id']}/versions", headers=headers).status_code
    write = client.post(URL, json=payload(), headers=headers).status_code
    copy = client.post(f"{URL}/copy", json={"ids": [case["id"]]}, headers=headers).status_code
    edit = client.put(f"{URL}/{case['id']}", json=payload(), headers=headers).status_code

    assert {read, card, versions} == ({200} if can_read else {403})
    assert {write, copy} == ({201} if can_write else {403})
    assert edit == (200 if can_write else 403)


def test_no_token_is_401(client):
    assert client.get(URL).status_code == 401
