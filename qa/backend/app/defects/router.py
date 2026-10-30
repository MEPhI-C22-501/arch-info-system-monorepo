import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import Principal, Role, require_roles
from app.db import get_session
from app.defects import service
from app.defects.schemas import (
    Defect,
    DefectComment,
    DefectCommentInput,
    DefectDetail,
    DefectHistoryList,
    DefectInput,
    DefectTransition,
    DefectUpdate,
)
from app.models.enums import DefectStatus, Severity
from app.schemas import Page, PageParams

router = APIRouter(prefix="/defects", tags=["defects"])

# 070, раздел 4.
readers = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
editors = require_roles(Role.TESTER, Role.AUTOMATION, Role.LEAD)
commenters = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD)
transitions = require_roles(Role.TESTER, Role.LEAD)


@router.get("", response_model=Page[Defect], dependencies=[Depends(readers)])
def list_defects(
    status: DefectStatus | None = None,
    severity: Severity | None = None,
    author: str | None = None,
    tracker_mismatch: bool | None = Query(None, alias="trackerMismatch"),
    planning_project_id: str | None = Query(None, alias="planningProjectId"),
    planning_release_id: str | None = Query(None, alias="planningReleaseId"),
    tracker_iteration_id: str | None = Query(None, alias="trackerIterationId"),
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
):
    return service.list_defects(
        session,
        params,
        status=status,
        severity=severity,
        author=author,
        tracker_mismatch=tracker_mismatch,
        planning_project_id=planning_project_id,
        planning_release_id=planning_release_id,
        tracker_iteration_id=tracker_iteration_id,
    )


@router.post("", response_model=DefectDetail, status_code=status.HTTP_201_CREATED)
def create_defect(
    data: DefectInput,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.create_defect(session, data, principal)


@router.get("/{id}", response_model=DefectDetail, dependencies=[Depends(readers)])
def get_defect(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.read_defect(session, id)


@router.put("/{id}", response_model=DefectDetail)
def update_defect(
    id: uuid.UUID,
    data: DefectUpdate,
    principal: Principal = Depends(editors),
    session: Session = Depends(get_session),
):
    return service.update_defect(session, id, data, principal)


@router.post("/{id}/transitions", response_model=DefectDetail)
def transition_defect(
    id: uuid.UUID,
    data: DefectTransition,
    principal: Principal = Depends(transitions),
    session: Session = Depends(get_session),
):
    return service.transition(session, id, data.to, data.comment, principal)


@router.get("/{id}/history", response_model=DefectHistoryList, dependencies=[Depends(readers)])
def list_defect_history(id: uuid.UUID, session: Session = Depends(get_session)):
    return DefectHistoryList(items=service.list_history(session, id))


@router.post("/{id}/comments", response_model=DefectComment, status_code=status.HTTP_201_CREATED)
def add_defect_comment(
    id: uuid.UUID,
    data: DefectCommentInput,
    principal: Principal = Depends(commenters),
    session: Session = Depends(get_session),
):
    return service.add_comment(session, id, data, principal)
