import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.service import check_codes
from app.cases.service import CLASSIFIER_FIELDS
from app.errors import not_found, validation_failed
from app.models import TestCaseTemplate
from app.schemas import Page, PageParams, paginate
from app.templates.schemas import Template, TemplateInput


def list_templates(session: Session, is_active: bool | None, params: PageParams) -> Page[Template]:
    stmt = select(TestCaseTemplate).order_by(TestCaseTemplate.name)
    if is_active is not None:
        stmt = stmt.where(TestCaseTemplate.is_active == is_active)
    return paginate(session, stmt, params, Template)


def get_template(session: Session, template_id: uuid.UUID) -> Template:
    return Template.model_validate(_get(session, template_id))


def create_template(session: Session, data: TemplateInput) -> Template:
    _validate(session, data)
    template = TestCaseTemplate(**_columns(data))
    session.add(template)
    session.commit()
    return Template.model_validate(template)


def update_template(session: Session, template_id: uuid.UUID, data: TemplateInput) -> Template:
    template = _get(session, template_id)
    _validate(session, data, template.id)
    for column, value in _columns(data).items():
        setattr(template, column, value)
    session.commit()
    return Template.model_validate(template)


def _get(session: Session, template_id: uuid.UUID) -> TestCaseTemplate:
    template = session.get(TestCaseTemplate, template_id)
    if template is None:
        raise not_found("Шаблон")
    return template


def _validate(session: Session, data: TemplateInput, own_id: uuid.UUID | None = None) -> None:
    same_name = session.scalar(
        select(TestCaseTemplate.id).where(TestCaseTemplate.name == data.name)
    )
    errors = [{"field": "name", "reason": "duplicate"}] if same_name not in (None, own_id) else []
    codes = {
        f"body.{field}": (kind, str(getattr(data.body, field)))
        for field, kind in CLASSIFIER_FIELDS.items()
        if getattr(data.body, field)
    }
    errors += check_codes(session, codes)
    if errors:
        raise validation_failed(errors, "Шаблон не прошёл проверку")


def _columns(data: TemplateInput) -> dict:
    return {
        "name": data.name,
        "description": data.description,
        "body": data.body.model_dump(by_alias=True, exclude_none=True, mode="json"),
        "is_active": data.is_active,
    }
