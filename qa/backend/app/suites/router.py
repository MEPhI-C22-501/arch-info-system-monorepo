import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import Principal, Role, require_roles
from app.db import get_session
from app.models.enums import SuiteKind, SuitePurpose, SuiteStatus
from app.schemas import Page, PageParams
from app.suites import service
from app.suites.schemas import Suite, SuiteInput

router = APIRouter(prefix="/suites", tags=["suites"])

# 070, раздел 3: читают все люди, меняют R-02…R-04; «Smoke» и «Приёмку стенда» — R-04.
readers = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
editors = require_roles(Role.TESTER, Role.AUTOMATION, Role.LEAD)


@router.get("", response_model=Page[Suite], dependencies=[Depends(readers)])
def list_suites(
    status: SuiteStatus | None = None,
    purpose: SuitePurpose | None = None,
    kind: SuiteKind | None = None,
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
):
    return service.list_suites(session, status, purpose, kind, params)


@router.post("", response_model=Suite, status_code=status.HTTP_201_CREATED)
def create_suite(
    data: SuiteInput,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.create_suite(session, data, principal)


@router.get("/{id}", response_model=Suite, dependencies=[Depends(readers)])
def get_suite(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.read_suite(session, id)


@router.put("/{id}", response_model=Suite)
def update_suite(
    id: uuid.UUID,
    data: SuiteInput,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.update_suite(session, id, data, principal)


@router.post("/{id}/archive", response_model=Suite)
def archive_suite(
    id: uuid.UUID,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.archive_suite(session, id, principal)


@router.post("/{id}/restore", response_model=Suite)
def restore_suite(
    id: uuid.UUID,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.restore_suite(session, id, principal)
