import uuid

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.auth import Principal, Role, require_roles
from app.db import get_session
from app.models.enums import PlanStatus
from app.plans import service
from app.plans.schemas import PlanCasesInput, PlanSummary, TestPlan, TestPlanInput
from app.schemas import Page, PageParams

router = APIRouter(prefix="/test-plans", tags=["test-plans"])

# 070, раздел 3: читают все люди, меняет QA-лид.
readers = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
leads = require_roles(Role.LEAD)


@router.get("", response_model=Page[TestPlan], dependencies=[Depends(readers)])
def list_test_plans(
    status: PlanStatus | None = None,
    tracker_iteration_id: str | None = Query(None, alias="trackerIterationId"),
    planning_project_id: str | None = Query(None, alias="planningProjectId"),
    planning_release_id: str | None = Query(None, alias="planningReleaseId"),
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
):
    return service.list_plans(
        session, status, tracker_iteration_id, planning_project_id, planning_release_id, params
    )


@router.post(
    "", response_model=TestPlan, status_code=status.HTTP_201_CREATED, dependencies=[Depends(leads)]
)
def create_test_plan(data: TestPlanInput, session: Session = Depends(get_session)):
    return service.create_plan(session, data)


@router.get("/{id}", response_model=TestPlan, dependencies=[Depends(readers)])
def get_test_plan(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.read_plan(session, id)


@router.put("/{id}", response_model=TestPlan, dependencies=[Depends(leads)])
def update_test_plan(id: uuid.UUID, data: TestPlanInput, session: Session = Depends(get_session)):
    return service.update_plan(session, id, data)


@router.post("/{id}/cases", response_model=TestPlan)
def add_plan_cases(
    id: uuid.UUID,
    data: PlanCasesInput,
    principal: Principal = Depends(leads),
    session: Session = Depends(get_session),
):
    return service.add_cases(session, id, data, principal)


@router.delete(
    "/{id}/cases/{caseId}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(leads)],
)
def remove_plan_case(
    id: uuid.UUID,
    case_id: uuid.UUID = Path(alias="caseId"),
    session: Session = Depends(get_session),
):
    service.remove_case(session, id, case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/activate", response_model=TestPlan, dependencies=[Depends(leads)])
def activate_test_plan(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.activate_plan(session, id)


@router.post("/{id}/complete", response_model=TestPlan, dependencies=[Depends(leads)])
def complete_test_plan(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.complete_plan(session, id)


@router.post("/{id}/cancel", response_model=TestPlan, dependencies=[Depends(leads)])
def cancel_test_plan(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.cancel_plan(session, id)


@router.get("/{id}/summary", response_model=PlanSummary, dependencies=[Depends(readers)])
def get_test_plan_summary(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.read_summary(session, id)
