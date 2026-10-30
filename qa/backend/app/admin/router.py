import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.admin import service
from app.admin.schemas import (
    Classifier,
    ClassifierInput,
    ClassifierUpdate,
    Environment,
    EnvironmentInput,
    EnvironmentUpdate,
    TrackerStatusMapping,
    TrackerStatusMappingInput,
)
from app.auth import Principal, Role, require_roles
from app.db import get_session
from app.models.enums import ClassifierKind
from app.schemas import Page, PageParams

router = APIRouter(prefix="/admin", tags=["admin"])

# Изменяет только администратор (070, раздел 5). Чтение открыто всем людям: значения нужны
# формам кейса и прогона, а в самих кейсах они и так видны.
readers = require_roles(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
admin = require_roles(Role.ADMIN)


@router.get("/classifiers", response_model=Page[Classifier], dependencies=[Depends(readers)])
def list_classifiers(
    kind: ClassifierKind | None = None,
    is_active: bool | None = Query(None, alias="isActive"),
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
):
    return service.list_classifiers(session, kind, is_active, params)


@router.post(
    "/classifiers",
    response_model=Classifier,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin)],
)
def create_classifier(data: ClassifierInput, session: Session = Depends(get_session)):
    return service.create_classifier(session, data)


@router.put("/classifiers/{kind}/{code}", response_model=Classifier, dependencies=[Depends(admin)])
def update_classifier(
    kind: ClassifierKind,
    code: str,
    data: ClassifierUpdate,
    session: Session = Depends(get_session),
):
    return service.update_classifier(session, kind, code, data)


@router.get("/environments", response_model=Page[Environment], dependencies=[Depends(readers)])
def list_environments(
    is_active: bool | None = Query(None, alias="isActive"),
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
):
    return service.list_environments(session, is_active, params)


@router.post(
    "/environments",
    response_model=Environment,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin)],
)
def create_environment(data: EnvironmentInput, session: Session = Depends(get_session)):
    return service.create_environment(session, data)


@router.put("/environments/{id}", response_model=Environment, dependencies=[Depends(admin)])
def update_environment(
    id: uuid.UUID, data: EnvironmentUpdate, session: Session = Depends(get_session)
):
    return service.update_environment(session, id, data)


# Маппинг статусов «Ошибки» ведёт администратор (070, раздел 5).
@router.get(
    "/tracker-status-mapping", response_model=TrackerStatusMapping, dependencies=[Depends(admin)]
)
def get_tracker_status_mapping(session: Session = Depends(get_session)):
    return TrackerStatusMapping(items=service.list_tracker_mapping(session))


@router.put("/tracker-status-mapping", response_model=TrackerStatusMapping)
def put_tracker_status_mapping(
    data: TrackerStatusMappingInput,
    principal: Principal = Depends(admin),
    session: Session = Depends(get_session),
):
    return TrackerStatusMapping(
        items=service.replace_tracker_mapping(session, data, principal.subject)
    )
