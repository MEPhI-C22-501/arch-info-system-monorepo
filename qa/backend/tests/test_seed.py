"""Демо-данные: состав по vision 7, идемпотентность, счётчики ключей, доступ через API."""

from sqlalchemy import func, select

from app.auth import Role
from app.keys import next_key
from app.models import (
    ClassifierValue,
    Environment,
    TestCase,
    TestCaseTemplate,
    TestCaseVersion,
    TestStep,
    TestSuite,
)
from app.seed import load

TABLES = (
    ClassifierValue,
    Environment,
    TestCaseTemplate,
    TestCase,
    TestCaseVersion,
    TestStep,
    TestSuite,
)


def counts(session):
    return {
        table.__name__: session.scalar(select(func.count()).select_from(table)) for table in TABLES
    }


def test_seed_contents(db_session):
    created = load(db_session)

    assert created == {
        "classifiers": 13,
        "environments": 1,
        "templates": 2,
        "test-cases": 25,
        "suites": 2,
    }
    keys = db_session.scalars(select(TestCase.key).order_by(TestCase.key)).all()
    for prefix in ("RM", "TT", "PS", "REP", "INF"):
        assert [k for k in keys if k.startswith(f"TC-{prefix}-")] == [
            f"TC-{prefix}-0{i}" for i in range(1, 6)
        ]
    assert db_session.scalar(select(Environment.code)) == "dev"


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
