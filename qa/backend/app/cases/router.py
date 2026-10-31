import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth import Principal, Role, require_roles
from app.cases import service
from app.cases.schemas import (
    CaseFilter,
    CaseStatusInput,
    CopyInput,
    TestCase,
    TestCaseInput,
    TestCaseVersionList,
)
from app.db import get_session
from app.models.enums import CaseStatus
from app.schemas import Page, PageParams

router = APIRouter(prefix="/test-cases", tags=["test-cases"])

# 070, раздел 2.
readers = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
editors = require_roles(Role.TESTER, Role.AUTOMATION, Role.LEAD)


@router.get("", response_model=Page[TestCase], dependencies=[Depends(readers)])
def list_test_cases(
    module: str | None = None,
    status: CaseStatus | None = Query(None, description="Без статуса архивные не показываются"),
    include_archived: bool = Query(
        False, alias="includeArchived", description="Показать и архивные; status важнее"
    ),
    type: str | None = None,
    epic_ref: str | None = Query(None, alias="epicRef"),
    automated: bool | None = None,
    q: str | None = Query(None, description="Подстрока ключа или названия"),
    suite_id: uuid.UUID | None = Query(None, alias="suiteId", description="Состав набора"),
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
):
    case_filter = CaseFilter(
        module=module,
        status=status,
        type=type,
        epic_ref=epic_ref,
        automated=automated,
        q=q,
        suite_id=suite_id,
    )
    return service.list_cases(session, case_filter, params, include_archived)


@router.post("", response_model=TestCase, status_code=status.HTTP_201_CREATED)
def create_test_case(
    data: TestCaseInput,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.create_case(session, data, principal)


@router.post("/copy", response_model=Page[TestCase], status_code=status.HTTP_201_CREATED)
def copy_test_cases(
    data: CopyInput,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    copies = service.copy_cases(session, data.ids, principal)
    return Page[TestCase](items=copies, page=1, page_size=len(copies), total_pages=1)


@router.get("/{id}", response_model=TestCase, dependencies=[Depends(readers)])
def get_test_case(
    id: uuid.UUID,
    version: int | None = Query(None, ge=1),
    session: Session = Depends(get_session),
):
    return service.read_case(session, id, version)


@router.put("/{id}", response_model=TestCase)
def update_test_case(
    id: uuid.UUID,
    data: TestCaseInput,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.update_case(session, id, data, principal)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(
    id: uuid.UUID,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    service.delete_case(session, id, principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/status", response_model=TestCase)
def change_test_case_status(
    id: uuid.UUID,
    data: CaseStatusInput,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.change_status(session, id, data.status, principal)


@router.get("/{id}/versions", response_model=TestCaseVersionList, dependencies=[Depends(readers)])
def list_test_case_versions(id: uuid.UUID, session: Session = Depends(get_session)):
    return TestCaseVersionList(items=service.list_versions(session, id))
