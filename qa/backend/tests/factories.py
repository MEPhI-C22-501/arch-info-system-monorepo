"""Объекты для тестов через API: те же проверки и транзакции, что в работе."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models import Environment

API = "/api/v1"
CASES = f"{API}/test-cases"
SUITES = f"{API}/suites"
RUNS = f"{API}/runs"
PLANS = f"{API}/test-plans"
DEFECTS = f"{API}/defects"


def environment(session: Session, code: str = "dev", is_active: bool = True) -> Environment:
    row = Environment(code=code, name=code, base_urls={}, is_active=is_active)
    session.add(row)
    session.flush()
    return row


def new_case(client, headers, module="RM", status="ACTUAL", steps=2, **fields) -> dict:
    body = {
        "title": f"Кейс {module}",
        "module": module,
        "priority": "HIGH",
        "severity": "MAJOR",
        "type": "FUNCTIONAL",
        "preconditions": "Есть доступ",
        "steps": [
            {"action": f"Действие {i}", "expectedResult": f"Ожидание {i}"}
            for i in range(1, steps + 1)
        ],
        **fields,
    }
    created = client.post(CASES, json=body, headers=headers)
    assert created.status_code == 201, created.text
    case = created.json()
    if status in ("ACTUAL", "NEEDS_UPDATE", "ARCHIVED"):
        case = change_case_status(client, headers, case, "ACTUAL")
    if status in ("NEEDS_UPDATE", "ARCHIVED"):
        case = change_case_status(client, headers, case, status)
    return case


def change_case_status(client, headers, case, status) -> dict:
    changed = client.post(f"{CASES}/{case['id']}/status", json={"status": status}, headers=headers)
    assert changed.status_code == 200, changed.text
    return changed.json()


def new_suite(client, headers, cases=(), **fields) -> dict:
    body = {
        "name": f"Набор {uuid.uuid4().hex[:8]}",
        "kind": "MANUAL",
        "caseIds": [case["id"] for case in cases],
        **fields,
    }
    created = client.post(SUITES, json=body, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


def new_run(client, headers, cases, environment="dev", start=True) -> dict:
    """Прогон из нового ручного набора; кейсы должны быть актуальными."""
    suite = new_suite(client, headers, cases)
    body = {"suiteId": suite["id"], "environment": environment, "start": start}
    created = client.post(RUNS, json=body, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()


def run_results(client, headers, run) -> dict[str, dict]:
    listed = client.get(f"{RUNS}/{run['id']}/results", headers=headers)
    assert listed.status_code == 200, listed.text
    return {item["testCaseKey"]: item for item in listed.json()["items"]}


def record(client, headers, run, result, **body):
    url = f"{RUNS}/{run['id']}/results/{result['id']}"
    return client.put(url, json=body, headers=headers)


def fail(client, headers, run, result, actual="500", step=None):
    """Провал кейса; step — номер упавшего шага."""
    body = {"status": "FAILED"}
    if step is None:
        body["actualResult"] = actual
    else:
        step_id = result["steps"][step - 1]["stepId"]
        body["steps"] = [{"stepId": step_id, "status": "FAILED", "actualResult": actual}]
    response = record(client, headers, run, result, **body)
    assert response.status_code == 200, response.text
    return response.json()


def finish_run(client, headers, run) -> dict:
    finished = client.post(f"{RUNS}/{run['id']}/complete", headers=headers)
    assert finished.status_code == 200, finished.text
    return finished.json()


def new_plan(client, headers, cases=(), activate=False, **fields) -> dict:
    body = {
        "name": "План",
        "scopeKind": "MODULE",
        "scopeRef": "RM",
        "owner": "ivanov",
        "startDate": date(2026, 11, 1).isoformat(),
        "endDate": date(2026, 11, 30).isoformat(),
        **fields,
    }
    created = client.post(PLANS, json=body, headers=headers)
    assert created.status_code == 201, created.text
    plan = created.json()
    if cases:
        ids = [case["id"] for case in cases]
        added = client.post(f"{PLANS}/{plan['id']}/cases", json={"ids": ids}, headers=headers)
        assert added.status_code == 200, added.text
        plan = added.json()
    if activate:
        activated = client.post(f"{PLANS}/{plan['id']}/activate", headers=headers)
        assert activated.status_code == 200, activated.text
        plan = activated.json()
    return plan


def to_status(client, headers, defect, *statuses) -> dict:
    """Проводит дефект по цепочке статусов."""
    for status in statuses:
        moved = client.post(
            f"{DEFECTS}/{defect['id']}/transitions", json={"to": status}, headers=headers
        )
        assert moved.status_code == 200, moved.text
        defect = moved.json()
    return defect
