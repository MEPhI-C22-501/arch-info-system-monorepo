"""Шаблоны кейсов: читают авторы кейсов, ведёт администратор (130, 070 раздел 2)."""

import pytest

from app.auth import Role

pytestmark = pytest.mark.usefixtures("classifiers")

URL = "/api/v1/templates"


def template(name="Проверка API", **body):
    return {
        "name": name,
        "description": "HTTP-проверка",
        "body": {
            "priority": "MEDIUM",
            "type": "FUNCTIONAL",
            "steps": [{"action": "Запрос", "expectedResult": "200"}],
            **body,
        },
    }


def test_create_read_update(client, auth):
    created = client.post(URL, json=template(), headers=auth(Role.ADMIN))

    assert created.status_code == 201
    item = created.json()
    assert item["isActive"] is True
    assert item["body"]["steps"] == [{"action": "Запрос", "expectedResult": "200"}]
    assert item["body"]["severity"] is None

    changed = template(severity="MINOR")
    changed["isActive"] = False
    updated = client.put(f"{URL}/{item['id']}", json=changed, headers=auth(Role.ADMIN)).json()
    assert (updated["body"]["severity"], updated["isActive"]) == ("MINOR", False)
    card = client.get(f"{URL}/{item['id']}", headers=auth(Role.TESTER)).json()
    assert card == updated


def test_list_filters_active(client, auth):
    client.post(URL, json=template("А"), headers=auth(Role.ADMIN))
    inactive = template("Б")
    inactive["isActive"] = False
    client.post(URL, json=inactive, headers=auth(Role.ADMIN))

    all_items = client.get(URL, headers=auth(Role.TESTER)).json()["items"]
    active = client.get(URL, params={"isActive": True}, headers=auth(Role.TESTER)).json()["items"]

    assert [t["name"] for t in all_items] == ["А", "Б"]
    assert [t["name"] for t in active] == ["А"]


@pytest.mark.parametrize(
    "body, field, reason",
    [
        ({"priority": "URGENT"}, "body.priority", "unknown"),
        ({"type": "EXPLORATORY"}, "body.type", "unknown"),
    ],
)
def test_template_codes_are_checked(client, auth, body, field, reason):
    response = client.post(URL, json=template(**body), headers=auth(Role.ADMIN))

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": field, "reason": reason}]


def test_template_name_is_unique(client, auth):
    first = client.post(URL, json=template(), headers=auth(Role.ADMIN)).json()

    duplicate = client.post(URL, json=template(), headers=auth(Role.ADMIN))
    same_on_update = client.put(f"{URL}/{first['id']}", json=template(), headers=auth(Role.ADMIN))

    assert duplicate.json()["errors"] == [{"field": "name", "reason": "duplicate"}]
    assert same_on_update.status_code == 200


@pytest.mark.parametrize(
    "role, can_read, can_write",
    [
        (Role.VIEWER, False, False),
        (Role.TESTER, True, False),
        (Role.AUTOMATION, True, False),
        (Role.LEAD, True, False),
        (Role.ADMIN, True, True),
        (Role.CI, False, False),
        (Role.REPORTS_READER, False, False),
    ],
)
def test_role_matrix(client, auth, role, can_read, can_write):
    existing = client.post(URL, json=template("Есть"), headers=auth(Role.ADMIN)).json()

    read = client.get(URL, headers=auth(role)).status_code
    create = client.post(URL, json=template("Новый"), headers=auth(role)).status_code
    edit = client.put(f"{URL}/{existing['id']}", json=template("Есть"), headers=auth(role))

    assert read == (200 if can_read else 403)
    assert create == (201 if can_write else 403)
    assert edit.status_code == (200 if can_write else 403)
