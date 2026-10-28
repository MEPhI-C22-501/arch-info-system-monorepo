"""Авторизация по ролям из 070.

Пока Keycloak не выдан (Q-06), работает только демо-режим: токен `demo-<роль>`
или `demo-<роль>@<пользователь>`, например `Bearer demo-qa-lead@ivanov`.
Проверка JWT Keycloak (ADR-011) — TECH-09.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errors import ApiError


class Role(StrEnum):
    VIEWER = "qa-viewer"  # R-01
    TESTER = "qa-tester"  # R-02
    AUTOMATION = "qa-automation"  # R-03
    LEAD = "qa-lead"  # R-04
    ADMIN = "qa-admin"  # R-05
    CI = "qa-ci"  # R-06
    REPORTS_READER = "qa-reports-reader"  # R-07


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[Role]

    def has_any(self, *roles: Role) -> bool:
        return bool(self.roles.intersection(roles))


_bearer = HTTPBearer(auto_error=False)


def _demo_principal(token: str) -> Principal:
    role_part, _, user = token.removeprefix("demo-").partition("@")
    if not token.startswith("demo-") or role_part not in Role._value2member_map_:
        raise ApiError(401, "UNAUTHENTICATED", "Недействительный токен")
    role = Role(role_part)
    return Principal(subject=user or f"demo-{role}", roles=frozenset({role}))


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None:
        raise ApiError(401, "UNAUTHENTICATED", "Нужен токен доступа")
    if get_settings().auth_mode == "demo":
        return _demo_principal(credentials.credentials)
    raise ApiError(401, "UNAUTHENTICATED", "Недействительный токен")


def require_roles(*roles: Role) -> Callable[..., Principal]:
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.has_any(*roles):
            raise ApiError(403, "PERMISSION_DENIED", "Недостаточно прав для операции")
        return principal

    return dependency
