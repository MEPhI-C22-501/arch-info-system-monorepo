import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import Role, require_roles
from app.db import get_session
from app.schemas import Page, PageParams
from app.templates import service
from app.templates.schemas import Template, TemplateInput

router = APIRouter(prefix="/templates", tags=["templates"])

# 130: чтение — R-02 и выше, запись — R-05 (070, раздел 2).
readers = require_roles(Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)
admin = require_roles(Role.ADMIN)


@router.get("", response_model=Page[Template], dependencies=[Depends(readers)])
def list_templates(
    is_active: bool | None = Query(None, alias="isActive"),
    params: PageParams = Depends(),
    session: Session = Depends(get_session),
):
    return service.list_templates(session, is_active, params)


@router.get("/{id}", response_model=Template, dependencies=[Depends(readers)])
def get_template(id: uuid.UUID, session: Session = Depends(get_session)):
    return service.get_template(session, id)


@router.post(
    "", response_model=Template, status_code=status.HTTP_201_CREATED, dependencies=[Depends(admin)]
)
def create_template(data: TemplateInput, session: Session = Depends(get_session)):
    return service.create_template(session, data)


@router.put("/{id}", response_model=Template, dependencies=[Depends(admin)])
def update_template(id: uuid.UUID, data: TemplateInput, session: Session = Depends(get_session)):
    return service.update_template(session, id, data)
