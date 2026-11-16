"""Авторизация по ролям клиента qa-system."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

import jwt
from jwt import PyJWKClient
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


@lru_cache(maxsize=4)
def jwks(url: str) -> PyJWKClient:
    return PyJWKClient(url, timeout=5)


def _oidc_principal(token: str) -> Principal:
    settings = get_settings()
    url = settings.oidc_jwks_url or settings.oidc_issuer + "/protocol/openid-connect/certs"
    try:
        key = jwks(url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.oidc_issuer,
            audience="qa-system",
            options={"require": ["sub", "iss", "aud", "exp"]},
        )
        if not claims["sub"].strip() or claims.get("typ") != "Bearer":
            raise jwt.InvalidTokenError()
    except (jwt.PyJWTError, TypeError, ValueError) as exc:
        raise ApiError(401, "UNAUTHENTICATED", "Недействительный токен") from exc
    access = claims.get("resource_access")
    entry = access.get("qa-system") if isinstance(access, dict) else None
    names = entry.get("roles") if isinstance(entry, dict) else None
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        names = []
    return Principal(claims["sub"], frozenset(role for role in Role if role in names))


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
    return _oidc_principal(credentials.credentials)


def require_roles(*roles: Role) -> Callable[..., Principal]:
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.has_any(*roles):
            raise ApiError(403, "PERMISSION_DENIED", "Недостаточно прав для операции")
        return principal

    return dependency
