import uuid

from fastapi import APIRouter, Depends, Header, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.auth import Principal, Role, require_roles
from app.db import get_session
from app.models.enums import ResultStatus, RunStatus
from app.runs import service
from app.runs.schemas import ResultInput, Run, RunInput, RunResult
from app.schemas import Page, PageParams

router = APIRouter(prefix="/runs", tags=["runs"])

# 070, раздел 3. R-06 видит свои прогоны и запускает наборы; результаты читают люди (130).
result_readers = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
readers = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN, Role.CI)
starters = require_roles(Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.CI)
recorders = require_roles(Role.TESTER, Role.LEAD)
leads = require_roles(Role.LEAD)


@router.get("", response_model=Page[Run])
def list_runs(
    plan_id: uuid.UUID | None = Query(None, alias="planId"),
    suite_id: uuid.UUID | None = Query(None, alias="suiteId"),
    status: RunStatus | None = None,
    params: PageParams = Depends(),
    principal: Principal = Depends(readers),
    session: Session = Depends(get_session),
):
    return service.list_runs(session, principal, plan_id, suite_id, status, params)


@router.post("", response_model=Run, status_code=status.HTTP_201_CREATED)
def create_run(
    data: RunInput,
    response: Response,
    idempotency_key: str | None = Header(
        None, alias="Idempotency-Key", min_length=1, max_length=128
    ),
    principal: Principal = Depends(starters),
    session: Session = Depends(get_session),
):
    run, created = service.create_run(session, data, principal, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return run


@router.get("/{id}", response_model=Run)
def get_run(
    id: uuid.UUID,
    principal: Principal = Depends(readers),
    session: Session = Depends(get_session),
):
    return service.read_run(session, id, principal)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    id: uuid.UUID,
    principal: Principal = Depends(leads),
    session: Session = Depends(get_session),
):
    service.delete_run(session, id, principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/start", response_model=Run)
def start_run(
    id: uuid.UUID,
    principal: Principal = Depends(starters),
    session: Session = Depends(get_session),
):
    return service.start_run(session, id, principal)


@router.post("/{id}/complete", response_model=Run)
def complete_run(
    id: uuid.UUID,
    principal: Principal = Depends(leads),
    session: Session = Depends(get_session),
):
    return service.complete_run(session, id, principal)


@router.post("/{id}/abort", response_model=Run)
def abort_run(
    id: uuid.UUID,
    principal: Principal = Depends(leads),
    session: Session = Depends(get_session),
):
    return service.abort_run(session, id, principal)


@router.get("/{id}/results", response_model=Page[RunResult])
def list_run_results(
    id: uuid.UUID,
    status: ResultStatus | None = None,
    assignee: str | None = None,
    params: PageParams = Depends(),
    principal: Principal = Depends(result_readers),
    session: Session = Depends(get_session),
):
    return service.list_results(session, id, principal, status, assignee, params)


@router.put("/{id}/results/{resultId}", response_model=RunResult)
def record_result(
    id: uuid.UUID,
    data: ResultInput,
    result_id: uuid.UUID = Path(alias="resultId"),
    principal: Principal = Depends(recorders),
    session: Session = Depends(get_session),
):
    return service.record_result(session, id, result_id, data, principal)
