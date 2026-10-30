"""Демо-данные: состав по vision 7, идемпотентность, счётчики ключей, доступ через API."""

from sqlalchemy import func, select

from app.auth import Role
from app.keys import next_key
from app.models import (
    ClassifierValue,
    Defect,
    DefectHistory,
    DefectRunLink,
    Environment,
    OutboxMessage,
    RunResult,
    TestCase,
    TestCaseTemplate,
    TestCaseVersion,
    TestPlan,
    TestPlanCase,
    TestRun,
    TestStep,
    TestSuite,
    TrackerStatusMapping,
)
from app.seed import SEED_DIR, _load_plans, _read, load

TABLES = (
    ClassifierValue,
    Environment,
    TestCaseTemplate,
    TestCase,
    TestCaseVersion,
    TestStep,
    TestSuite,
    TrackerStatusMapping,
    TestPlan,
    TestPlanCase,
    TestRun,
    RunResult,
    Defect,
    DefectRunLink,
    DefectHistory,
    OutboxMessage,
)


def counts(session):
    return {
        table.__name__: session.scalar(select(func.count()).select_from(table)) for table in TABLES
    }


def test_seed_contents(db_session):
    created = load(db_session)

    assert created == {
        "classifiers": 13,
        "environments": 2,
        "templates": 2,
        "test-cases": 25,
        "suites": 2,
        "tracker-status-mapping": 5,
        "plans": 1,
    }
    keys = db_session.scalars(select(TestCase.key).order_by(TestCase.key)).all()
    for prefix in ("RM", "TT", "PS", "REP", "INF"):
        assert [k for k in keys if k.startswith(f"TC-{prefix}-")] == [
            f"TC-{prefix}-0{i}" for i in range(1, 6)
        ]
    assert set(db_session.scalars(select(Environment.code))) == {"dev", "staging"}


def test_seed_is_idempotent(db_session):
    load(db_session)
    before = counts(db_session)

    again = load(db_session)

    assert set(again.values()) == {0}
    assert counts(db_session) == before


def test_seed_keeps_user_changes(db_session):
    load(db_session)
    db_session.get(ClassifierValue, ("SEVERITY", "MAJOR")).name = "Major"
    db_session.flush()

    load(db_session)

    assert db_session.get(ClassifierValue, ("SEVERITY", "MAJOR")).name == "Major"


def test_key_counters_continue_after_seed(db_session):
    next_key(db_session, "TC-RM")  # счётчик уже был: seed поднимает его, а не сбрасывает
    load(db_session)
    load(db_session)

    assert next_key(db_session, "TC-RM") == "TC-RM-06"
    assert next_key(db_session, "TC-REP") == "TC-REP-06"


def test_seed_is_visible_through_api(client, auth, db_session):
    load(db_session)
    lead = auth(Role.LEAD)

    cases = client.get("/api/v1/test-cases", params={"pageSize": 50}, headers=lead).json()
    suites = {s["name"]: s for s in client.get("/api/v1/suites", headers=lead).json()["items"]}

    assert len(cases["items"]) == 25
    assert all(c["status"] == "ACTUAL" and c["steps"] for c in cases["items"])
    assert set(suites) == {"Smoke", "Приёмка стенда"}
    assert (suites["Приёмка стенда"]["purpose"], suites["Приёмка стенда"]["caseCount"]) == (
        "ACCEPTANCE",
        25,
    )
    # «Smoke» — кейсы стартового набора с реализованным автотестом; на 12.10.2026 их нет.
    assert suites["Smoke"]["purpose"] == "SMOKE"
    assert suites["Smoke"]["filter"]["suiteId"] == suites["Приёмка стенда"]["id"]
    assert suites["Smoke"]["caseCount"] == 0


def test_demo_plan_run_and_defect(client, auth, db_session):
    load(db_session)
    lead = auth(Role.LEAD)

    plans = client.get("/api/v1/test-plans", headers=lead).json()["items"]
    assert [(p["key"], p["status"], p["scopeKind"]) for p in plans] == [
        ("TP-01", "ACTIVE", "RELEASE")
    ]
    assert plans[0]["caseCount"] == 25
    assert plans[0]["planningProjectId"] and plans[0]["planningReleaseId"]

    runs = client.get("/api/v1/runs", headers=lead).json()["items"]
    assert [(r["key"], r["status"], r["environment"]) for r in runs] == [
        ("RUN-01", "COMPLETED", "dev")
    ]
    assert runs[0]["planId"] == plans[0]["id"]
    summary = runs[0]["summary"]
    assert (summary["total"], summary["passed"], summary["failed"]) == (25, 8, 1)
    assert runs[0]["smokeVerdict"] == "RED"

    defects = client.get("/api/v1/defects", headers=lead).json()["items"]
    assert [(d["key"], d["origin"], d["status"], d["testCaseKey"]) for d in defects] == [
        ("DEF-01", "AUTO", "NEW", "TC-TT-04")
    ]
    assert defects[0]["runIds"] == [runs[0]["id"]]
    assert db_session.scalars(select(OutboxMessage.kind)).all() == ["TRACKER_BUG"]

    case = next(
        c
        for c in client.get("/api/v1/test-cases", headers=lead).json()["items"]
        if c["key"] == "TC-TT-04"
    )
    assert case["lastResult"]["runKey"] == "RUN-01"
    assert case["lastResult"]["status"] == "FAILED"


def test_key_counters_of_demo_objects(db_session):
    load(db_session)

    assert next_key(db_session, "TP") == "TP-02"
    assert next_key(db_session, "RUN") == "RUN-02"
    assert next_key(db_session, "DEF") == "DEF-02"


def test_tracker_mapping_follows_vision(client, auth, db_session):
    load(db_session)

    rows = client.get("/api/v1/admin/tracker-status-mapping", headers=auth(Role.ADMIN)).json()

    assert [
        (r["trackerStatusName"], r["qaStatus"], r["requiresAssignee"]) for r in rows["items"]
    ] == [
        ("Бэклог", "OPEN", True),
        ("В работе", "IN_PROGRESS", False),
        ("На проверке", "FIXED", False),
        ("Завершена", None, False),
        ("Архивирована", None, False),
    ]


def test_seed_skips_case_that_is_no_longer_actual(db_session):
    """На томе с правками seed не падает: иначе qa-api не запустится."""
    load(db_session)
    case = db_session.scalar(select(TestCase).where(TestCase.key == "TC-TT-04"))
    case.status = "NEEDS_UPDATE"
    db_session.flush()
    plans = _read(SEED_DIR, "plans")
    plans[0]["key"] = "TP-99"

    assert _load_plans(db_session, plans) == 1

    plan = db_session.scalar(select(TestPlan).where(TestPlan.key == "TP-02"))
    members = select(func.count()).select_from(TestPlanCase).where(TestPlanCase.plan_id == plan.id)
    assert db_session.scalar(members) == 24
