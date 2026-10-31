import uuid

from app.cases.schemas import Code, StepInput
from app.models.enums import Severity
from app.schemas import ApiModel, NonEmptyStr


class TemplateBody(ApiModel):
    """Поля и шаги по умолчанию; хранятся в test_case_template.body в camelCase."""

    description: str | None = None
    preconditions: str | None = None
    priority: Code | None = None
    severity: Severity | None = None
    type: Code | None = None
    steps: list[StepInput] = []


class TemplateInput(ApiModel):
    name: NonEmptyStr
    description: str | None = None
    body: TemplateBody = TemplateBody()
    is_active: bool = True


class Template(ApiModel):
    id: uuid.UUID
    name: str
    description: str | None
    body: TemplateBody
    is_active: bool
