"""Reference Manager projection and scoped QA profile reads."""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import select, text, union
from sqlalchemy.orm import Session

from app.auth import Principal, Role, require_roles
from app.config import get_settings
from app.db import get_engine, get_session
from app.errors import ApiError
from app.models import (
    Defect,
    DefectComment,
    DefectHistory,
    EmployeeCache,
    RunResult,
    TestCase,
    TestCaseVersion,
    TestPlan,
    TestRun,
    TestSuite,
)
from app.schemas import ApiModel, Page, PageParams, paginate

router = APIRouter(tags=["profiles"])
human = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
log = logging.getLogger(__name__)


class Profile(ApiModel):
    account_user_id: str
    display_name: str


class ProfileLookup(ApiModel):
    subjects: list[str] = Field(min_length=1, max_length=100)


@router.get("/profile")
def self_profile(
    principal: Principal = Depends(human),
    session: Session = Depends(get_session),
) -> Profile | None:
    cached = session.scalar(
        select(EmployeeCache).where(EmployeeCache.account_user_id == principal.subject)
    )
    return Profile.model_validate(cached) if cached else None


@router.post("/profiles/resolve", dependencies=[Depends(human)])
def resolve_profiles(
    body: ProfileLookup,
    session: Session = Depends(get_session),
) -> list[Profile]:
    # A subject must appear in a QA object readable with the human QA roles.
    columns = (
        TestCase.created_by,
        TestCaseVersion.author,
        TestSuite.owner,
        TestPlan.owner,
        TestRun.started_by,
        RunResult.assignee,
        RunResult.executed_by,
        Defect.author,
        Defect.tracker_assignee,
        DefectHistory.author,
        DefectComment.author,
    )
    visible = union(*(select(column).where(column.in_(body.subjects)) for column in columns))
    rows = session.scalars(select(EmployeeCache).where(EmployeeCache.account_user_id.in_(visible)))
    return [Profile.model_validate(row) for row in rows]


@router.get("/profiles/assignees", dependencies=[Depends(require_roles(Role.LEAD))])
def eligible_assignees(
    q: str = Query("", max_length=120),
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
) -> Page[Profile]:
    stmt = (
        select(EmployeeCache)
        .where(
            EmployeeCache.is_active,
            EmployeeCache.account_user_id.is_not(None),
            EmployeeCache.synced_at >= datetime.now(UTC) - timedelta(hours=1),
            EmployeeCache.display_name.icontains(q, autoescape=True),
        )
        .order_by(EmployeeCache.display_name, EmployeeCache.account_user_id)
    )
    return paginate(session, stmt, params, Profile)


def require_current_owner(session: Session, subject: str) -> None:
    if get_settings().auth_mode == "demo":
        return
    if not session.scalar(
        select(EmployeeCache).where(
            EmployeeCache.account_user_id == subject,
            EmployeeCache.is_active,
            EmployeeCache.synced_at >= datetime.now(UTC) - timedelta(hours=1),
        )
    ):
        raise ApiError(
            422, "VALIDATION_ERROR", "Для назначения нужен актуальный профиль сотрудника"
        )


def _read(request: Request):
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def sync_profiles() -> None:
    base = os.environ["RM_BASE_URL"].rstrip("/")
    token_url = os.environ["RM_TOKEN_URL"]
    for url in (base, token_url):
        parsed = urlsplit(url)
        local = get_settings().app_env == "development" and parsed.hostname in {
            "keycloak",
            "reference-manager",
            "localhost",
            "127.0.0.1",
        }
        if parsed.username or parsed.password or not parsed.hostname:
            raise ValueError("Invalid Reference Manager URL")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
            raise ValueError("Reference Manager requires HTTPS")
    form = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": os.environ["RM_CLIENT_ID"],
            "client_secret": os.environ["RM_CLIENT_SECRET"],
        }
    ).encode()
    token = _read(Request(token_url, data=form))["access_token"]
    started = datetime.now(UTC)
    profiles, seen = {}, set()
    cursor = ""
    for _ in range(10000):
        params = {"pageSize": 100, "includeInactive": "true"}
        if cursor:
            params["pageToken"] = cursor
        body = _read(
            Request(
                f"{base}/profiles?{urlencode(params)}", headers={"Authorization": f"Bearer {token}"}
            )
        )
        if not isinstance(body["items"], list):
            raise ValueError("Malformed profile page")
        for row in body["items"]:
            if row["issuer"] != get_settings().oidc_issuer:
                raise ValueError("Unexpected profile issuer")
            subject, name = row["userId"], row["displayName"]
            if not subject or row["isTechnical"]:
                continue
            if subject in profiles or not name.strip():
                raise ValueError("Invalid profile identity")
            profiles[subject] = {
                "display_name": name,
                "org_unit": row["orgUnitName"],
                "is_active": (
                    row["isActive"] is True
                    and row["employmentState"] == "EMPLOYED"
                    and row["accountState"] == "ENABLED"
                ),
            }
        cursor = body.get("nextPageToken")
        if not cursor:
            break
        if not isinstance(cursor, str) or cursor in seen:
            raise ValueError("Invalid profile page token")
        seen.add(cursor)
    else:
        raise ValueError("Reference Manager page limit exceeded")

    with Session(get_engine()) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext('qa-profile-sync'))"))
        cached = {
            row.account_user_id: row
            for row in session.scalars(select(EmployeeCache))
            if row.account_user_id
        }
        if any(row.synced_at > started for row in cached.values()):
            return
        for subject, row in cached.items():
            if subject not in profiles:
                row.is_active = False
        for subject, data in profiles.items():
            row = cached.get(subject)
            if row is None:
                session.add(
                    EmployeeCache(
                        external_name=f"users/{subject}",
                        account_user_id=subject,
                        synced_at=started,
                        **data,
                    )
                )
                continue
            for key, value in data.items():
                setattr(row, key, value)
            row.synced_at = started


async def sync_forever():
    while True:
        try:
            await asyncio.to_thread(sync_profiles)
        except Exception:
            log.warning("Reference Manager profile refresh failed; keeping previous snapshot")
        await asyncio.sleep(900)
